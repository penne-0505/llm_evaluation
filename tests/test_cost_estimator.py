"""usage サマリーと推定コストのテスト"""

import json
import tempfile
import unittest
from pathlib import Path

from core.cost_estimator import (
    summarize_benchmark_usage,
    summarize_judge_usage,
    summarize_subject_usage,
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

    def test_summarize_benchmark_usage_estimates_openai_cost_via_openrouter_catalog(self):
        """OpenAI 直接接続でも OpenRouter カタログをフォールバックして価格推定できる"""
        # OpenRouter カタログに openai/gpt-5.4 の価格情報を追加
        cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        cache["providers"]["openrouter"]["models"].append("openrouter/openai/gpt-5.4")
        cache["providers"]["openrouter"]["entries"].append(
            {
                "id": "openrouter/openai/gpt-5.4",
                "pricing": {"prompt": "0.000005", "completion": "0.000015"},
            }
        )
        self.cache_path.write_text(json.dumps(cache), encoding="utf-8")

        tasks = [
            {
                "subject_usage": {
                    "provider": "openai",
                    "model": "gpt-5.4",
                    "input_tokens": 2000,
                    "output_tokens": 1000,
                    "total_tokens": 3000,
                },
                "judge_results": {},
            }
        ]

        summary = summarize_benchmark_usage(tasks)

        self.assertEqual(summary["totals"]["call_count"], 1)
        self.assertEqual(summary["totals"]["input_tokens"], 2000)
        self.assertEqual(summary["totals"]["output_tokens"], 1000)
        self.assertEqual(summary["totals"]["pricing_status"], "available")
        # (2000 * 0.000005) + (1000 * 0.000015) = 0.01 + 0.015 = 0.025
        self.assertAlmostEqual(summary["totals"]["estimated_cost_usd"], 0.025, places=8)

    def test_summarize_benchmark_usage_estimates_gemini_cost_via_openrouter_catalog(self):
        """Gemini 直接接続でも OpenRouter カタログ（google/...）をフォールバックして価格推定できる"""
        cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        cache["providers"]["openrouter"]["models"].append("openrouter/google/gemini-1.5-pro")
        cache["providers"]["openrouter"]["entries"].append(
            {
                "id": "openrouter/google/gemini-1.5-pro",
                "pricing": {"prompt": "0.000001", "completion": "0.000002"},
            }
        )
        self.cache_path.write_text(json.dumps(cache), encoding="utf-8")

        tasks = [
            {
                "subject_usage": {
                    "provider": "gemini",
                    "model": "gemini-1.5-pro",
                    "input_tokens": 3000,
                    "output_tokens": 1500,
                    "total_tokens": 4500,
                },
                "judge_results": {},
            }
        ]

        summary = summarize_benchmark_usage(tasks)

        self.assertEqual(summary["totals"]["call_count"], 1)
        self.assertEqual(summary["totals"]["pricing_status"], "available")
        # (3000 * 0.000001) + (1500 * 0.000002) = 0.003 + 0.003 = 0.006
        self.assertAlmostEqual(summary["totals"]["estimated_cost_usd"], 0.006, places=8)

    def test_summarize_benchmark_usage_openai_model_unpriced_fallback_fails(self):
        """OpenRouter カタログに存在しないモデルは価格未設定となる"""
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


if __name__ == "__main__":
    unittest.main()
