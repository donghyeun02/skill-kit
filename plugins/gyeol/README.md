# gyeol (글결)

한국어 글을 **레퍼런스 글의 목소리로 수렴**시키는 Claude Code 플러그인.

"AI 티 제거"와는 다른 목표다. 티를 지우는 일은 뺄셈이라서, 끝까지 하면 밋밋한 글이
남는다. gyeol 은 지울 것보다 **지킬 것**을 먼저 정하고, 그 기준을 레퍼런스 글에서
직접 측정해 들고 있다.

## 무엇이 다른가

**1. 임계값을 손으로 적지 않는다.**
게이트가 쓰는 모든 숫자는 `build_baseline.py` 가 레퍼런스 코퍼스에서 유도한다.
사람이 고른 숫자는 근거가 없고, 근거가 없으면 게이트는 트집이 된다.
레퍼런스를 자기 글로 갈아끼우면 프로파일 전체가 그 사람 목소리로 바뀐다.

```bash
python3 scripts/build_baseline.py --refs my1.txt my2.txt my3.txt \
    --output skills/gyeol/references/baseline.json --label "내 글"
```

**2. 과윤문을 잡는 축이 있다.**
문자 기반 변경률은 구조 편집에 눈이 없다. 구어 어미와 1인칭만 걷어낸 윤문은
글자를 거의 안 바꾸므로 변경률 게이트를 그냥 통과한다. 의미는 보존됐는데 사람
냄새만 빠진 글이 나온다.

`human_marker_retention` 축이 그걸 잡는다. 골든 픽스처 `02_marker_strip` 실측:

| | 값 |
|---|---|
| 변경률 | 8.1% (통과 대역) |
| 인간 표지 유지율 | **14%** |
| 게이트 | exit 1 |

**3. 사전·사후 룰북을 하나의 원본에서 만든다.**
`voice-rules.md` 가 SSOT 다. 거기서 두 산출물이 생성된다.

- `write-rules.md` (20개) — 글을 **쓰기 전** 주입. 문장을 쓰는 순간 지킬 수 있는 규칙만.
- `quick-rules.md` (36개) — 초안을 **쓴 뒤** 윤문. 밀도·분포·리듬 포함.

밀도 기반 규칙은 사전 룰북에 들어갈 수 없다. 문단이 끝나기 전에는 "이미 3번 썼다"를
알 수 없기 때문이다. 이 불변식은 테스트로 강제한다
(`test_density_rules_never_reach_write_stage`).

**4. 판정은 코드가 한다.**
에이전트가 보고하는 변경률은 참고값이다. `verify_gates.py` 의 출력이 SSOT 이고,
오케스트레이터는 그 값을 사용자에게 그대로 전달한다.

## 6축

| 축 | 종류 | 잡는 것 |
|---|---|---|
| `change_rate` | 30% 경고 / 50% 중단 | 의미 드리프트 |
| `sentence_cv` | 하한 | 문장이 평평해지는 것 |
| `hanja_nominalizer_density` | 상한 | "-성/-적/-화" 명사화 |
| `closing_idiom_per_1k` | 상한 | "결론적으로/따라서/이를 통해" |
| `register_mixing_rate` | 상한 | 해요체·합니다체 혼용 |
| `human_marker_retention` | 상대 80% | **구어 어미·1인칭·유보·자기비하를 깎는 것** |

## 설치

```bash
git clone https://github.com/donghyeun02/gyeol.git
cd gyeol && python3 scripts/validate_package.py
```

Claude Code 에서 이 저장소를 마켓플레이스로 추가하거나, `skills/gyeol` 을
`~/.claude/skills/` 로, `agents/*.md` 를 `~/.claude/agents/` 로 연결한다.

> **주의:** `epoko77-ai/im-not-ai` 의 `humanize-korean` 스킬과 트리거가 겹칠 수 있다.
> 서브에이전트는 description 매칭으로 자동 라우팅되므로 둘을 동시에 켜면 엉뚱한
> 쪽이 호출될 수 있다. 하나만 활성화할 것.

## 사용

```
글결 맞춰줘         # 사후 — 계량 → 진단 → 윤문 → 게이트
정밀하게 맞춰줘      # heavy 고정 (3콜)
가볍게              # light 고정 (1콜)
글 쓰기 전 규칙      # 사전 — write-rules.md 를 읽어 전달. 콜 0회
```

