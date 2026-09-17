# skill-kit

제가 직접 만들어 쓰는 AI 에이전트용 스킬·플러그인 모음입니다. 마켓플레이스 하나로 묶어 두어서, 새 환경에서도 두 줄이면 필요한 걸 다시 깔 수 있습니다.

각 플러그인의 자세한 사용법·동작 방식·한계는 플러그인 폴더의 README에 있습니다.

## 설치

```
/plugin marketplace add donghyeun02/skill-kit
/plugin install <플러그인>@skill-kit
```

업데이트는 `/plugin marketplace update skill-kit` 후 `/plugin update <플러그인>`입니다.

## 플러그인

| 플러그인 | 무엇을 하나 | 구성 | 버전 |
|---|---|---|---|
| [gyeol](plugins/gyeol) | 한국어 글을 레퍼런스 글의 목소리로 맞춥니다. 임계는 레퍼런스에서 유도하고 판정은 파이썬 게이트가 합니다 | 스킬 1 · 에이전트 3 · 스크립트 6 | 0.1.1 |
| [hardening](plugins/hardening) | `/redteam` 증거 기반 감사, `/harden` 점수 기반 반복 하드닝 | 커맨드 2 | 0.1.0 |
| [game-reference](plugins/game-reference) | 만들려는 게임의 레퍼런스를 미국 매출 순위와 리텐션으로 찾습니다 | 스킬 1 (평가 3건) | 0.1.0 |
| [lecture-summary](plugins/lecture-summary) | PDF 강의자료를 한글 요약 노트로 정리합니다 | 스킬 1 | 0.1.0 |

### 어디서 돌아가나

설치는 지금 Claude Code 마켓플레이스로만 됩니다. 스킬 파일 자체는 표준 `SKILL.md` 형식이라, Claude 전용 요소가 없는 것은 다른 에이전트의 스킬 폴더에 넣어도 그대로 동작합니다.

| 플러그인 | 다른 에이전트에서 | 걸리는 부분 |
|---|---|---|
| game-reference | 그대로 동작 | 없음 |
| lecture-summary | 그대로 동작 | 없음 |
| gyeol | 일부만 | 파이썬 스크립트와 룰북은 쓸 수 있지만, 진단 → 윤문 → 마무리 흐름은 Claude Code의 서브에이전트 호출과 `CLAUDE_SKILL_DIR`에 기대고 있습니다 |
| hardening | 동작 안 함 | Claude Code 슬래시 커맨드 형식(`$ARGUMENTS`, `argument-hint`, `subagent_type`)입니다 |

### 필요한 것

| 플러그인 | 외부 의존 |
|---|---|
| gyeol | Python 3.10+ (표준 라이브러리만) |
| hardening | 없음. 내장 `general-purpose` 에이전트만 씀 |
| game-reference | 없음. data.ai 접근이 있으면 더 정확함 |
| lecture-summary | `poppler` (`brew install poppler`) |

## 구조

```
.claude-plugin/marketplace.json   플러그인 목록
plugins/
  gyeol/                          .claude-plugin/ · skills/ · agents/ · scripts/ · tests/
  hardening/                      .claude-plugin/ · commands/
  game-reference/                 .claude-plugin/ · skills/
  lecture-summary/                .claude-plugin/ · skills/
scripts/validate_marketplace.py   마켓플레이스 전체 정합성 검사
.github/workflows/validate.yml    push마다 검사 + gyeol 테스트
```

## 플러그인 추가하기

1. `plugins/<이름>/.claude-plugin/plugin.json`을 만듭니다. `name`은 폴더 이름과 같아야 합니다.
2. 구성요소를 관례 위치에 둡니다. 커맨드는 `commands/*.md`, 스킬은 `skills/<스킬명>/SKILL.md`, 에이전트는 `agents/*.md`.
3. `.claude-plugin/marketplace.json`의 `plugins`에 항목을 추가합니다. 버전은 `plugin.json`과 맞춥니다.
4. 플러그인 README를 씁니다. 순서는 다른 플러그인과 같게 맞춥니다 — 한 문단 소개 → 설치 → 사용법 → 동작 방식 → 실행 예시 → 하지 않는 것 → 알려진 한계 → 버전 기록 → 라이선스. 실행 예시에는 실제로 돌린 결과만 씁니다.
5. 검사를 돌립니다.

```bash
python3 scripts/validate_marketplace.py
claude plugin validate .
```

`validate_marketplace.py`가 확인하는 것: 이름·버전이 매니페스트끼리 맞는지, 등록 안 된 플러그인 폴더가 없는지, 구성요소가 하나 이상 있는지, 스킬 `name`이 폴더 이름과 같은지, 커맨드·스킬에 `description`이 있는지, 시크릿으로 보이는 문자열이 없는지.

## 로컬 원본과 같이 쓸 때

`hardening`, `game-reference`, `lecture-summary`는 원래 `~/.claude/commands/`와 `~/.claude/skills/`에 파일로 두고 쓰던 것입니다. 플러그인으로 설치한 뒤 원본을 지우지 않으면 같은 커맨드·스킬이 두 벌 뜹니다. 하나만 남기세요.

## 라이선스

MIT. gyeol이 가져온 외부 코드·규칙의 출처는 [gyeol README](plugins/gyeol/README.md#출처)에 있습니다.
