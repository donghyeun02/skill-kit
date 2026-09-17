---
name: gyeol
version: "0.1.1"
description: |
  한국어 글을 레퍼런스 글의 목소리로 수렴시키는 오케스트레이터. AI 티를 지우는 데서
  멈추지 않고, 지정한 레퍼런스 코퍼스에서 측정한 문체 대역(문장 길이 편차·인간 표지
  밀도·한자 명사화·종결 체계)으로 글을 맞춘다. 판정은 파이썬 게이트가 하고 에이전트는
  자기 결과를 채점하지 못한다. 트리거 — "글결 맞춰줘", "gyeol", "내 문체로 다듬어",
  "레퍼런스처럼 고쳐줘", "이 글투로 맞춰줘", "블로그 글 다듬기", "초안 문체 정리",
  "글 쓰기 전 규칙 알려줘"(사전 모드). 맞춤법·오탈자 교정만 필요하면 직접 처리하고,
  내용을 더하거나 빼는 재작성은 이 스킬이 아니다.
---

# gyeol — 한국어 글결 수렴기

목표는 **"AI 티 제거"가 아니라 "레퍼런스 목소리로 수렴"**이다. 둘은 다르다. 뺄셈만 하면
밋밋해진다. 그래서 이 스킬은 지울 것보다 **지킬 것**을 먼저 정하고, 그 기준을
`references/baseline.json` 에 실측값으로 들고 있다.

## 두 가지 모드

| 모드 | 언제 | 무엇을 |
|---|---|---|
| **사전(write)** | 글을 쓰기 **전** | `references/write-rules.md` 를 읽어 규칙을 제시한다. 콜 0회 |
| **사후(rewrite)** | 초안이 **있을 때** | 계량 → 진단 → 윤문 → 게이트 → 마무리 |

사전 규칙에는 밀도·분포 규칙이 없다. 문단이 끝나기 전에는 "이미 3번 썼다"를 알 수
없기 때문이다. 그쪽은 사후 패스가 맡는다. 두 룰북 모두 `voice-rules.md` 하나에서
생성되므로 어긋나지 않는다.

**사용자가 "글 쓰기 전 규칙"·"어떻게 써야 해"를 물으면 사전 모드다.** `write-rules.md`
를 읽어 그대로 전달하고 끝낸다. 파이프라인을 돌리지 않는다.

---

## Phase 0 — 경로와 위치 확정

### 스크립트 루트

**스크립트는 절대경로로 부른다.** `scripts/*.py` 는 설치 루트에 있고 cwd 는 사용자
작업 디렉터리다. 마켓플레이스 설치에서 둘은 일치하지 않는다.

```bash
SKILL_ROOT="$(d="$(cd -P "${CLAUDE_SKILL_DIR}" && pwd)"; \
  while [ "$d" != / ] && [ ! -d "$d/.claude-plugin" ]; do d="$(dirname "$d")"; done; echo "$d")"
```

`.claude-plugin/` 을 만날 때까지 거슬러 올라간다. 고정 깊이로 올라가지 않는 이유는
배포 방식마다 스킬 위치가 달라서다 — 고정 깊이는 레이아웃이 바뀌면 조용히 엉뚱한
곳을 가리킨다. `cd -P` 가 필요한 이유는 심링크 설치에서 셸이 논리 경로를 유지해
엉뚱한 곳으로 올라가기 때문이다.

확인: `ls "${SKILL_ROOT}/scripts/profile.py"`. 실패하면 추측하지 말고 **"계량·게이트
없이 진행한다"고 사용자에게 알린 뒤** 계속한다. 조용히 건너뛰면 게이트가 사라진 것을
아무도 모른다.

`references/*` 는 스킬 디렉터리 기준이라 `${CLAUDE_SKILL_DIR}` 을 쓴다. 두 기준을 섞지 않는다.

### run_id

- `_workspace/{YYYY-MM-DD-NNN}/` — **cwd 기준**이다.
- 기존 시퀀스는 `Glob(pattern="_workspace/*/01_input.txt")` 로 확인하고 폴더명에서
  NNN 최댓값 + 1. Glob 은 디렉터리를 직접 매칭하지 못하므로 표지 파일을 매칭한다.
