"""Tests for judge reliability exclusion (Core-Feat-43)."""

from __future__ import annotations

import unittest

from core.judge_reliability import (
    REASON_CRITICAL_FAIL,
    REASON_CROSS_JUDGE_DIVERGENCE,
    REASON_HIGH_VARIANCE,
    REASON_LOW_CONFIDENCE,
    collect_unreliable_judges,
    compute_score_aggregation,
)


def _agg(
    mean: float,
    *,
    std: float = 0.0,
    critical_fail: bool = False,
    low: int = 0,
) -> dict:
    return {
        "aggregated": {
            "total_score_mean": mean,
            "total_score_std": std,
            "critical_fail": critical_fail,
            "confidence_distribution": {"high": 1, "medium": 0, "low": low},
        }
    }


def _tasks_two_judges_stable() -> list:
    return [
        {
            "task_name": "01",
            "judge_results": {
                "judge-a": _agg(80.0, std=1.0),
                "judge-b": _agg(70.0, std=2.0),
            },
        },
        {
            "task_name": "02",
            "judge_results": {
                "judge-a": _agg(90.0, std=1.5),
                "judge-b": _agg(60.0, std=2.0),
            },
        },
    ]


class TestJudgeReliability(unittest.TestCase):
    def test_toggle_off_matches_all_judge_mean(self):
        tasks = _tasks_two_judges_stable()
        # (80+70+90+60)/4 = 75.0
        off = compute_score_aggregation(tasks, exclude_unreliable_judges=False)
        self.assertFalse(off["exclude_unreliable_judges"])
        self.assertEqual(off["average_score"], 75.0)
        self.assertEqual(off["best_score"], 90.0)
        self.assertEqual(off["score_aggregation"]["excluded_judges"], [])
        self.assertEqual(
            off["score_aggregation"]["average_score_before"],
            off["score_aggregation"]["average_score_after"],
        )

    def test_high_variance_excludes_lineage(self):
        tasks = [
            {
                "task_name": "01",
                "judge_results": {
                    "judge-stable": _agg(80.0, std=1.0),
                    "judge-noisy": _agg(70.0, std=5.1),
                },
            },
            {
                "task_name": "02",
                "judge_results": {
                    "judge-stable": _agg(90.0, std=1.0),
                    "judge-noisy": _agg(75.0, std=2.0),  # only task1 flagged → whole lineage
                },
            },
        ]
        flags = collect_unreliable_judges(tasks)
        self.assertIn(REASON_HIGH_VARIANCE, flags["judge-noisy"])
        self.assertNotIn("judge-stable", flags)

        on = compute_score_aggregation(tasks, exclude_unreliable_judges=True)
        # only stable: (80+90)/2 = 85.0
        self.assertEqual(on["average_score"], 85.0)
        excluded_ids = [e["judge_id"] for e in on["score_aggregation"]["excluded_judges"]]
        self.assertEqual(excluded_ids, ["judge-noisy"])

    def test_low_confidence_and_critical_fail(self):
        tasks = [
            {
                "task_name": "01",
                "judge_results": {
                    "judge-ok": _agg(80.0),
                    "judge-low": _agg(78.0, low=1),
                    "judge-cf": _agg(76.0, critical_fail=True),
                },
            }
        ]
        flags = collect_unreliable_judges(tasks)
        self.assertEqual(flags["judge-low"], [REASON_LOW_CONFIDENCE])
        self.assertEqual(flags["judge-cf"], [REASON_CRITICAL_FAIL])
        self.assertNotIn("judge-ok", flags)

        on = compute_score_aggregation(tasks, exclude_unreliable_judges=True)
        self.assertEqual(on["average_score"], 80.0)
        self.assertEqual(on["best_score"], 80.0)

    def test_cross_judge_divergence_flags_participants(self):
        tasks = [
            {
                "task_name": "01",
                "judge_results": {
                    "judge-high": _agg(90.0),
                    "judge-low": _agg(70.0),  # range 20 > 15
                },
            },
            {
                "task_name": "02",
                "judge_results": {
                    "judge-high": _agg(88.0),
                    "judge-low": _agg(86.0),  # tight; still excluded via task1
                },
            },
        ]
        flags = collect_unreliable_judges(tasks)
        self.assertIn(REASON_CROSS_JUDGE_DIVERGENCE, flags["judge-high"])
        self.assertIn(REASON_CROSS_JUDGE_DIVERGENCE, flags["judge-low"])

        on = compute_score_aggregation(tasks, exclude_unreliable_judges=True)
        self.assertIsNone(on["average_score"])
        self.assertIsNone(on["best_score"])
        self.assertTrue(on["score_aggregation"]["all_excluded"])

    def test_all_excluded_returns_null_not_zero(self):
        tasks = [
            {
                "task_name": "01",
                "judge_results": {
                    "judge-a": _agg(50.0, std=6.0),
                    "judge-b": _agg(40.0, critical_fail=True),
                },
            }
        ]
        on = compute_score_aggregation(tasks, exclude_unreliable_judges=True)
        self.assertIsNone(on["average_score"])
        self.assertIsNone(on["best_score"])
        self.assertTrue(on["score_aggregation"]["all_excluded"])
        self.assertNotEqual(on["average_score"], 0)
        self.assertEqual(on["score_aggregation"]["average_score_before"], 45.0)

    def test_empty_tasks_off_returns_zero(self):
        off = compute_score_aggregation([], exclude_unreliable_judges=False)
        self.assertEqual(off["average_score"], 0.0)
        self.assertEqual(off["best_score"], 0.0)

    def test_zero_score_is_included(self):
        """0 mean must not be dropped by truthiness (legacy bug avoided)."""
        tasks = [
            {
                "task_name": "01",
                "judge_results": {
                    "judge-a": _agg(0.0),
                    "judge-b": _agg(100.0),
                },
            }
        ]
        off = compute_score_aggregation(tasks, exclude_unreliable_judges=False)
        self.assertEqual(off["average_score"], 50.0)


if __name__ == "__main__":
    unittest.main()
