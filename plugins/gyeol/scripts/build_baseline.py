#!/usr/bin/env python3
"""레퍼런스 글 묶음에서 baseline.json 을 만든다.

임계값을 손으로 적지 않는 것이 이 스크립트의 존재 이유다. 사람이 고른 숫자는
근거가 없고, 근거가 없으면 게이트가 트집으로 바뀐다. 여기서는 실제 레퍼런스
코퍼스의 분포에서 대역을 유도하고, 유도 규칙 자체를 파일에 적어둔다.

사용자가 자기 글로 코퍼스를 갈아끼우면 프로파일 전체가 그 사람 목소리로 바뀐다.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import profile as profiler

# 대역 유도 규칙. 숫자를 바꾸려면 이 표를 바꾸고 재생성한다.
# floor  : 레퍼런스 최솟값 × 계수 — 이 아래로 떨어지면 사람 글의 성질을 잃은 것
# ceiling: 레퍼런스 최댓값 × 계수 — 이 위로 올라가면 AI 쪽으로 넘어간 것
DERIVATION = {
    "sentence_cv": ("floor", 0.85),
    "hanja_nominalizer_density": ("ceiling", 1.30),
    "closing_idiom_per_1k": ("ceiling", 1.50),
    "register_mixing_rate": ("ceiling", 1.15),
    "lexical_diversity": ("floor", 0.90),
}

# 상대 축 — 절대 대역이 아니라 윤문 전후 변화로 판정한다.
RELATIVE = {
    # 인간 표지가 원문 대비 이 비율 아래로 줄면 과윤문이다.
    "human_marker_retention": 0.80,
    # im-not-ai 의 변경률 임계를 그대로 쓴다 (출처: epoko77-ai/im-not-ai, MIT).
    "change_rate_warn": 0.30,
    "change_rate_abort": 0.50,
}


def measure(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        report = profiler.compute(text)
        axes = dict(report["axes"])
        axes["closing_idiom_per_1k"] = round(
            report["axes"]["closing_idiom_count"] / max(len(text), 1) * 1000, 4
        )
        rows.append({"name": path.name, "chars": len(text), "axes": axes,
                     "register": report["register"]["dominant"]})
    return rows


def derive(rows: list[dict]) -> dict:
    bands = {}
    for axis, (kind, factor) in DERIVATION.items():
        values = [r["axes"][axis] for r in rows]
        band = {
            "kind": kind,
            "factor": factor,
            "observed": {
                "min": round(min(values), 5),
                "median": round(statistics.median(values), 5),
                "max": round(max(values), 5),
            },
        }
        band["threshold"] = round(
            (min(values) * factor) if kind == "floor" else (max(values) * factor), 5
        )
        bands[axis] = band
    return bands


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="레퍼런스 코퍼스에서 baseline.json 생성")
    ap.add_argument("--refs", nargs="+", required=True, help="레퍼런스 텍스트 파일들")
    ap.add_argument("--output", required=True, help="baseline.json 출력 경로")
    ap.add_argument("--label", default="default", help="프로파일 이름")
    args = ap.parse_args(argv)

    paths = [Path(p) for p in args.refs]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise SystemExit("레퍼런스 파일 없음: " + ", ".join(missing))
    if len(paths) < 2:
        raise SystemExit("레퍼런스는 2편 이상이어야 대역이 의미를 가진다")

    rows = measure(paths)
    baseline = {
        "label": args.label,
        "profile_version": profiler.VERSION,
        "sources": [{"name": r["name"], "chars": r["chars"], "register": r["register"]} for r in rows],
        "per_source_axes": {r["name"]: r["axes"] for r in rows},
        "bands": derive(rows),
        "relative": RELATIVE,
        "note": (
            "임계값은 손으로 적은 값이 아니라 위 레퍼런스 분포에서 유도된 값이다. "
            "레퍼런스를 바꾸고 이 스크립트를 다시 돌리면 프로파일 전체가 따라 바뀐다."
        ),
    }
    Path(args.output).write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"baseline 생성: {args.output} (레퍼런스 {len(rows)}편)")
    for axis, band in baseline["bands"].items():
        obs = band["observed"]
        print(f"  {axis:32s} {band['kind']:7s} {band['threshold']:<10} "
              f"(관측 {obs['min']}~{obs['max']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
