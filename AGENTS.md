# 에이전트를 위한 안내

이 저장소를 고칠 때 깨뜨리면 안 되는 계약을 적는다.

## 구조

- `skills/gyeol/references/voice-rules.md` 가 **유일한 룰북 원본**이다.
- `quick-rules.md`, `write-rules.md`, `baseline.json` 은 **생성물**이다. 직접 고치지 않는다.
- 판정 수치의 SSOT 는 `scripts/verify_gates.py` 의 출력이다. 에이전트 자가 산출값이 아니다.

## 규칙을 고칠 때

1. `voice-rules.md` 만 고친다.
2. `_meta:` 한 줄을 반드시 붙인다 — `stage=write|rewrite|both`, 그리고 stage 에 맞는
   `write=` / `rewrite=` 지시.
3. `python3 scripts/build_rules.py` 로 재생성한다.
4. `python3 -m unittest discover -s tests` 를 돌린다.

**밀도·반복 조건이 붙은 규칙은 `stage=rewrite` 여야 한다.** 문단이 끝나기 전에는
"이미 3번 썼다"를 알 수 없으므로 사전 룰북에 넣으면 지킬 수 없는 지시가 된다.
`test_density_rules_never_reach_write_stage` 가 이걸 막는다. 테스트가 막으면
테스트를 고치지 말고 `stage` 를 고친다.

## 임계값을 고칠 때

숫자를 직접 적지 않는다. `scripts/build_baseline.py` 의 `DERIVATION` 표에 있는
**유도 규칙**(floor/ceiling 과 계수)을 고치고 재생성한다. 어떤 축의 임계가 왜
그 값인지는 `baseline.json` 의 `observed` 에 남는다.

레퍼런스를 바꾸면 `tests/fixtures/ref_*.txt` 도 함께 바꾼다. 레퍼런스 글은 정의상
대역 안에 있어야 하고, `test_references_sit_inside_bands` 가 그걸 확인한다.

## 축을 추가할 때

새 축은 다음 셋을 모두 만족해야 한다. 하나라도 못 지키면 넣지 않는다.

1. `profile.py` 에서 표준 라이브러리만으로 측정된다
2. 레퍼런스 코퍼스에서 실제 값이 나온다 (베이스라인이 비어 있는 축은 판정에 쓸 수 없다)
3. 윤문 전후로 비교 가능하다

## 버전

`SKILL.md` 의 `version`, `README.md` 의 첫 버전 항목, `plugin.json`,
`marketplace.json` 의 `metadata.version` — 네 곳이 같아야 한다.
`scripts/validate_package.py` 가 강제한다.

## 문체

이 저장소의 문서와 주석은 자기가 만드는 도구의 규칙을 따른다.

- 결론을 먼저 쓴다.
- "결론적으로/따라서/이를 통해"로 문단을 열지 않는다.
- 왜 그렇게 했는지를 적는다. 무엇을 했는지는 코드에 이미 있다.
- 지킬 수 없는 규칙을 적지 않는다.
