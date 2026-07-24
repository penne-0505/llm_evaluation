"""Unit tests for wall-clock progress ETA with history prior."""

from __future__ import annotations

import unittest

from core.progress_eta import (
    MEASURED_PRIOR_STRENGTH,
    compute_progress_eta,
    measured_blend_alpha,
)


NOW_MS = 1_753_315_200_000.0  # 2026-07-24T00:00:00Z approx fixed


def _summary(**overrides):
    base = {
        "target_model": "model-a",
        "task_count": 10,
        "judge_count": 2,
        "execution_duration_ms": 100_000,
        "executed_at": "2026-07-20T00:00:00+00:00",
    }
    base.update(overrides)
    return base


class ProgressEtaTests(unittest.TestCase):
    def test_measured_pace_not_task_timing(self):
        # Wall pace: elapsed/completed*remaining = 10000/2*3 = 15000
        eta = compute_progress_eta(
            completed_task_count=2,
            remaining_task_count=3,
            elapsed_ms=10_000,
            current_step=4,
            total_steps=10,
            history_summaries=[],
            subject_model="model-a",
            task_count=5,
            judge_count=2,
        )
        self.assertEqual(eta["eta_status"], "measured")
        self.assertEqual(eta["eta_ms"], 15_000)

    def test_history_when_no_completed(self):
        # L_hist=10*(1+2)=30; rate=100000/30; remaining_L=5*(30/10)=15
        # remaining_ms = rate * 15 = 100000/30 * 15 = 50000
        eta = compute_progress_eta(
            completed_task_count=0,
            remaining_task_count=5,
            elapsed_ms=0,
            current_step=0,
            total_steps=20,
            history_summaries=[_summary()],
            subject_model="model-a",
            task_count=10,
            judge_count=2,
            now_ms=NOW_MS,
        )
        self.assertEqual(eta["eta_status"], "history")
        self.assertEqual(eta["eta_ms"], 50_000)

    def test_step_fallback_without_history(self):
        eta = compute_progress_eta(
            completed_task_count=0,
            remaining_task_count=3,
            elapsed_ms=4_000,
            current_step=2,
            total_steps=8,
            history_summaries=[],
        )
        self.assertEqual(eta["eta_status"], "step_fallback")
        self.assertEqual(eta["eta_ms"], 12_000)

    def test_blend_weights_measured_heavily(self):
        self.assertAlmostEqual(measured_blend_alpha(1), 1 / (1 + MEASURED_PRIOR_STRENGTH))
        # Huge history remaining vs modest measured → still pulled toward measured
        eta = compute_progress_eta(
            completed_task_count=1,
            remaining_task_count=2,
            elapsed_ms=2_000,
            current_step=2,
            total_steps=10,
            history_summaries=[
                _summary(execution_duration_ms=1_000_000, task_count=2, judge_count=1)
            ],
            subject_model="model-a",
            task_count=3,
            judge_count=1,
            now_ms=NOW_MS,
        )
        measured = 2_000 / 1 * 2  # 4000
        # α(1)≈0.91 ≥ threshold → measured status; value still near pace
        self.assertEqual(eta["eta_status"], "measured")
        self.assertLess(eta["eta_ms"], measured * 2)
        self.assertGreater(eta["eta_ms"], measured * 0.5)

    def test_remaining_zero_returns_measured_zero(self):
        eta = compute_progress_eta(
            completed_task_count=3,
            remaining_task_count=0,
            elapsed_ms=9_000,
            current_step=10,
            total_steps=10,
        )
        self.assertEqual(eta["eta_status"], "measured")
        self.assertEqual(eta["eta_ms"], 0)

    def test_history_preferred_over_step_at_start(self):
        eta = compute_progress_eta(
            completed_task_count=0,
            remaining_task_count=4,
            elapsed_ms=1_000,
            current_step=1,
            total_steps=20,
            history_summaries=[_summary()],
            subject_model="model-a",
            task_count=10,
            judge_count=2,
            now_ms=NOW_MS,
        )
        self.assertEqual(eta["eta_status"], "history")
        self.assertNotEqual(eta["eta_status"], "step_fallback")


if __name__ == "__main__":
    unittest.main()