- 재실행("이 부분만 다시"·"2차")이면 기존 run_id 를 재사용하고 heavy 로 승급한다.

### 상태 줄

Phase 1 직후 한 줄을 출력한다.

```
gyeol v0.1 — 경로 {light|standard|heavy} ({route_hint|사용자 지정}) / run_id {YYYY-MM-DD-NNN}
```

### 경로 결정

1. **사용자 명시가 최우선.** "정밀하게"·"제대로"·`--strict` → heavy 고정.
   "가볍게"·"빠르게" → light 고정.
2. 명시가 없으면 `00_profile.json` 의 `route_hint` 를 따른다.
3. shim 이 실패했으면 standard 로 간주한다.
4. **입력 길이는 경로를 바꾸지 않는다.** 긴 글이 반드시 더 AI 같지는 않다.
   판단은 대역 이탈 축의 개수에 위임한다.

---

## Phase 1 — 입력 저장과 계량 (전 경로 공통)

```bash
python3 "${SKILL_ROOT}/scripts/prepare_input.py" \
    --run-dir _workspace/{run_id} --input _workspace/{run_id}/raw.txt
```

사용자가 붙여넣은 텍스트는 먼저 `_workspace/{run_id}/raw.txt` 로 저장한다.

산출:
- `01_input.txt` — 챗봇 프레임을 벗긴 원문
- `00_profile.json` — 6축 계량 + `route_hint` + 대역 이탈 축
- `01_input_with_profile.txt` — 계량 블록 + 원문 (윤문 에이전트 입력)

`route_hint` 를 읽어 경로를 확정하고 상태 줄을 출력한다.

---

## Light 경로 — 이미 잘 쓴 글 (1콜)

대역 이탈이 0~1개. **목표는 과윤문 방지이지 많이 고치는 게 아니다.**

1. `gyeol-rewriter` 를 `Agent` 로 1회 호출.
   - `input_path=01_input_with_profile.txt`
   - `rules_path=${CLAUDE_SKILL_DIR}/references/quick-rules.md`
   - `strength=보수`
2. Phase 2 게이트 (Bash, LLM 콜 아님).
3. **조기 종료 보고.** 게이트가 통과이고 변경률이 5% 미만이면 결과를
   "이미 좋은 글입니다 — 손댄 곳은 {N}곳" 으로 요약한다. 억지로 더 고치지 않는다.
4. 게이트가 exit 2 면 보수 강도를 재강조해 1회 재실행(총 2콜).

---

## Standard 경로 — 보통의 초안 (2콜)

대역 이탈 2~3개.

1. **진단 1콜** — `gyeol-diagnostician`
   - `input_path=01_input_with_profile.txt`
   - `rules_path=${CLAUDE_SKILL_DIR}/references/voice-rules.md` (SSOT 전문)
   - → `02_diagnosis.md`
2. 진단을 입력 앞에 결합 (Bash, LLM 콜 아님):
   ```bash
   python3 "${SKILL_ROOT}/scripts/prepare_input.py" \
       --run-dir _workspace/{run_id} --diagnosis _workspace/{run_id}/02_diagnosis.md
   ```
3. **윤문 1콜** — `gyeol-rewriter`, `strength=표준` → `final.md`
4. Phase 2 게이트.
5. **마무리는 기본 생략.** 게이트가 결정적으로 판정하므로, 아래 승급 조건에
   걸릴 때만 `gyeol-finalizer` 를 부른다(그 경우 3콜).

---

## Heavy 경로 — 중증이거나 증적이 필요할 때 (3콜)

대역 이탈 4개 이상, 또는 `--strict`.

1. 진단 1콜 (Standard 와 동일)
2. 진단 결합 → 윤문 1콜
3. Phase 2 게이트
4. **마무리 1콜 — heavy 는 항상 실행한다.** `gyeol-finalizer` 에
   `original_path`, `rewritten_path`, `gate_path` 를 준다.
5. 마무리 후 게이트를 한 번 더 돌려 최종 수치를 확정한다.

---

## 마무리 승급 규칙 (전 경로 공통)

