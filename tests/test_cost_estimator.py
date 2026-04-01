"""usage サマリーと推定コストのテスト"""

import tempfile
import unittest
from pathlib import Path

from core.cost_estimator import summarize_benchmark_usage
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


if __name__ == "__main__":
    unittest.main()
