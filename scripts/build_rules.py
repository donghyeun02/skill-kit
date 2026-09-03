#!/usr/bin/env python3
"""SSOT 룰북에서 사전용·사후용 룰북 두 개를 생성한다.

같은 지식을 두 곳에 손으로 적으면 반드시 어긋난다. 원본은 voice-rules.md 하나이고
산출물은 여기서 만든다. 산출물을 직접 고치면 다음 빌드에서 덮어써진다.
(빌드 계약 구조는 epoko77-ai/im-not-ai 의 quick 빌드 메타에서 가져왔다. MIT.)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_HEADING = re.compile(r"^###\s+([A-Z]-\d+)\.\s+(.+?)\s*(?:\[(S\d)\])?\s*$")
_CATEGORY = re.compile(r"^##\s+([A-Z])\.\s+(.+?)\s*$")
_META = re.compile(r"^-?\s*_meta:\s*(.+?)_?\s*$")


def parse(path: Path) -> list[dict]:
    patterns: list[dict] = []
    category = None
    current: dict | None = None
    for raw in path.read_text(encoding="utf-8").split("\n"):
        line = raw.rstrip()
        cat = _CATEGORY.match(line)
        if cat:
            category = f"{cat.group(1)}. {cat.group(2)}"
            continue
        head = _HEADING.match(line)
        if head:
            current = {
                "id": head.group(1),
                "title": head.group(2).strip(),
                "severity": head.group(3) or "S2",
                "category": category or "",
                "stage": None,
                "write": None,
                "rewrite": None,
            }
            patterns.append(current)
            continue
        meta = _META.match(line)
        if meta and current is not None:
            body = meta.group(1).rstrip("_")
            for field in body.split(" · "):
                if "=" not in field:
                    continue
                key, _, value = field.partition("=")
                key = key.strip()
                value = value.strip().strip('"')
                if key in ("stage", "write", "rewrite"):
                    current[key] = value
    return patterns


def validate(patterns: list[dict]) -> list[str]:
    errors = []
    seen: set[str] = set()
    for p in patterns:
        if p["id"] in seen:
            errors.append(f"{p['id']}: ID 중복")
        seen.add(p["id"])
        if p["stage"] not in ("write", "rewrite", "both"):
            errors.append(f"{p['id']}: stage 가 write|rewrite|both 중 하나여야 한다 (현재 {p['stage']!r})")
            continue
        if p["stage"] in ("write", "both") and not p["write"]:
            errors.append(f"{p['id']}: stage={p['stage']} 인데 write= 지시가 없다")
        if p["stage"] in ("rewrite", "both") and not p["rewrite"]:
            errors.append(f"{p['id']}: stage={p['stage']} 인데 rewrite= 처방이 없다")
    return errors


def render(patterns: list[dict], field: str, header: str, footer: str) -> str:
    out = [header.rstrip(), ""]
    current_category = None
    for p in patterns:
        if not p.get(field):
            continue
        if p["category"] != current_category:
            current_category = p["category"]
            if out and out[-1] != "":
                out.append("")
            out.append(f"## {current_category}")
            out.append("")
        out.append(f"- **{p['id']}** [{p['severity']}] {p[field]}")
    out.append(footer.rstrip())
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    refs = root / "skills" / "gyeol" / "references"
    ap = argparse.ArgumentParser(description="voice-rules.md 에서 사전·사후 룰북 생성")
    ap.add_argument("--source", default=str(refs / "voice-rules.md"))
    ap.add_argument("--check", action="store_true",
                    help="생성하지 않고 기존 산출물이 최신인지만 확인한다 (CI용)")
    args = ap.parse_args(argv)

    source = Path(args.source)
    patterns = parse(source)
    if not patterns:
        print("패턴을 하나도 읽지 못했다. 룰북 형식을 확인할 것.", file=sys.stderr)
        return 1

    errors = validate(patterns)
    if errors:
        for e in errors:
            print(f"[build_rules] {e}", file=sys.stderr)
        return 1

    targets = {
        "quick-rules.md": ("rewrite", refs / "quick-rules.header.md"),
        "write-rules.md": ("write", refs / "write-rules.header.md"),
    }
    footer = (refs / "rules.footer.md").read_text(encoding="utf-8")

    failed = False
    for name, (field, header_path) in targets.items():
        content = render(patterns, field, header_path.read_text(encoding="utf-8"), footer)
        out_path = refs / name
        count = sum(1 for p in patterns if p.get(field))
        if args.check:
            existing = out_path.read_text(encoding="utf-8") if out_path.is_file() else ""
            if existing != content:
                print(f"[build_rules] {name} 가 SSOT 와 어긋난다. build_rules.py 를 다시 돌릴 것.",
                      file=sys.stderr)
                failed = True
            else:
                print(f"[build_rules] {name} 최신 ({count}개)")
        else:
            out_path.write_text(content, encoding="utf-8")
            print(f"[build_rules] {name} 생성 — {count}개 패턴")

    if not args.check:
        stages = {}
        for p in patterns:
            stages[p["stage"]] = stages.get(p["stage"], 0) + 1
        print(f"[build_rules] 총 {len(patterns)}개 / " +
              " · ".join(f"{k}={v}" for k, v in sorted(stages.items())))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