| 조건 | finalize |
|---|---|
| heavy 경로 | **항상** |
| 게이트 exit 1 (경고) | 실행 |
| 게이트 exit 2 재발 | 실행 후 `hold_and_report` |
| rewriter 자체검증 6항 중 2개 이상 위반 | 실행 |
| 사용자가 검증·증적을 명시 요청 | 실행 |
| 그 외 light·standard | 생략 |

Light 에서 승급하면 `diagnosis_path` 없이 부른다. 진단을 만들려고 콜을 추가하지 않는다 —
Light 가 승급하는 상황은 "예상보다 많이 고쳤다"이므로, 조준 대상을 새로 찾는 것보다
고친 결과를 검증하는 게 맞다.

---

## Phase 2 — 결정적 게이트

**rewriter 가 보고한 변경률은 참고값이다. 판정은 코드가 한다.**

```bash
python3 "${SKILL_ROOT}/scripts/verify_gates.py" \
    --before _workspace/{run_id}/01_input.txt \
    --after  _workspace/{run_id}/final.md \
    --output _workspace/{run_id}/03_gate.json
```

| exit | 판정 | 후속 |
|---|---|---|
| 0 | 수렴 | 결과 전달 |
| 1 | 경고 — 어느 축이 대역을 벗어남 | 결과 전달 + **걸린 축 고지** + finalize 승급 |
| 2 | 중단 — 변경률 50% 초과 | **윤문본 채택 금지.** 롤백 지시 후 1회 재실행. 재차 2면 `hold_and_report` |
| 3 | 판정 불가 | 입력 확인 후 재시도. **건너뛰지 않는다** |

게이트가 보는 축은 여섯이다. 변경률, 문장 길이 변동계수, 한자 명사화 밀도,
결산 관용구 밀도, 종결 체계 혼용률, 그리고 **인간 표지 유지율**.

마지막 축이 이 게이트의 핵심이다. 문자 기반 변경률은 구조 편집에 눈이 없어서,
구어 어미와 1인칭만 걷어낸 윤문은 변경률 8%로 통과해 버린다. 유지율 축은 그걸 잡는다.
(실측: 골든 픽스처 `02_marker_strip` — 변경률 8.1%, 유지율 14%, exit 1)

`--ignore-markup` 은 헤딩·불릿 산문화로 변경률이 부풀려졌는지 교차 확인할 때만 쓴다.
**판정을 뒤집는 근거로 쓰려면 두 수치를 모두 사용자에게 보고한다.**

---

## 결과 전달

1. **한 줄 상태** — `완료. 경로 {경로} / 변경률 {X}% / 인간표지 유지 {Y}% / 게이트 {판정}`
   수치는 **게이트 스크립트 출력값**을 그대로 쓴다. 에이전트 자가 산출값으로 덮어쓰지 않는다.
2. **윤문본 본문.** light 조기 종료면 "이미 좋습니다 + 손댄 곳 요약"으로 대체 가능.
3. `final.md` 끝 `<!-- GYEOL-SUMMARY -->` 블록의 표.
4. 게이트가 exit 1 이면 **걸린 축과 그 의미**를 한 줄씩 적는다. 숫자만 던지지 않는다.

## 부분 재실행

"이 문단만"·"이 카테고리만 다시"·"2차" 는 기존 run_id 재사용 + heavy 승급이다.
`final.md` 를 새 입력으로 삼지 말고 `01_input.txt` 를 기준으로 다시 돈다 —
윤문본을 다시 윤문하면 의미가 단계마다 미끄러진다.

## 레퍼런스 코퍼스 교체

사용자가 "내 글투로 맞춰줘"라며 자기 글을 주면 베이스라인을 다시 만든다.

```bash
python3 "${SKILL_ROOT}/scripts/build_baseline.py" \
    --refs my1.txt my2.txt my3.txt \
    --output "${CLAUDE_SKILL_DIR}/references/baseline.json" --label "내 글"
```

레퍼런스는 2편 이상이어야 대역이 의미를 가진다. 3편 이상을 권한다.
바꾸고 나면 게이트 임계가 전부 그 사람 글에서 유도된 값이 된다.
