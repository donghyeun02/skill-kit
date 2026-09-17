#!/usr/bin/env python3
"""패키지 정합성 검사. 외부 의존성 없음.

버전이 세 곳에 흩어져 있으면 반드시 어긋난다. 여기서 강제한다.
(검사 방식은 blader/humanizer 의 validate-package.py 에서 가져왔다. MIT.)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILURES: list[str] = []


def fail(message: str) -> None:
    FAILURES.append(message)


def read(path: Path) -> str:
    if not path.is_file():
        fail(f"필수 파일 없음: {path.relative_to(ROOT)}")
        return ""
    return path.read_text(encoding="utf-8")


skill = read(ROOT / "skills" / "gyeol" / "SKILL.md")
readme = read(ROOT / "README.md")
plugin_raw = read(ROOT / ".claude-plugin" / "plugin.json")
# 독립 레포면 자기 marketplace.json, 모노레포(skill-kit)면 루트 marketplace.json 의 gyeol 항목을 본다.
_marketplace_candidates = [ROOT / ".claude-plugin" / "marketplace.json",
                           ROOT.parents[1] / ".claude-plugin" / "marketplace.json"]
_marketplace_path = next((c for c in _marketplace_candidates if c.is_file()), None)
if _marketplace_path is None:
    fail("marketplace.json 을 찾지 못했다 (플러그인 루트와 모노레포 루트 모두 없음)")
marketplace_raw = _marketplace_path.read_text(encoding="utf-8") if _marketplace_path else ""

# --- 버전 3중 동기화 -----------------------------------------------------------
skill_version = re.search(r'(?m)^version:\s*["\']([^"\']+)["\']\s*$', skill)
readme_version = re.search(r"(?m)^- \*\*(\d+\.\d+\.\d+)\*\*", readme)
plugin = json.loads(plugin_raw) if plugin_raw else {}
marketplace = json.loads(marketplace_raw) if marketplace_raw else {}

versions = {
    "SKILL.md": skill_version.group(1) if skill_version else None,
    "README.md": readme_version.group(1) if readme_version else None,
    "plugin.json": plugin.get("version"),
    "marketplace.json": next(
        (e.get("version") for e in marketplace.get("plugins", []) if e.get("name") == "gyeol"),
        marketplace.get("metadata", {}).get("version"),
    ),
}
for name, value in versions.items():
    if not value:
        fail(f"{name} 에서 버전을 찾지 못했다")
distinct = {v for v in versions.values() if v}
if len(distinct) > 1:
    fail(f"버전이 어긋난다: {versions}")

# --- 매니페스트 --------------------------------------------------------------
if plugin.get("skills") != ["./skills/gyeol"]:
    fail('plugin.json 의 skills 는 ["./skills/gyeol"] 이어야 한다')
if plugin.get("license") != "MIT" or not (ROOT / "LICENSE").is_file():
    fail("MIT 라이선스 선언과 LICENSE 파일이 함께 있어야 한다")

# --- 스킬 파일은 하나 ----------------------------------------------------------
skill_files = {p.relative_to(ROOT) for p in ROOT.rglob("SKILL.md")}
if skill_files != {Path("skills/gyeol/SKILL.md")}:
    fail(f"SKILL.md 는 하나여야 한다. 발견: {sorted(str(p) for p in skill_files)}")

# --- 룰북 생성물이 SSOT 와 일치하는가 -------------------------------------------
sys.path.insert(0, str(ROOT / "scripts"))
import build_rules  # noqa: E402

patterns = build_rules.parse(ROOT / "skills" / "gyeol" / "references" / "voice-rules.md")
if not patterns:
    fail("voice-rules.md 에서 패턴을 읽지 못했다")
for error in build_rules.validate(patterns):
    fail(f"룰북: {error}")
if build_rules.main(["--check"]) != 0:
    fail("생성 룰북이 SSOT 와 어긋난다. build_rules.py 를 다시 돌릴 것")

# --- 에이전트가 전부 존재하는가 -------------------------------------------------
referenced = set(re.findall(r"`(gyeol-[a-z]+)`", skill))
present = {p.stem for p in (ROOT / "agents").glob("*.md")}
for name in referenced - present:
    fail(f"SKILL.md 가 참조하는 에이전트 정의가 없다: {name}")

# --- 베이스라인 ---------------------------------------------------------------
baseline_path = ROOT / "skills" / "gyeol" / "references" / "baseline.json"
if baseline_path.is_file():
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if len(baseline.get("sources", [])) < 2:
        fail("baseline.json 의 레퍼런스가 2편 미만이다")
    for axis, band in baseline.get("bands", {}).items():
        if band.get("kind") not in ("floor", "ceiling"):
            fail(f"baseline 축 {axis} 의 kind 가 floor|ceiling 이 아니다")
else:
    fail("baseline.json 이 없다. build_baseline.py 를 돌릴 것")

if FAILURES:
    for message in FAILURES:
        print(f"[validate] {message}", file=sys.stderr)
    raise SystemExit(1)

print(f"[validate] 통과 — 버전 {versions['plugin.json']} / 패턴 {len(patterns)}개 "
      f"/ 에이전트 {len(present)}종")
