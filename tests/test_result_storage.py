"""ResultStorage の保存メタデータテスト"""

import tempfile
import unittest
from pathlib import Path

from core.result_storage import ResultStorage


class TestResultStorage(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.results_dir = Path(self._tmp_dir.name) / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self._orig_results_dir = ResultStorage.RESULTS_DIR
        self._orig_index_file = ResultStorage.INDEX_FILE
        ResultStorage.RESULTS_DIR = self.results_dir
        ResultStorage.INDEX_FILE = self.results_dir / "index.json"

    def tearDown(self) -> None:
        ResultStorage.RESULTS_DIR = self._orig_results_dir
        ResultStorage.INDEX_FILE = self._orig_index_file
        self._tmp_dir.cleanup()

    def test_save_and_summary_include_execution_duration_and_cost(self):
        benchmark_result = {
            "run_id": "run-1",
            "target_model": "gpt-5.1",
            "judge_models": ["judge-a", "judge-b"],
            "judge_runs": 3,
            "executed_at": "2026-04-03T01:23:45Z",
            "execution_duration_ms": 12345,
            "estimated_cost_usd": 0.0123,
            "cost_estimate_status": "partial",
            "strict_mode": {
                "version": "v2",
                "requested": True,
                "enforced": True,
                "eligible": True,
                "preset_id": "official-v1",
                "preset_label": "Official Strict v1",
                "profile_id": "strict-profile-1",
                "profile_label": "1 tasks · 2 judges · runs x3 · temp 0.60",
            },
            "tasks": [
                {
                    "task_name": "01",
                    "task_type": "fact",
                    "input_prompt": "prompt",
                    "response": "response",
                    "subject_usage": {
                        "provider": "openrouter",
                        "model": "gpt-5.1",
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "total_tokens": 150,
                    },
                    "judge_results": {
                        "judge-a": {"aggregated": {"total_score_mean": 80}},
                        "judge-b": {"aggregated": {"total_score_mean": 70}},
                    },
                }
            ],
        }

        saved_path = ResultStorage.save(benchmark_result)
        loaded = ResultStorage.load(saved_path)
        summaries = ResultStorage.list_summaries()
        saved_summary = next(
            summary for summary in summaries if summary["filename"] == saved_path.name
        )

        self.assertEqual(loaded["execution_duration_ms"], 12345)
        self.assertEqual(loaded["estimated_cost_usd"], 0.0123)
        self.assertEqual(saved_summary["execution_duration_ms"], 12345)
        self.assertEqual(saved_summary["estimated_cost_usd"], 0.0123)
        self.assertEqual(saved_summary["cost_estimate_status"], "partial")
        self.assertEqual(saved_summary["subject_total_tokens"], 150)
        self.assertIsNone(saved_summary["subject_estimated_cost_usd"])
        self.assertIsNone(saved_summary["subject_cost_per_1m_tokens_usd"])
        self.assertTrue(saved_summary["strict_mode_eligible"])
        self.assertTrue(saved_summary["strict_mode_requested"])
        self.assertTrue(saved_summary["strict_mode_enforced"])
        self.assertEqual(saved_summary["strict_mode_preset_id"], "official-v1")
        self.assertEqual(saved_summary["strict_mode_preset_label"], "Official Strict v1")
        self.assertEqual(saved_summary["strict_mode_profile_id"], "strict-profile-1")
        self.assertEqual(
            saved_summary["strict_mode_profile_label"],
            "1 tasks · 2 judges · runs x3 · temp 0.60",
        )

    def test_delete_removes_result_file_and_summary(self):
        benchmark_result = {
            "run_id": "run-delete",
            "target_model": "gpt-5.1",
            "judge_models": ["judge-a"],
            "tasks": [],
        }

        saved_path = ResultStorage.save(benchmark_result)
        self.assertTrue(saved_path.exists())

        deleted = ResultStorage.delete(saved_path)

        self.assertTrue(deleted)
        self.assertFalse(saved_path.exists())
        self.assertEqual(ResultStorage.list_summaries(), [])


if __name__ == "__main__":
    unittest.main()
