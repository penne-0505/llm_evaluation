"""Strict Mode metadata と preset 検証のテスト"""

import tempfile
import unittest
from pathlib import Path

from core.strict_mode import (
    build_strict_mode_metadata,
    get_official_strict_preset,
    validate_official_strict_request,
)


class TestStrictModeMetadata(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp_dir.name)

        self.prompt_path = self.root / "01_prompt.md"
        self.rubric_path = self.root / "01_rubric.md"
        self.judge_prompt_path = self.root / "judge_system_prompt.md"

        self.prompt_path.write_text("prompt", encoding="utf-8")
        self.rubric_path.write_text("rubric", encoding="utf-8")
        self.judge_prompt_path.write_text("judge system prompt", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_profile_id_is_shared_across_subject_models(self):
        preset = get_official_strict_preset()
        preset["judge_models"] = [{"id": "judge-a", "label": "Judge A", "provider": "openrouter"}]
        preset["task_ids"] = ["01"]

        selected_tasks = [
            {
                "id": "01",
                "type": "fact",
                "prompt_file": str(self.prompt_path),
                "rubric_file": str(self.rubric_path),
                "prompt_source": "bundled",
                "rubric_source": "bundled",
            }
        ]

        run_a = build_strict_mode_metadata(
            target_model="openrouter/model-a",
            selected_tasks=selected_tasks,
            judge_models=["judge-a"],
            judge_runs=3,
            subject_temp=0.6,
            judge_system_prompt_path=self.judge_prompt_path,
            judge_system_prompt_source="bundled",
            preset=preset,
        )
        run_b = build_strict_mode_metadata(
            target_model="openrouter/model-b",
            selected_tasks=selected_tasks,
            judge_models=["judge-a"],
            judge_runs=3,
            subject_temp=0.6,
            judge_system_prompt_path=self.judge_prompt_path,
            judge_system_prompt_source="bundled",
            preset=preset,
            requested=True,
        )

        self.assertTrue(run_a["eligible"])
        self.assertTrue(run_b["eligible"])
        self.assertFalse(run_a["enforced"])
        self.assertTrue(run_b["enforced"])
        self.assertEqual(run_a["profile_id"], run_b["profile_id"])
        self.assertEqual(run_a["config"]["subject_model"], "openrouter/model-a")
        self.assertEqual(run_b["config"]["subject_model"], "openrouter/model-b")

    def test_override_resource_marks_run_ineligible(self):
        preset = get_official_strict_preset()
        preset["judge_models"] = [{"id": "judge-a", "label": "Judge A", "provider": "openrouter"}]
        preset["task_ids"] = ["01"]

        selected_tasks = [
            {
                "id": "01",
                "type": "fact",
                "prompt_file": str(self.prompt_path),
                "rubric_file": str(self.rubric_path),
                "prompt_source": "user_override",
                "rubric_source": "bundled",
            }
        ]

        run = build_strict_mode_metadata(
            target_model="openrouter/model-a",
            selected_tasks=selected_tasks,
            judge_models=["judge-a"],
            judge_runs=1,
            subject_temp=0.3,
            judge_system_prompt_path=self.judge_prompt_path,
            judge_system_prompt_source="bundled",
            preset=preset,
        )

        self.assertFalse(run["eligible"])
        self.assertIn("prompt source=user_override", " ".join(run["reasons"]))

    def test_validate_official_strict_request_detects_parameter_mismatch(self):
        preset = get_official_strict_preset()
        preset["judge_models"] = [{"id": "judge-a", "label": "Judge A", "provider": "openrouter"}]
        preset["task_ids"] = ["01"]

        violations = validate_official_strict_request(
            selected_tasks=[
                {
                    "id": "01",
                    "type": "fact",
                    "prompt_file": str(self.prompt_path),
                    "rubric_file": str(self.rubric_path),
                    "prompt_source": "bundled",
                    "rubric_source": "bundled",
                }
            ],
            judge_models=["judge-a"],
            judge_runs=5,
            subject_temp=0.7,
            judge_system_prompt_source="bundled",
            preset=preset,
        )

        self.assertIn("judge_runs mismatch expected=3 actual=5", violations)
        self.assertIn("subject_temp mismatch expected=0.60 actual=0.70", violations)


if __name__ == "__main__":
    unittest.main()
