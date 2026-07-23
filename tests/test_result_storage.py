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

    def test_save_round_trip_preserves_task_timing(self):
        benchmark_result = {
            "run_id": "run-timing",
            "target_model": "gpt-5.1",
            "judge_models": ["judge-a"],
            "judge_runs": 1,
            "executed_at": "2026-07-23T01:00:00Z",
            "execution_duration_ms": 5000,
            "tasks": [
                {
                    "task_name": "01",
                    "task_type": "fact",
                    "input_prompt": "prompt",
                    "response": "response",
                    "subject_usage": {
                        "provider": "openrouter",
                        "model": "gpt-5.1",
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15,
                        "duration_ms": 1200,
                    },
                    "judge_results": {
                        "judge-a": {
                            "runs": [
                                {
                                    "usage": {
                                        "provider": "openrouter",
                                        "model": "judge-a",
                                        "duration_ms": 3400,
                                    }
                                }
                            ],
                            "aggregated": {"total_score_mean": 80},
                        }
                    },
                    "task_timing": {
                        "subject_duration_ms": 1200,
                        "judge_duration_ms": 3400,
                    },
                }
            ],
        }

        saved_path = ResultStorage.save(benchmark_result)
        loaded = ResultStorage.load(saved_path)
        self.assertEqual(
            loaded["tasks"][0]["task_timing"],
            {"subject_duration_ms": 1200, "judge_duration_ms": 3400},
        )

    def test_summary_includes_timing_summary_from_task_timing(self):
        """AC-001 / DEC-002: summary index に task_timing 合算が載る。"""
        benchmark_result = {
            "run_id": "run-timing-summary",
            "target_model": "gpt-5.1",
            "judge_models": ["judge-a"],
            "judge_runs": 1,
            "executed_at": "2026-07-23T02:00:00Z",
            # wall-clock intentionally larger than processing sum (parallel-like)
            "execution_duration_ms": 20_000,
            "tasks": [
                {
                    "task_name": "01",
                    "task_type": "fact",
                    "input_prompt": "prompt",
                    "response": "response",
                    "subject_usage": {
                        "provider": "openrouter",
                        "model": "gpt-5.1",
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15,
                        "duration_ms": 1000,
                    },
                    "judge_results": {
                        "judge-a": {
                            "runs": [
                                {
                                    "usage": {
                                        "provider": "openrouter",
                                        "model": "judge-a",
                                        "duration_ms": 2000,
                                    }
                                }
                            ],
                            "aggregated": {"total_score_mean": 80},
                        }
                    },
                    "task_timing": {
                        "subject_duration_ms": 1000,
                        "judge_duration_ms": 2000,
                    },
                },
                {
                    "task_name": "02",
                    "task_type": "fact",
                    "input_prompt": "prompt",
                    "response": "response",
                    "subject_usage": {
                        "provider": "openrouter",
                        "model": "gpt-5.1",
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15,
                        "duration_ms": 500,
                    },
                    "judge_results": {
                        "judge-a": {
                            "runs": [
                                {
                                    "usage": {
                                        "provider": "openrouter",
                                        "model": "judge-a",
                                        "duration_ms": 1500,
                                    }
                                }
                            ],
                            "aggregated": {"total_score_mean": 70},
                        }
                    },
                    "task_timing": {
                        "subject_duration_ms": 500,
                        "judge_duration_ms": 1500,
                    },
                },
            ],
        }

        saved_path = ResultStorage.save(benchmark_result)
        summaries = ResultStorage.list_summaries()
        saved_summary = next(
            summary for summary in summaries if summary["filename"] == saved_path.name
        )

        self.assertEqual(
            saved_summary["timing_summary"],
            {
                "subject_duration_ms": 1500,
                "judge_duration_ms": 3500,
                "total_duration_ms": 5000,
            },
        )
        self.assertGreater(
            saved_summary["execution_duration_ms"],
            saved_summary["timing_summary"]["total_duration_ms"],
        )

    def test_summary_timing_none_when_task_timing_missing(self):
        """AC-003: 旧 result は timing_summary=None（wall-clock を埋めない）。"""
        benchmark_result = {
            "run_id": "run-legacy-timing",
            "target_model": "gpt-5.1",
            "judge_models": ["judge-a"],
            "executed_at": "2026-07-23T03:00:00Z",
            "execution_duration_ms": 9999,
            "tasks": [
                {
                    "task_name": "01",
                    "task_type": "fact",
                    "input_prompt": "prompt",
                    "response": "response",
                    "judge_results": {
                        "judge-a": {"aggregated": {"total_score_mean": 80}},
                    },
                }
            ],
        }

        saved_path = ResultStorage.save(benchmark_result)
        summaries = ResultStorage.list_summaries()
        saved_summary = next(
            summary for summary in summaries if summary["filename"] == saved_path.name
        )
        self.assertIsNone(saved_summary["timing_summary"])
        self.assertEqual(saved_summary["execution_duration_ms"], 9999)

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

    def test_save_preserves_subject_runs_array(self):
        benchmark_result = {
            "run_id": "run-subject-multi",
            "target_model": "gpt-5.1",
            "judge_models": ["judge-a"],
            "judge_runs": 2,
            "subject_runs": 3,
            "tasks": [
                {
                    "task_name": "01",
                    "task_type": "fact",
                    "input_prompt": "prompt",
                    "response": "run-a",
                    "subject_run_count": 3,
                    "subject_runs": [
                        {
                            "run_index": 1,
                            "response": "run-a",
                            "subject_usage": {
                                "provider": "stub",
                                "model": "m",
                                "input_tokens": 10,
                                "output_tokens": 5,
                                "total_tokens": 15,
                            },
                            "tool_trace": [],
                            "error": None,
                        },
                        {
                            "run_index": 2,
                            "response": "run-b",
                            "subject_usage": {
                                "provider": "stub",
                                "model": "m",
                                "input_tokens": 11,
                                "output_tokens": 6,
                                "total_tokens": 17,
                            },
                            "tool_trace": [],
                            "error": None,
                        },
                        {
                            "run_index": 3,
                            "response": "[ERROR] fail",
                            "subject_usage": None,
                            "tool_trace": [],
                            "error": "fail",
                        },
                    ],
                    "subject_usage": {
                        "provider": "stub",
                        "model": "m",
                        "input_tokens": 21,
                        "output_tokens": 11,
                        "total_tokens": 32,
                    },
                    "judge_results": {
                        "judge-a": {"aggregated": {"total_score_mean": 80}},
                    },
                }
            ],
        }

        saved_path = ResultStorage.save(benchmark_result)
        loaded = ResultStorage.load(saved_path)
        task = loaded["tasks"][0]
        self.assertEqual(loaded["subject_runs"], 3)
        self.assertEqual(task["subject_run_count"], 3)
        self.assertEqual(len(task["subject_runs"]), 3)
        self.assertEqual(task["response"], "run-a")
        self.assertEqual(task["subject_runs"][2]["error"], "fail")

    def test_save_round_trip_preserves_exclude_unreliable_and_null_scores(self):
        """AC-005 / DEC-003/004: toggle + null hero scores round-trip."""
        benchmark_result = {
            "run_id": "run-exclude",
            "target_model": "gpt-5.1",
            "judge_models": ["judge-a", "judge-b"],
            "judge_runs": 1,
            "executed_at": "2026-07-23T03:00:00Z",
            "exclude_unreliable_judges": True,
            "average_score": None,
            "best_score": None,
            "score_aggregation": {
                "average_score_before": 45.0,
                "average_score_after": None,
                "best_score_before": 50.0,
                "best_score_after": None,
                "excluded_judges": [
                    {"judge_id": "judge-a", "reasons": ["high_variance"]},
                    {"judge_id": "judge-b", "reasons": ["critical_fail"]},
                ],
                "included_judges": [],
                "all_excluded": True,
                "unreliable_candidates": [],
            },
            "tasks": [
                {
                    "task_name": "01",
                    "task_type": "fact",
                    "input_prompt": "prompt",
                    "response": "response",
                    "judge_results": {
                        "judge-a": {
                            "aggregated": {
                                "total_score_mean": 50,
                                "total_score_std": 6,
                                "critical_fail": False,
                                "confidence_distribution": {
                                    "high": 0,
                                    "medium": 0,
                                    "low": 0,
                                },
                            }
                        },
                        "judge-b": {
                            "aggregated": {
                                "total_score_mean": 40,
                                "total_score_std": 1,
                                "critical_fail": True,
                                "confidence_distribution": {
                                    "high": 0,
                                    "medium": 0,
                                    "low": 0,
                                },
                            }
                        },
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

        self.assertTrue(loaded["exclude_unreliable_judges"])
        self.assertIsNone(loaded["average_score"])
        self.assertIsNone(loaded["best_score"])
        self.assertTrue(loaded["score_aggregation"]["all_excluded"])
        self.assertTrue(saved_summary["exclude_unreliable_judges"])
        self.assertIsNone(saved_summary["avg_score"])
        self.assertIsNone(saved_summary["max_score"])


if __name__ == "__main__":
    unittest.main()
