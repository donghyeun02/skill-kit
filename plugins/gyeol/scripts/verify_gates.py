#!/usr/bin/env python3
"""윤문 결과를 결정적으로 판정한다. LLM 콜 0회.

에이전트가 자기 결과를 채점하면 안 된다 — 이 판정이 SSOT다.
게이트 구조와 exit code 규약은 epoko77-ai/im-not-ai (MIT) 에서 가져왔고,
판정 축과 임계 유도 방식은 이 저장소의 것이다.

exit 0  수렴      — 전 축 통과
exit 1  경고      — 어느 축이 대역을 벗어남. 결과는 쓰되 고지하고 finalize 승급
exit 2  중단      — 변경률 초과. 윤문본 채택 금지, 롤백 후 재실행
exit 3  판정불가  — 입력이 없거나 문장이 너무 적음. 건너뛰지 말 것
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

import profile as profiler

_SUMMARY_BLOCK = re.compile(r"<!--\s*GYEOL-SUMMARY\s*-->.*\Z", re.DOTALL)
_DEFAULT_BASELINE = Path(__file__).resolve().parent.parent / "skills" / "gyeol" / "references" / "baseline.json"


def strip_summary(text: str) -> str:
    return _SUMMARY_BLOCK.sub("", text).strip()


def change_rate(before: str, after: str, ignore_markup: bool = False) -> float:
    a, b = before, after
    if ignore_markup:
        a, b = profiler.strip_markup_lines(a), profiler.strip_markup_lines(b)
    a, b = re.sub(r"\s+", "", a), re.sub(r"\s+", "", b)
    if not a:
        return 1.0
    return 1.0 - difflib.SequenceMatcher(None, a, b).ratio()


def judge(before: str, after: str, baseline: dict, ignore_markup: bool) -> dict:
    bands = baseline["bands"]
    rel = baseline["relative"]

    before_report = profiler.compute(before)
    after_report = profiler.compute(after)
    after_axes = dict(after_report["axes"])
    after_axes["closing_idiom_per_1k"] = (
        after_report["axes"]["closing_idiom_count"] / max(len(after), 1) * 1000
    )

    findings: list[dict] = []

    rate = change_rate(before, after, ignore_markup)
    if rate >= rel["change_rate_abort"]:
        findings.append({"axis": "change_rate", "level": "abort",
                         "value": round(rate, 4), "threshold": rel["change_rate_abort"],
                         "message": "변경률이 중단 임계를 넘었다. 의미가 드리프트했을 가능성이 높다."})
    elif rate >= rel["change_rate_warn"]:
        findings.append({"axis": "change_rate", "level": "warn",
                         "value": round(rate, 4), "threshold": rel["change_rate_warn"],
                         "message": "변경률이 경고 대역이다. 과윤문 여부를 확인할 것."})

    for axis, band in bands.items():
        value = after_axes.get(axis)
        if value is None:
            continue
        threshold = band["threshold"]
        breached = value < threshold if band["kind"] == "floor" else value > threshold
        if breached:
            direction = "아래로 떨어졌다" if band["kind"] == "floor" else "위로 넘어갔다"
            findings.append({"axis": axis, "level": "warn",
                             "value": round(value, 5), "threshold": threshold,
                             "message": f"{axis} 가 대역 {direction}."})

    # 상대 축 — 인간 표지가 줄면 과윤문이다. 절대 대역으로는 잡히지 않는다.
    before_marker = before_report["axes"]["human_marker_total"]
    after_marker = after_report["axes"]["human_marker_total"]
    retention = (after_marker / before_marker) if before_marker > 0 else 1.0
    if before_marker > 0 and retention < rel["human_marker_retention"]:
        findings.append({"axis": "human_marker_retention", "level": "warn",
                         "value": round(retention, 4),
                         "threshold": rel["human_marker_retention"],
                         "message": "구어 어미·1인칭·유보 표현이 원문보다 줄었다. 사람 냄새를 깎은 것이다."})

    if any(f["level"] == "abort" for f in findings):
        verdict, code = "abort", 2
    elif findings:
        verdict, code = "warn", 1
    else:
        verdict, code = "pass", 0

    return {
        "verdict": verdict,
        "exit_code": code,
        "change_rate": round(rate, 4),
        "before_axes": before_report["axes"],
        "after_axes": {k: round(v, 5) if isinstance(v, float) else v for k, v in after_axes.items()},
        "human_marker_retention": round(retention, 4),
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="윤문 결과 결정적 게이트")
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--baseline", default=str(_DEFAULT_BASELINE))
    ap.add_argument("--ignore-markup", action="store_true",
                    help="헤딩·불릿 산문화로 변경률이 부풀려졌는지 교차 확인")
    ap.add_argument("--output", help="판정 JSON 저장 경로")
    args = ap.parse_args(argv)

    before_path, after_path = Path(args.before), Path(args.after)
    for path in (before_path, after_path):
        if not path.is_file():
            print(f"[gate] 파일 없음: {path}", file=sys.stderr)
            return 3

    before = before_path.read_text(encoding="utf-8").strip()
    after = strip_summary(after_path.read_text(encoding="utf-8"))
    if len(profiler.split_sentences(before)) < 3:
        print("[gate] 문장이 3개 미만이라 판정할 수 없다.", file=sys.stderr)
        return 3

    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    report = judge(before, after, baseline, args.ignore_markup)

    label = {"pass": "수렴", "warn": "경고", "abort": "중단"}[report["verdict"]]
    print(f"[gate] {label} (exit {report['exit_code']}) / 변경률 {report['change_rate']:.1%} "
          f"/ 인간표지 유지 {report['human_marker_retention']:.0%}")
    for finding in report["findings"]:
        print(f"  - [{finding['level']}] {finding['axis']}: "
              f"{finding['value']} (임계 {finding['threshold']}) — {finding['message']}")
    if args.output:
        Path(args.output).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
