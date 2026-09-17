#!/usr/bin/env python3
"""글의 문체를 6축으로 계량한다. 표준 라이브러리만 쓴다.

축 선정 기준은 하나다 — 레퍼런스 코퍼스에서 실제로 측정되고, 윤문 전후로
비교 가능해야 한다. 측정할 수 없는 축은 넣지 않는다.
형태소 분석기는 쓰지 않는다(설치 부담 > 정확도 이득). 접미사·어미 사전으로 근사한다.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

VERSION = "0.1.0"

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_EOJEOL_SPLIT = re.compile(r"\s+")
_PUNCT_STRIP = re.compile(r"""[.,!?;:()\[\]{}"'`~、。“”‘’\-—–]+""")
_MIN_SENT_CHARS = 2  # 짧은 문장은 버리지 않는다 — V-2 가 재려는 신호가 바로 그것이다

# --- 한자어 명사화 (F계열): "-성/-적/-화" + 조사 -----------------------------
_NOMINALIZER_SUFFIXES = ("성", "적", "화")
# 접미사가 아니라 어근의 일부인 흔한 낱말. 오탐의 대부분이 여기서 나온다.
_NOMINALIZER_BLOCK = {
    "변화", "문화", "영화", "대화", "회화", "동화", "만화", "소화", "강화",
    "여성", "남성", "음성", "속성", "완성", "구성", "작성", "달성", "적성",
    "목적", "지적", "면적", "체적", "기적", "사적", "공적", "인적",
}

# --- 결산 관용구 (D계열) ------------------------------------------------------
_CLOSING_IDIOMS = (
    "결론적으로", "따라서", "이를 통해", "그러므로", "요컨대",
    "정리하자면", "정리하면", "종합하면", "궁극적으로",
)

# --- 인간 표지: 과윤문 방지용. 줄어들면 실패다 -------------------------------
_HUMAN_MARKERS = {
    "colloquial_ending": re.compile(
        r"더라고요|더라고|거든요|잖아요|네요|고요[.!?]|(?<![가-힣])죠[.!?,]"
    ),
    "first_person": re.compile(r"(?<![가-힣])(?:저는|제가|저희|내가|나는|우리)(?![가-힣])"),
    "hedge": re.compile(r"것\s*같|싶[은다어]|모르겠|아닐까|(?<![가-힣])듯(?![가-힣])"),
    "self_deprecation": re.compile(r"삽질|서툴|부끄|어설프|헤맸|망했|기우|멍때|엉뚱|솔직히"),
}

# --- 종결 체계 ----------------------------------------------------------------
_HAEYO = re.compile(r"(?:요|죠)[.!?]?$")
_HAPNIDA = re.compile(r"(?:다|까)[.!?]?$")

# --- 연결어미 뒤 쉼표 (C계열) -------------------------------------------------
_ENDING_COMMA = re.compile(r"(?:고|며|면서|지만|는데|은데|아서|어서|하여|여|니까|므로),")


def split_sentences(text: str) -> list[str]:
    body = strip_markup_lines(text)
    return [s.strip() for s in _SENT_SPLIT.split(body) if len(s.strip()) >= _MIN_SENT_CHARS]


def strip_markup_lines(text: str) -> str:
    """헤딩 기호·인용 기호·불릿 기호만 벗긴다. 글자는 남긴다."""
    out = []
    for line in text.split("\n"):
        line = re.sub(r"^\s*(?:#{1,6}\s+|>\s?|[-*+]\s+|\d{1,3}[.)]\s+)", "", line)
        out.append(line)
    return "\n".join(out)


def eojeols(text: str) -> list[str]:
    return [t for t in _EOJEOL_SPLIT.split(strip_markup_lines(text)) if t]


def sentence_cv(text: str) -> float:
    """문장 길이 변동계수. 사람 글은 길이가 출렁이고 AI 글은 평평하다."""
    lengths = [len(s) for s in split_sentences(text)]
    if len(lengths) < 3:
        return 0.0
    mean = statistics.mean(lengths)
    if mean == 0:
        return 0.0
    return statistics.pstdev(lengths) / mean