경로는 자동으로 정해진다. 대역 이탈 축이 0~1개면 light, 2~3개면 standard,
4개 이상이면 heavy. **입력 길이는 경로를 바꾸지 않는다** — 긴 글이 반드시 더
AI 같지는 않다.

## 구조

```
skills/gyeol/
  SKILL.md              오케스트레이터 (경로 결정 · 게이트 분기 · 결과 전달)
  references/
    voice-rules.md      SSOT 룰북 (37패턴 / 6카테고리)
    quick-rules.md      생성물 — 사후 윤문용
    write-rules.md      생성물 — 사전 작성용
    baseline.json       생성물 — 레퍼런스 코퍼스에서 유도한 대역
agents/
  gyeol-diagnostician   지배 패턴 3~6개 진단 (span 을 세지 않는다)
  gyeol-rewriter        탐지·재작성·자체검증 1콜
  gyeol-finalizer       원문 대조 후 국소 보정 (전체 재작성 금지)
scripts/
  profile.py            6축 계량
  prepare_input.py      입력 저장 · 챗봇 잔재 제거 · route_hint
  verify_gates.py       결정적 게이트 (exit 0/1/2/3)
  build_baseline.py     레퍼런스 → baseline.json
  build_rules.py        SSOT → 룰북 2종
  validate_package.py   버전 4중 동기화 · 룰북 정합 · 에이전트 존재 확인
```

## 개발

```bash
python3 scripts/build_rules.py            # 룰북 재생성
python3 scripts/build_rules.py --check    # 생성물이 SSOT 와 맞는지 (CI)
python3 scripts/validate_package.py       # 패키지 정합성
python3 -m unittest discover -s tests     # 회귀 테스트
```

룰북을 고치면 `voice-rules.md` 만 고치고 `build_rules.py` 를 돌린다.
생성물을 직접 고치면 다음 빌드에서 덮어써진다.

## 레퍼런스 코퍼스

기본 베이스라인은 아래 세 편에서 유도했다. 문장 길이 편차가 크고, 결산 관용구가
거의 없고, 1인칭과 유보 표현이 살아 있다는 공통점이 있다. 종결 체계는 갈리므로
(해요체 1 · 합니다체 2) 고정하지 않고 혼용률만 본다.

| 글 | CV | 한자 명사화 | 종결 |
|---|---|---|---|
| 당근 기술블로그 「프론트엔드와 백엔드를 한 팀으로 합치면」 | 0.54 | 0.008 | 해요체 |
| donghyeun02.com/about | 0.52 | 0.007 | 합니다체 |
| yeolyi.com 「개발 인스타 이대로만 하면 되는걸까」 | 0.69 | 0.016 | 합니다체 |

세 편 모두 회귀 테스트에서 **네거티브 픽스처**로 쓰인다 — 손대면 실패다.
오탐률이 룰북 품질의 진짜 지표이기 때문이다.

## 출처

두 선행 프로젝트에서 구조와 규칙을 가져왔다. 둘 다 MIT 다.

- **[epoko77-ai/im-not-ai](https://github.com/epoko77-ai/im-not-ai)** — SSOT 룰북에서
  슬림 룰북을 빌드하는 계약, exit code 게이트 규약과 변경률 임계(30%/50%),
  `_workspace/{run_id}/` 산출물 구조, 경로 라우팅(light·standard·heavy),
  `SKILL_ROOT` 해석 관용구, 내용 앵커 개념, 번역투 패턴(T 카테고리)과 그 실측 보수화.
- **[blader/humanizer](https://github.com/blader/humanizer)** — 패키지 검증기의 버전
  동기화 방식, `AGENTS.md` 기여 계약 형식, 오탐 목록("What not to flag") 개념,
  구조·형식·챗봇 패턴(S·F·C 카테고리).

V 카테고리, 6축 게이트, 베이스라인 유도, 사전·사후 이원 산출물은 이 저장소의 것이다.

## 버전

- **0.1.0** — 첫 공개. 6축 게이트, 레퍼런스 유도 베이스라인, SSOT→룰북 2종 빌드,
  서브에이전트 3종, 골든 픽스처 2건 + 네거티브 픽스처 3편, 회귀 테스트 18건.

## 라이선스

MIT
