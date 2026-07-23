"""usage サマリーと推定コストのテスト"""

import json
import tempfile
import unittest
from pathlib import Path

from core.cost_estimator import (
    summarize_benchmark_usage,
    summarize_judge_usage,
    summarize_subject_usage,
    summarize_task_timing,
)
from core.model_catalog import ModelCatalog


class TestCostEstimator(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.cache_path = Path(self._tmp_dir.name) / "models.json"
        self._orig_cache_path = ModelCatalog.CACHE_PATH
        ModelCatalog.CACHE_PATH = self.cache_path
        self.cache_path.write_text(
            """
{
  "updated_at": "2026-04-03T00:00:00Z",
  "providers": {
    "openrouter": {
      "models": ["openrouter/google/gemma-4-31b-it"],
      "entries": [
        {
          "id": "openrouter/google/gemma-4-31b-it",
          "pricing": {
            "prompt": "0.0000002",
            "completion": "0.0000008"
          }
        }
      ]
    }
  }
}
            """.strip(),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        ModelCatalog.CACHE_PATH = self._orig_cache_path
        self._tmp_dir.cleanup()

    def test_summarize_benchmark_usage_estimates_openrouter_cost(self):
        tasks = [
            {
                "subject_usage": {
                    "provider": "openrouter",
                    "model": "openrouter/google/gemma-4-31b-it",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "total_tokens": 1500,
                },
                "judge_results": {
                    "judge-a": {
                        "runs": [
                            {
                                "usage": {
                                    "provider": "openrouter",
                                    "model": "openrouter/google/gemma-4-31b-it",
                                    "input_tokens": 250,
                                    "output_tokens": 250,
                                    "total_tokens": 500,
                                }
                            }
                        ]
                    }
                },
            }
        ]

        summary = summarize_benchmark_usage(tasks)

        self.assertEqual(summary["totals"]["call_count"], 2)
        self.assertEqual(summary["totals"]["input_tokens"], 1250)
        self.assertEqual(summary["totals"]["output_tokens"], 750)
        self.assertEqual(summary["totals"]["pricing_status"], "available")
        self.assertAlmostEqual(summary["totals"]["estimated_cost_usd"], 0.00085, places=8)

    def test_summarize_benchmark_usage_estimates_openai_cost_via_static_table(self):
        """OpenAI profile は静的表で推定する（AC-007）。"""
        tasks = [
            {
                "subject_usage": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "input_tokens": 2_000_000,
                    "output_tokens": 1_000_000,
                    "total_tokens": 3_000_000,
                },
                "judge_results": {},
            }
        ]

        summary = summarize_benchmark_usage(tasks)

        self.assertEqual(summary["totals"]["call_count"], 1)
        self.assertEqual(summary["totals"]["pricing_status"], "available")
        # gpt-4o: $2.5 / $10 per 1M → 2*2.5 + 1*10 = 15.0
        self.assertAlmostEqual(summary["totals"]["estimated_cost_usd"], 15.0, places=8)
        self.assertEqual(summary["calls"][0]["pricing_source"], "openai_static")

    def test_summarize_benchmark_usage_estimates_google_cost_via_static_table(self):
        """google-ai-studio / gemini は google 静的表で推定する。"""
        tasks = [
            {
                "subject_usage": {
                    "provider": "google-ai-studio",
                    "model": "gemini-1.5-pro",
                    "input_tokens": 1_000_000,
                    "output_tokens": 1_000_000,
                    "total_tokens": 2_000_000,
                },
                "judge_results": {},
            }
        ]

        summary = summarize_benchmark_usage(tasks)

        self.assertEqual(summary["totals"]["call_count"], 1)
        self.assertEqual(summary["totals"]["pricing_status"], "available")
        # $1.25 + $5.0 per 1M
        self.assertAlmostEqual(summary["totals"]["estimated_cost_usd"], 6.25, places=8)
        self.assertEqual(summary["calls"][0]["pricing_source"], "google_static")

    def test_inv001_openai_profile_ignores_openrouter_catalog(self):
        """INV-001: 公式 profile は OR カタログに同名があっても openrouter_catalog を使わない。"""
        cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        cache["providers"]["openrouter"]["models"].append("openrouter/openai/mystery-model")
        cache["providers"]["openrouter"]["entries"].append(
            {
                "id": "openrouter/openai/mystery-model",
                "pricing": {"prompt": "0.000005", "completion": "0.000015"},
            }
        )
        self.cache_path.write_text(json.dumps(cache), encoding="utf-8")

        tasks = [
            {
                "subject_usage": {
                    "provider": "openai",
                    "model": "mystery-model",
                    "input_tokens": 2000,
                    "output_tokens": 1000,
                    "total_tokens": 3000,
                },
                "judge_results": {},
            }
        ]

        summary = summarize_benchmark_usage(tasks)
        self.assertEqual(summary["totals"]["pricing_status"], "unavailable")
        self.assertIsNone(summary["totals"]["estimated_cost_usd"])
        self.assertIn("openai:mystery-model", summary["totals"]["unpriced_models"])

    def test_summarize_benchmark_usage_openai_model_unpriced_fallback_fails(self):
        """静的表に無い OpenAI モデルは価格未設定となる"""
        tasks = [
            {
                "subject_usage": {
                    "provider": "openai",
                    "model": "unknown-model",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "total_tokens": 1500,
                },
                "judge_results": {},
            }
        ]

        summary = summarize_benchmark_usage(tasks)

        self.assertEqual(summary["totals"]["call_count"], 1)
        self.assertEqual(summary["totals"]["pricing_status"], "unavailable")
        self.assertIsNone(summary["totals"]["estimated_cost_usd"])
        self.assertIn("openai:unknown-model", summary["totals"]["unpriced_models"])

    def test_summarize_subject_usage_isolates_subject_calls(self):
        """summarize_subject_usage は被検モデルの usage のみを集計する"""
        tasks = [
            {
                "subject_usage": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "total_tokens": 1500,
                },
                "judge_results": {
                    "judge-a": {
                        "runs": [
                            {
                                "usage": {
                                    "provider": "anthropic",
                                    "model": "claude-3",
                                    "input_tokens": 200,
                                    "output_tokens": 100,
                                    "total_tokens": 300,
                                }
                            }
                        ]
                    }
                },
            }
        ]

        subject_summary = summarize_subject_usage(tasks)
        self.assertEqual(subject_summary["totals"]["call_count"], 1)
        self.assertEqual(subject_summary["totals"]["input_tokens"], 1000)
        self.assertEqual(subject_summary["totals"]["output_tokens"], 500)
        self.assertEqual(len(subject_summary["calls"]), 1)
        self.assertEqual(subject_summary["calls"][0]["provider"], "openai")

    def test_summarize_subject_usage_prefers_subject_runs_array(self):
        tasks = [
            {
                "subject_usage": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "input_tokens": 999,
                    "output_tokens": 999,
                    "total_tokens": 1998,
                },
                "subject_runs": [
                    {
                        "run_index": 1,
                        "subject_usage": {
                            "provider": "openai",
                            "model": "gpt-4o",
                            "input_tokens": 100,
                            "output_tokens": 50,
                            "total_tokens": 150,
                        },
                    },
                    {
                        "run_index": 2,
                        "subject_usage": {
                            "provider": "openai",
                            "model": "gpt-4o",
                            "input_tokens": 200,
                            "output_tokens": 80,
                            "total_tokens": 280,
                        },
                    },
                ],
                "judge_results": {},
            }
        ]
        subject_summary = summarize_subject_usage(tasks)
        self.assertEqual(subject_summary["totals"]["call_count"], 2)
        self.assertEqual(subject_summary["totals"]["input_tokens"], 300)
        self.assertEqual(subject_summary["totals"]["output_tokens"], 130)

    def test_summarize_judge_usage_isolates_judge_calls(self):
        """summarize_judge_usage は judge モデルの usage のみを集計する"""
        tasks = [
            {
                "subject_usage": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "total_tokens": 1500,
                },
                "judge_results": {
                    "judge-a": {
                        "runs": [
                            {
                                "usage": {
                                    "provider": "anthropic",
                                    "model": "claude-3",
                                    "input_tokens": 200,
                                    "output_tokens": 100,
                                    "total_tokens": 300,
                                }
                            },
                            {
                                "usage": {
                                    "provider": "anthropic",
                                    "model": "claude-3",
                                    "input_tokens": 200,
                                    "output_tokens": 100,
                                    "total_tokens": 300,
                                }
                            },
                        ]
                    },
                    "judge-b": {
                        "runs": [
                            {
                                "usage": {
                                    "provider": "openai",
                                    "model": "gpt-4o-mini",
                                    "input_tokens": 150,
                                    "output_tokens": 50,
                                    "total_tokens": 200,
                                }
                            }
                        ]
                    },
                },
            }
        ]

        judge_summary = summarize_judge_usage(tasks)
        self.assertEqual(judge_summary["totals"]["call_count"], 3)
        self.assertEqual(judge_summary["totals"]["input_tokens"], 550)
        self.assertEqual(judge_summary["totals"]["output_tokens"], 250)
        self.assertEqual(len(judge_summary["calls"]), 2)

    def test_summarize_subject_and_judge_sum_to_total(self):
        """subject + judge = total となる"""
        tasks = [
            {
                "subject_usage": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "total_tokens": 1500,
                },
                "judge_results": {
                    "judge-a": {
                        "runs": [
                            {
                                "usage": {
                                    "provider": "anthropic",
                                    "model": "claude-3",
                                    "input_tokens": 200,
                                    "output_tokens": 100,
                                    "total_tokens": 300,
                                }
                            }
                        ]
                    }
                },
            }
        ]

        total = summarize_benchmark_usage(tasks)
        subject = summarize_subject_usage(tasks)
        judge = summarize_judge_usage(tasks)

        self.assertEqual(
            total["totals"]["input_tokens"],
            subject["totals"]["input_tokens"] + judge["totals"]["input_tokens"],
        )
        self.assertEqual(
            total["totals"]["output_tokens"],
            subject["totals"]["output_tokens"] + judge["totals"]["output_tokens"],
        )
        self.assertEqual(
            total["totals"]["call_count"],
            subject["totals"]["call_count"] + judge["totals"]["call_count"],
        )

    def test_task_timing_matches_usage_total_duration(self):
        from core.benchmark_engine import TaskResult

        tasks = [
            {
                "subject_usage": {
                    "provider": "openai",
                    "model": "gpt-4o",
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
                                    "provider": "anthropic",
                                    "model": "claude-3",
                                    "input_tokens": 20,
                                    "output_tokens": 10,
                                    "total_tokens": 30,
                                    "duration_ms": 800,
                                }
                            },
                            {
                                "usage": {
                                    "provider": "anthropic",
                                    "model": "claude-3",
                                    "input_tokens": 20,
                                    "output_tokens": 10,
                                    "total_tokens": 30,
                                    "duration_ms": 700,
                                }
                            },
                        ]
                    }
                },
            }
        ]
        timing = TaskResult.build_task_timing(
            tasks[0]["subject_usage"], tasks[0]["judge_results"]
        )
        summary = summarize_benchmark_usage(tasks)
        self.assertEqual(
            timing["subject_duration_ms"] + timing["judge_duration_ms"],
            summary["totals"]["total_duration_ms"],
        )

    def test_summarize_task_timing_matches_usage_and_rejects_partial(self):
        """AC-004: timing_summary と usage total_duration_ms が一致する。"""
        tasks = [
            {
                "subject_usage": {
                    "provider": "openai",
                    "model": "gpt-4o",
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
                                    "provider": "anthropic",
                                    "model": "claude-3",
                                    "input_tokens": 20,
                                    "output_tokens": 10,
                                    "total_tokens": 30,
                                    "duration_ms": 2000,
                                }
                            }
                        ]
                    }
                },
                "task_timing": {
                    "subject_duration_ms": 1000,
                    "judge_duration_ms": 2000,
                },
            },
            {
                "subject_usage": {
                    "provider": "openai",
                    "model": "gpt-4o",
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
                                    "provider": "anthropic",
                                    "model": "claude-3",
                                    "input_tokens": 20,
                                    "output_tokens": 10,
                                    "total_tokens": 30,
                                    "duration_ms": 1500,
                                }
                            }
                        ]
                    }
                },
                "task_timing": {
                    "subject_duration_ms": 500,
                    "judge_duration_ms": 1500,
                },
            },
        ]

        timing_summary = summarize_task_timing(tasks)
        usage_summary = summarize_benchmark_usage(tasks)
        self.assertEqual(
            timing_summary,
            {
                "subject_duration_ms": 1500,
                "judge_duration_ms": 3500,
                "total_duration_ms": 5000,
            },
        )
        self.assertEqual(
            timing_summary["total_duration_ms"],
            usage_summary["totals"]["total_duration_ms"],
        )

        partial = [tasks[0], {**tasks[1], "task_timing": None}]
        self.assertIsNone(summarize_task_timing(partial))


if __name__ == "__main__":
    unittest.main()
