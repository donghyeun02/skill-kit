# 레퍼런스 픽스처

베이스라인 유도와 **네거티브 회귀 테스트**에 쓰는 사람 글입니다. "손대면 실패"를 확인하는
용도라서, 오탐률을 재는 데 이 파일들이 쓰입니다.

| 파일 | 출처 | 저작자 | 저장소 포함 |
|---|---|---|---|
| `ref_donghyeun02.txt` | https://www.donghyeun02.com/about | 저장소 소유자 | 포함 |
| `ref_daangn.txt` | https://medium.com/daangn — 「프론트엔드와 백엔드를 한 팀으로 합치면 어떤 일이 일어날까?」 | 당근 / Iltaek | **미포함** |
| `ref_yeolyi.txt` | https://yeolyi.com/post/about-insta — 「개발 인스타 이대로만 하면 되는걸까」 | 이성열 | **미포함** |

## 제3자 글을 넣지 않은 이유

두 편은 다른 사람의 저작물이라 전문을 공개 저장소에 올리지 않습니다. 대신 이 글들에서
**측정한 수치**는 `skills/gyeol/references/baseline.json` 의 `per_source_axes` 에 남아 있고,
게이트 임계도 세 편 전부에서 유도한 값 그대로입니다. 수치는 원문이 아니므로 공개해도 됩니다.

`.gitignore` 에 두 파일을 올려 두었으니 로컬에 있어도 커밋되지 않습니다.

## CI 에서는

두 편이 없으면 `ref_donghyeun02.txt` 만으로 대역·경로 테스트를 돌리고, 세 편이 모두 필요한
`test_baseline_can_be_regenerated` 는 건너뜁니다.

## 로컬에서 전부 돌리려면

위 URL 에서 본문 텍스트를 받아 같은 파일 이름으로 이 폴더에 두면 됩니다. 그 뒤:

```bash
python3 -m unittest discover -s tests     # 재현 검사까지 포함
```

## 레퍼런스를 내 글로 바꾸려면

```bash
python3 scripts/build_baseline.py --refs tests/fixtures/ref_*.txt \
    --output skills/gyeol/references/baseline.json --label "..."
python3 -m unittest discover -s tests
```

`test_references_sit_inside_bands` 가 새 레퍼런스도 대역 안에 있는지 확인합니다.
