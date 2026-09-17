"""gyeol 회귀 테스트. 표준 라이브러리만 쓴다: python3 -m unittest discover -s tests"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
REFS = ROOT / "skills" / "gyeol" / "references"
FIXTURES = ROOT / "tests" / "fixtures"
GOLDEN = ROOT / "tests" / "golden"

sys.path.insert(0, str(SCRIPTS))
import build_rules  # noqa: E402
import prepare_input  # noqa: E402
import profile as profiler  # noqa: E402
import verify_gates  # noqa: E402

BASELINE = json.loads((REFS / "baseline.json").read_text(encoding="utf-8"))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# 제3자 레퍼런스 원문은 저장소에 넣지 않는다(tests/fixtures/README.md).
# 로컬에 있으면 전부 검사하고, CI 처럼 없으면 있는 것만 검사한다.
REFERENCE_FILES = sorted(FIXTURES.glob("ref_*.txt"))
EXPECTED_REFERENCE_COUNT = len(BASELINE["sources"])


class ReferenceCorpus(unittest.TestCase):
    """레퍼런스 글은 정의상 대역 안에 있어야 한다. 벗어나면 대역이 틀린 것이다."""

    def test_at_least_one_reference_available(self):
        self.assertGreaterEqual(len(REFERENCE_FILES), 1, "레퍼런스 픽스처가 하나도 없다")

    def test_references_sit_inside_bands(self):
        for path in REFERENCE_FILES:
            text = read(path)
            report = profiler.compute(text)
            axes = dict(report["axes"])
            axes["closing_idiom_per_1k"] = (
                report["axes"]["closing_idiom_count"] / len(text) * 1000
            )
            for axis, band in BASELINE["bands"].items():
                value = axes[axis]
                with self.subTest(ref=path.name, axis=axis):
                    if band["kind"] == "floor":
                        self.assertGreaterEqual(value, band["threshold"])
                    else:
                        self.assertLessEqual(value, band["threshold"])

    def test_references_route_light(self):
        """사람이 쓴 글은 손댈 필요가 없다고 판정돼야 한다 — 오탐 방지의 핵심 지표."""
        for path in REFERENCE_FILES:
            report = profiler.compute(read(path))
            hint, breaches = prepare_input.route_hint(report, BASELINE)
            with self.subTest(ref=path.name):
                self.assertEqual(hint, "light", f"이탈축: {breaches}")


class Gate(unittest.TestCase):
    def test_identity_passes(self):
        text = read(FIXTURES / "ref_donghyeun02.txt")
        report = verify_gates.judge(text, text, BASELINE, False)
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["change_rate"], 0.0)

    def test_golden_flattened_aborts(self):
        before = read(GOLDEN / "01_flattened" / "input.txt")
        after = read(GOLDEN / "01_flattened" / "bad_output.txt")
        report = verify_gates.judge(before, after, BASELINE, False)
        self.assertEqual(report["exit_code"], 2)
        axes = {f["axis"] for f in report["findings"]}
        self.assertIn("change_rate", axes)
        self.assertIn("sentence_cv", axes)
        self.assertIn("closing_idiom_per_1k", axes)

    def test_marker_strip_caught_despite_low_change_rate(self):
        """이 테스트가 이 저장소의 존재 이유다.

        문자 기반 변경률만 보는 게이트는 이 케이스를 통과시킨다. 구어 어미와
        1인칭만 걷어낸 윤문은 글자를 거의 안 바꾸기 때문이다.
        """
        before = read(GOLDEN / "02_marker_strip" / "input.txt")
        after = read(GOLDEN / "02_marker_strip" / "bad_output.txt")
        report = verify_gates.judge(before, after, BASELINE, False)

        self.assertLess(report["change_rate"], 0.30,
                        "변경률이 경고 대역이면 이 테스트의 전제가 깨진다")
        self.assertEqual(report["exit_code"], 1)
        axes = {f["axis"] for f in report["findings"]}
        self.assertEqual(axes, {"human_marker_retention"})

    def test_summary_block_is_stripped(self):
        text = read(FIXTURES / "ref_donghyeun02.txt")  # 저장소에 항상 있는 레퍼런스
        with_summary = text + "\n\n<!-- GYEOL-SUMMARY -->\n| 항목 | 값 |\n"
        self.assertEqual(verify_gates.strip_summary(with_summary).strip(), text.strip())


class RuleBuild(unittest.TestCase):
    def setUp(self):
        self.patterns = build_rules.parse(REFS / "voice-rules.md")

    def test_patterns_parse(self):
        self.assertGreaterEqual(len(self.patterns), 30)

    def test_meta_contract_holds(self):
        self.assertEqual(build_rules.validate(self.patterns), [])

    def test_generated_rulebooks_are_current(self):
        self.assertEqual(build_rules.main(["--check"]), 0)

    def test_density_rules_never_reach_write_stage(self):
        """설계 불변식.

        밀도·반복 기반 규칙은 문장을 쓰는 순간에 지킬 수 없다. 문단이 끝나기 전에는
        '이미 3번 썼다'를 알 수 없기 때문이다. 이런 규칙이 사전 룰북에 새어 들어가면
        지킬 수 없는 지시가 되고, 사전 룰북은 곧 무시된다.
        """
        density = re.compile(r"\d+\s*회|밀집|반복|남발|연속|이상일 때|넘으면|대역")
        for pattern in self.patterns:
            if pattern["stage"] in ("write", "both") and pattern["write"]:
                with self.subTest(pattern=pattern["id"]):
                    self.assertIsNone(
                        density.search(pattern["write"]),
                        f'{pattern["id"]} 의 write 지시에 밀도 조건이 있다: {pattern["write"]!r}',
                    )

    def test_write_rulebook_is_short(self):
        """사전 룰북은 매 생성마다 컨텍스트에 얹힌다. 길어지면 값이 사라진다."""
        lines = read(REFS / "write-rules.md").count("\n")
        self.assertLess(lines, 60, "사전 룰북이 60줄을 넘으면 규칙을 덜어낼 것")


class Routing(unittest.TestCase):
    def test_ai_slop_routes_heavy(self):
        report = profiler.compute(read(GOLDEN / "01_flattened" / "bad_output.txt"))
        hint, breaches = prepare_input.route_hint(report, BASELINE)
        self.assertEqual(hint, "heavy")
        self.assertGreaterEqual(len(breaches), 4)

    def test_chatbot_frame_is_stripped(self):
        raw = "물론입니다!\n\n본문입니다. 여기가 진짜 내용이에요.\n\n도움이 되셨길 바랍니다."
        cleaned, removed = prepare_input.strip_chatbot_frame(raw)
        self.assertEqual(removed, 2)
        self.assertNotIn("물론입니다", cleaned)
        self.assertNotIn("도움이 되셨길", cleaned)
        self.assertIn("여기가 진짜 내용", cleaned)

    def test_chatbot_frame_on_one_line(self):
        """실사용에서 발견. LLM 은 여는 말을 단독 줄로 쓰지 않는다."""
        for frame in (
            "물론입니다! 요청하신 블로그 글을 작성해 드리겠습니다:",
            "알겠습니다. 아래와 같이 정리했습니다:",
            "네, 바로 작성해 드리겠습니다!",
            "다음은 N+1 문제에 대한 설명입니다:",
        ):
            with self.subTest(frame=frame):
                cleaned, removed = prepare_input.strip_chatbot_frame(frame + "\n\n본문이다.")
                self.assertEqual(removed, 1)
                self.assertNotIn(frame, cleaned)

    def test_body_sentences_survive_frame_stripping(self):
        """오탐이 참을 놓치는 것보다 훨씬 나쁘다. 본문을 지우면 의미가 사라진다."""
        for body in (
            "물론 이 방식에도 한계가 있습니다.",
            "다음은 제가 실제로 겪은 문제입니다.",
            "다음은 N+1 문제에 대한 설명입니다.",
            "결과는 다음과 같이 나왔습니다.",
        ):
            with self.subTest(body=body):
                cleaned, removed = prepare_input.strip_chatbot_frame(body + "\n\n이어지는 본문이다.")
                self.assertEqual(removed, 0, f"본문이 프레임으로 오인됐다: {body!r}")
                self.assertIn(body, cleaned)


class Profile(unittest.TestCase):
    def test_register_detection(self):
        haeyo = profiler.ending_register("오늘은 날씨가 좋아요. 산책을 다녀왔어요. 기분이 좋네요.")
        self.assertEqual(haeyo["dominant"], "haeyo")
        hapnida = profiler.ending_register("오늘은 날씨가 좋습니다. 산책을 다녀왔습니다. 기분이 좋습니다.")
        self.assertEqual(hapnida["dominant"], "hapnida")

    def test_cv_distinguishes_flat_from_varied(self):
        flat = " ".join(["같은 길이의 문장을 반복해서 씁니다."] * 8)
        varied = "짧다. " + "훨씬 더 길고 절이 여러 개 이어지며 호흡이 긴 문장도 섞여 있습니다. " * 3 + "끝."
        self.assertLess(profiler.sentence_cv(flat), profiler.sentence_cv(varied))

    def test_nominalizer_blocklist_prevents_false_positives(self):
        # '문화·변화·영화'는 접미사가 아니라 어근이다
        self.assertEqual(profiler.hanja_nominalizer_density("문화와 변화와 영화를 봤다"), 0.0)


class Package(unittest.TestCase):
    def test_validate_package_passes(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_package.py")],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(
        len(REFERENCE_FILES) == EXPECTED_REFERENCE_COUNT,
        "제3자 레퍼런스 원문이 없어 재현 검사를 건너뛴다 (tests/fixtures/README.md)",
    )
    def test_baseline_can_be_regenerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "baseline.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "build_baseline.py"),
                 "--refs", *[str(p) for p in sorted(FIXTURES.glob("ref_*.txt"))],
                 "--output", str(out)],
                capture_output=True, text=True, cwd=str(SCRIPTS),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            regenerated = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(regenerated["bands"], BASELINE["bands"],
                             "베이스라인이 재현되지 않는다 — 계량이 결정적이지 않다")


if __name__ == "__main__":
    unittest.main()
