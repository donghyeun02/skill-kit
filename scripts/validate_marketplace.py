#!/usr/bin/env python3
"""마켓플레이스 전체 정합성 검사. 표준 라이브러리만 쓴다.

플러그인이 늘어나면 매니페스트끼리 어긋나는 게 제일 먼저 생긴다.
이름·버전·경로·구성요소를 여기서 한 번에 확인한다.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILURES: list[str] = []
SECRET = re.compile(r"sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def fail(message: str) -> None:
    FAILURES.append(message)


def frontmatter(path: Path) -> str:
    match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


def check_plugin(entry: dict) -> None:
    name = entry.get("name", "?")
    source = ROOT / entry.get("source", "")
    manifest_path = source / ".claude-plugin" / "plugin.json"
    if not manifest_path.is_file():
        fail(f"{name}: {manifest_path.relative_to(ROOT)} 가 없다")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("name") != name:
        fail(f"{name}: plugin.json 의 name 이 {manifest.get('name')!r} 이다")
    if manifest.get("version") != entry.get("version"):
        fail(f"{name}: 버전 불일치 — marketplace {entry.get('version')} / plugin.json {manifest.get('version')}")

    commands = sorted((source / "commands").glob("*.md"))
    skills = sorted(source.glob("skills/*/SKILL.md"))
    agents = sorted((source / "agents").glob("*.md"))
    if not (commands or skills or agents):
        fail(f"{name}: commands/skills/agents 중 아무것도 없다")

    for skill in skills:
        meta = frontmatter(skill)
        declared = re.search(r"(?m)^name:\s*(\S+)", meta)
        if not declared or declared.group(1) != skill.parent.name:
            fail(f"{name}: {skill.relative_to(ROOT)} 의 name 이 디렉터리 이름과 다르다")
        if not re.search(r"(?m)^description:", meta):
            fail(f"{name}: {skill.relative_to(ROOT)} 에 description 이 없다")
    for command in commands:
        if not re.search(r"(?m)^description:", frontmatter(command)):
            fail(f"{name}: {command.relative_to(ROOT)} 에 description 이 없다")
    for agent in agents:
        if not re.search(r"(?m)^name:", frontmatter(agent)):
            fail(f"{name}: {agent.relative_to(ROOT)} 에 name 이 없다")

    for path in source.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".json", ".py", ".txt", ".toml", ".yml"}:
            if SECRET.search(path.read_text(encoding="utf-8", errors="ignore")):
                fail(f"{name}: 시크릿으로 보이는 문자열 — {path.relative_to(ROOT)}")

    print(f"  {name:16s} {entry.get('version'):8s} "
          f"commands {len(commands)} · skills {len(skills)} · agents {len(agents)}")


def main() -> int:
    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    entries = marketplace.get("plugins", [])
    names = [e.get("name") for e in entries]
    if len(names) != len(set(names)):
        fail(f"플러그인 이름 중복: {names}")

    listed = {(ROOT / e.get("source", "")).resolve() for e in entries}
    for directory in sorted((ROOT / "plugins").iterdir()):
        if directory.is_dir() and directory.resolve() not in listed:
            fail(f"marketplace.json 에 등록되지 않은 플러그인 디렉터리: {directory.relative_to(ROOT)}")

    print(f"[marketplace] {marketplace.get('name')} — 플러그인 {len(entries)}개")
    for entry in entries:
        check_plugin(entry)

    if FAILURES:
        for message in FAILURES:
            print(f"[marketplace] {message}", file=sys.stderr)
        return 1
    print("[marketplace] 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