def hanja_nominalizer_density(text: str) -> float:
    tokens = eojeols(text)
    if not tokens:
        return 0.0
    hits = 0
    for token in tokens:
        stem = _PUNCT_STRIP.sub("", token)
        # 조사를 최대 2음절까지 떼면서 접미사를 찾는다
        for cut in (0, 1, 2):
            candidate = stem[: len(stem) - cut] if cut else stem
            if len(candidate) < 2:
                continue
            if candidate[-1] in _NOMINALIZER_SUFFIXES and candidate not in _NOMINALIZER_BLOCK:
                hits += 1
                break
    return hits / len(tokens)


def closing_idiom_count(text: str) -> int:
    return sum(text.count(idiom) for idiom in _CLOSING_IDIOMS)


def human_marker_rate(text: str) -> dict[str, float]:
    """1000자당 인간 표지 밀도. 각 항목과 합계를 함께 낸다."""
    n = max(len(text), 1)
    out = {name: len(rx.findall(text)) / n * 1000 for name, rx in _HUMAN_MARKERS.items()}
    out["total"] = sum(out.values())
    return out


def ending_register(text: str) -> dict[str, float | str | int]:
    """해요체/합니다체 판정과 혼용률."""
    haeyo = hapnida = 0
    for sentence in split_sentences(text):
        stem = sentence.strip()
        if _HAEYO.search(stem):
            haeyo += 1
        elif _HAPNIDA.search(stem):
            hapnida += 1
    classified = haeyo + hapnida
    if classified == 0:
        return {"dominant": "unknown", "haeyo": 0, "hapnida": 0, "mixing_rate": 0.0}
    dominant = "haeyo" if haeyo >= hapnida else "hapnida"
    minority = min(haeyo, hapnida)
    return {
        "dominant": dominant,
        "haeyo": haeyo,
        "hapnida": hapnida,
        "mixing_rate": minority / classified,
    }


def lexical_diversity(text: str) -> float:
    tokens = [_PUNCT_STRIP.sub("", t) for t in eojeols(text)]
    tokens = [t for t in tokens if t]
    if not tokens:
        return 0.0
    return len(set(tokens)) / len(tokens)


def ending_comma_rate(text: str) -> float:
    sentences = split_sentences(text)
    if not sentences:
        return 0.0
    return sum(1 for s in sentences if _ENDING_COMMA.search(s)) / len(sentences)


def decoration_counts(text: str) -> dict[str, int]:
    return {
        "bold": len(re.findall(r"\*\*[^*\n]+\*\*", text)),
        "emoji": len(re.findall(r"[\U0001F300-\U0001FAFF☀-➿]", text)),
        "em_dash": text.count("—") + text.count("–"),
    }


def compute(text: str) -> dict:
    sentences = split_sentences(text)
    lengths = [len(s) for s in sentences] or [0]
    return {
        "version": VERSION,
        "char_count": len(text),
        "sentence_count": len(sentences),
        "sentence_mean": round(statistics.mean(lengths), 2),
        "sentence_stdev": round(statistics.pstdev(lengths), 2),
        "axes": {
            "sentence_cv": round(sentence_cv(text), 4),
            "hanja_nominalizer_density": round(hanja_nominalizer_density(text), 5),
            "closing_idiom_count": closing_idiom_count(text),
            "human_marker_total": round(human_marker_rate(text)["total"], 3),
            "register_mixing_rate": round(float(ending_register(text)["mixing_rate"]), 4),
            "lexical_diversity": round(lexical_diversity(text), 4),
        },
        "register": ending_register(text),
        "human_markers": {k: round(v, 3) for k, v in human_marker_rate(text).items()},
        "ending_comma_rate": round(ending_comma_rate(text), 4),
        "decoration": decoration_counts(text),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="한국어 글의 문체를 6축으로 계량한다.")
    ap.add_argument("--input", required=True, help="측정할 텍스트 파일")
    ap.add_argument("--output", help="결과 JSON 경로 (생략 시 stdout)")
    args = ap.parse_args(argv)

    path = Path(args.input)
    if not path.is_file():
        print(f"입력 파일을 찾을 수 없다: {path}", file=sys.stderr)
        return 3
    report = compute(path.read_text(encoding="utf-8"))
    blob = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(blob + "\n", encoding="utf-8")
    else:
        print(blob)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
