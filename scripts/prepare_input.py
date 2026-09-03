#!/usr/bin/env python3
"""입력을 저장하고 계량한 뒤, 경로(route)를 추천한다.

에이전트가 "이 글은 심해 보인다"로 콜 수를 정하면 매번 달라진다. 여기서 결정적으로
정하고, 오케스트레이터는 그 값을 따른다. 길이는 경로를 바꾸지 않는다 — 긴 글이
반드시 더 AI 같지는 않기 때문이다.

산출물
  01_input.txt              챗봇 잔재를 벗긴 원문
  00_profile.json           6축 계량 + route_hint
  01_input_with_profile.txt [진단] + [계량 블록] + 원문  (윤문 에이전트 입력)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import profile as profiler

# 챗봇 프레임 — 본문이 아니므로 제거해도 의미 손실이 0이다. (착안: im-not-ai, MIT)
# 실사용 관찰: LLM 은 "물론입니다!" 를 단독 줄로 쓰지 않는다.
# "물론입니다! 요청하신 글을 작성해 드리겠습니다:" 처럼 한 줄로 붙여 쓴다.
# 그래서 여는 말만 매칭하면 안 되고, 그 줄 전체가 프레임인지를 봐야 한다.
_CHATBOT_HEAD = re.compile(
    # 여는 말만 한 줄을 차지하는 경우 — 그 자체로 프레임이다.
    r"^\s*(?:물론(?:입니다|이죠|이에요)|알겠습니다|좋습니다)[!.]?\s*$"
    r"|^\s*(?:물론(?:입니다|이죠|이에요)|알겠습니다|좋습니다|네)[!.,]?"
    r"[^\n]{0,80}?(?:드리겠습니다|하겠습니다|드릴게요|정리했습니다|입니다)\s*[:.!]?\s*$"
    # "다음은 ~입니다" 는 본문 문장일 수도 있다("다음은 제가 겪은 문제입니다").
    # 뒤에 내용이 이어진다고 예고하는 콜론이 있을 때만 프레임으로 본다.
    # 참을 놓치는 것보다 본문을 지우는 쪽이 훨씬 나쁘다.
    r"|^\s*(?:다음은|아래는|요청하신)[^\n]{0,80}?(?:입니다|드립니다|드리겠습니다)\s*:\s*$",
    re.MULTILINE,
)
_CHATBOT_TAIL = re.compile(
    r"^\s*(?:도움이\s*(?:되셨|되었)[^\n]*|추가(?:로)?\s*궁금[^\n]*|더\s*궁금한[^\n]*"
    r"|필요하시면[^\n]*말씀[^\n]*|이해에\s*도움이[^\n]*)\s*$",
    re.MULTILINE,
)
_KNOWLEDGE_DISCLAIMER = re.compile(
    r"^\s*(?:제\s*지식은[^\n]*|학습\s*데이터[^\n]*까지[^\n]*|공개된\s*정보가\s*제한[^\n]*)\s*$",
    re.MULTILINE,
)


def strip_chatbot_frame(text: str) -> tuple[str, int]:
    cleaned = text
    removed = 0
    for rx in (_CHATBOT_HEAD, _CHATBOT_TAIL, _KNOWLEDGE_DISCLAIMER):
        cleaned, n = rx.subn("", cleaned)
        removed += n
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, removed


def route_hint(report: dict, baseline: dict) -> tuple[str, list[str]]:
    """대역을 벗어난 축의 개수로 경로를 정한다."""
    axes = dict(report["axes"])
    axes["closing_idiom_per_1k"] = (
        report["axes"]["closing_idiom_count"] / max(report["char_count"], 1) * 1000
    )
    breaches: list[str] = []
    for axis, band in baseline["bands"].items():
        value = axes.get(axis)
        if value is None:
            continue
        if (band["kind"] == "floor" and value < band["threshold"]) or (
            band["kind"] == "ceiling" and value > band["threshold"]
        ):
            breaches.append(axis)

    # 단발 S1 신호는 축 이탈과 별개로 센다.
    decoration = report["decoration"]
    if decoration["emoji"] > 0:
        breaches.append("emoji")
    if report["axes"]["human_marker_total"] < 1.0:
        breaches.append("human_marker_absent")

    if len(breaches) <= 1:
        return "light", breaches
    if len(breaches) <= 3:
        return "standard", breaches
    return "heavy", breaches


def build_combined(report: dict, hint: str, breaches: list[str],
                   body: str, diagnosis: str | None) -> str:
    axes = report["axes"]
    block = [
        "<!-- GYEOL-PROFILE — 계량값이다. 판정 근거로 쓰되 본문에 옮기지 말 것. -->",
        f"- 글자수 {report['char_count']} / 문장 {report['sentence_count']}개 "
        f"/ 평균 {report['sentence_mean']}자",
        f"- 문장 길이 변동계수(CV) {axes['sentence_cv']}  ← 낮으면 평평한 글이다",
        f"- 한자 명사화 밀도 {axes['hanja_nominalizer_density']}",
        f"- 결산 관용구 {axes['closing_idiom_count']}회",
        f"- 인간 표지 {axes['human_marker_total']}/1000자  ← 줄이면 실패다",
        f"- 종결 체계 {report['register']['dominant']} (혼용률 {axes['register_mixing_rate']})",
        f"- 어휘 다양도 {axes['lexical_diversity']}",
        f"- 대역 이탈 축: {', '.join(breaches) if breaches else '없음'}",
        f"- 추천 경로: {hint}",
        "",
    ]
    parts = []
    if diagnosis:
        parts.append("<!-- GYEOL-DIAGNOSIS -->\n" + diagnosis.strip() + "\n")
    parts.append("\n".join(block))
    parts.append(body)
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    default_baseline = root / "skills" / "gyeol" / "references" / "baseline.json"

    ap = argparse.ArgumentParser(description="입력 저장 + 계량 + 경로 추천")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--input", help="원문 파일 (생략 시 run-dir/01_input.txt 재사용)")
    ap.add_argument("--diagnosis", help="진단 파일 — 계량 블록 앞에 붙인다")
    ap.add_argument("--baseline", default=str(default_baseline))
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    input_path = run_dir / "01_input.txt"

    if args.input:
        raw = Path(args.input).read_text(encoding="utf-8")
        body, removed = strip_chatbot_frame(raw)
        input_path.write_text(body + "\n", encoding="utf-8")
        if removed:
            print(f"[prepare] 챗봇 프레임 {removed}줄 제거")
    elif input_path.is_file():
        body = input_path.read_text(encoding="utf-8").strip()
    else:
        print("[prepare] 입력이 없다. --input 을 주거나 01_input.txt 를 먼저 만들 것.",
              file=sys.stderr)
        return 3

    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    report = profiler.compute(body)
    hint, breaches = route_hint(report, baseline)
    report["route_hint"] = hint
    report["breaches"] = breaches
    (run_dir / "00_profile.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    diagnosis = None
    if args.diagnosis:
        diagnosis_path = Path(args.diagnosis)
        if diagnosis_path.is_file():
            diagnosis = diagnosis_path.read_text(encoding="utf-8")

    combined = build_combined(report, hint, breaches, body, diagnosis)
    (run_dir / "01_input_with_profile.txt").write_text(combined, encoding="utf-8")

    print(f"[prepare] route_hint={hint} / 이탈축 {len(breaches)}개"
          f"{' (' + ', '.join(breaches) + ')' if breaches else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
