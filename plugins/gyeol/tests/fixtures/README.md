# 레퍼런스 픽스처

베이스라인 유도와 **네거티브 회귀 테스트**에 쓰는 사람 글이다. "손대면 실패"를
확인하는 용도이므로, 오탐률을 재는 데 이 파일들이 쓰인다.

| 파일 | 출처 | 저작자 |
|---|---|---|
| `ref_daangn.txt` | https://medium.com/daangn — 「프론트엔드와 백엔드를 한 팀으로 합치면 어떤 일이 일어날까?」 | 당근 / Iltaek |
| `ref_yeolyi.txt` | https://yeolyi.com/post/about-insta — 「개발 인스타 이대로만 하면 되는걸까」 | 이성열 |
| `ref_donghyeun02.txt` | https://www.donghyeun02.com/about | 저장소 소유자 |

## 공개 전 확인할 것

앞의 두 편은 **제3자 저작물**이다. 저장소를 공개하기 전에 셋 중 하나를 택한다.

1. 본인 글 3편 이상으로 교체하고 베이스라인을 재생성한다 (권장 — 프로파일이
   실제로 자기 목소리가 된다)
2. 인용 범위를 짧은 발췌로 줄인다 (문장 수가 줄면 지표가 불안정해지니 재검증 필요)
3. 저작자에게 사용 허락을 받고 이 표에 명시한다

교체 방법:

```bash
python3 scripts/build_baseline.py --refs tests/fixtures/ref_*.txt \
    --output skills/gyeol/references/baseline.json --label "..."
python3 -m unittest discover -s tests
```

`test_references_sit_inside_bands` 가 새 레퍼런스도 대역 안에 있는지 확인한다.
