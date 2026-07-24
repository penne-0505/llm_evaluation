"""Progress ETA: wall-clock remaining with history prior.

intent: DEC-002 (Core/task-duration-eta) — wait remaining is canonical;
in-run pace dominates; history is a weak similarity-weighted prior (SSE).
"""

from __future__ import annotations

import math
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

# Mirrors `_docs/reference/UI/pre-run-estimate/reference.md` wall channel.
WEIGHT_ALPHA = 0.35
WEIGHT_GAMMA = 0.1
WEIGHT_HALF_LIFE_DAYS = 90.0
WEIGHT_LAMBDA = math.log(2) / WEIGHT_HALF_LIFE_DAYS

# Measured pace weight: α(n) = n / (n + MEASURED_PRIOR_STRENGTH).
# n=1 → ≈0.91, n=2 → ≈0.95 — measured quite heavy.
MEASURED_PRIOR_STRENGTH = 0.1
# Treat as measured-dominated for status labeling.
MEASURED_STATUS_THRESHOLD = 0.9
# When blending, clamp history prior into this factor band around measured
# so extreme unit-rate outliers cannot dominate the wait estimate.
HISTORY_BLEND_CLAMP_FACTOR = 4.0


def planned_load(
    task_count: int,
    judge_count: int,
    subject_run_count: int = 1,
    judge_run_count: int = 1,
) -> float:
    tasks = max(0, int(task_count or 0))
    judges = max(1, int(judge_count or 1))
    subject_runs = max(1, int(subject_run_count or 1))
    judge_runs = max(1, int(judge_run_count or 1))
    return float(tasks * (subject_runs + judges * judge_runs))


def historical_load(task_count: int, judge_count: int) -> float:
    tasks = max(0, int(task_count or 0))
    judges = max(1, int(judge_count or 1))
    return float(tasks * (1 + judges))


def match_distance(
    hist_task_count: int,
    hist_judge_count: int,
    task_count: int,
    judge_count: int,
) -> float:
    d_tasks = abs(int(hist_task_count or 0) - int(task_count or 0))
    d_judges = abs(int(hist_judge_count or 0) - max(1, int(judge_count or 1)))
    return float(d_tasks + 2 * d_judges)


def age_days(timestamp: Optional[str], now_ms: float) -> float:
    if not timestamp:
        return 0.0
    try:
        ts = str(timestamp).replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        t_ms = dt.timestamp() * 1000.0
    except (TypeError, ValueError, OSError):
        return 0.0
    return max(0.0, (now_ms - t_ms) / (1000.0 * 60.0 * 60.0 * 24.0))


def subject_matches(summary: Dict[str, Any], subject_model: str) -> bool:
    target = (subject_model or "").strip()
    if not target:
        return False
    return str(summary.get("target_model") or "") == target


def wall_channel_weight(*, subject_match: bool, distance: float, age: float) -> float:
    gate = 1.0 if subject_match else WEIGHT_GAMMA
    if gate <= 0:
        return 0.0
    return gate * math.exp(-WEIGHT_ALPHA * distance) * math.exp(-WEIGHT_LAMBDA * age)


def measured_blend_alpha(completed_task_count: int) -> float:
    n = max(0, int(completed_task_count or 0))
    if n <= 0:
        return 0.0
    return n / (n + MEASURED_PRIOR_STRENGTH)


def measured_remaining_ms(
    *,
    elapsed_ms: int,
    completed_task_count: int,
    remaining_task_count: int,
) -> Optional[int]:
    completed = int(completed_task_count or 0)
    remaining = int(remaining_task_count or 0)
    elapsed = int(elapsed_ms or 0)
    if remaining <= 0:
        return 0
    if completed <= 0 or elapsed <= 0:
        return None
    return int((elapsed / completed) * remaining)


def history_wall_remaining_ms(
    summaries: List[Dict[str, Any]],
    *,
    subject_model: str,
    task_count: int,
    judge_count: int,
    subject_run_count: int,
    judge_run_count: int,
    remaining_task_count: int,
    now_ms: Optional[float] = None,
) -> Optional[int]:
    """Similarity-weighted wall unit rate × remaining load (pre-run wall channel)."""
    remaining = int(remaining_task_count or 0)
    if remaining <= 0:
        return 0
    tasks = int(task_count or 0)
    if tasks <= 0:
        return None

    l_plan = planned_load(task_count, judge_count, subject_run_count, judge_run_count)
    load_per_task = l_plan / tasks
    remaining_l = remaining * load_per_task
    if remaining_l <= 0:
        return None

    clock = float(now_ms if now_ms is not None else time.time() * 1000.0)
    sum_w = 0.0
    sum_wr = 0.0
    for summary in summaries:
        if not isinstance(summary, dict):
            continue
        duration = summary.get("execution_duration_ms")
        if duration is None:
            continue
        try:
            duration_f = float(duration)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(duration_f) or duration_f <= 0:
            continue
        hist_tasks = int(summary.get("task_count") or 0)
        hist_judges = int(summary.get("judge_count") or 0)
        l_hist = historical_load(hist_tasks, hist_judges)
        if l_hist <= 0:
            continue
        match = subject_matches(summary, subject_model)
        dist = match_distance(hist_tasks, hist_judges, task_count, judge_count)
        age = age_days(summary.get("executed_at"), clock)
        weight = wall_channel_weight(subject_match=match, distance=dist, age=age)
        if weight <= 0:
            continue
        rate = duration_f / l_hist
        sum_w += weight
        sum_wr += weight * rate

    if sum_w <= 0:
        return None
    return max(0, int((sum_wr / sum_w) * remaining_l))


def step_fallback_remaining_ms(
    *,
    elapsed_ms: int,
    current_step: int,
    total_steps: int,
) -> Optional[int]:
    elapsed = int(elapsed_ms or 0)
    current = int(current_step or 0)
    total = int(total_steps or 0)
    if current <= 0 or total <= current or elapsed <= 0:
        return None
    remaining_steps = total - current
    return int((elapsed / current) * remaining_steps)


def compute_progress_eta(
    *,
    completed_task_count: int,
    remaining_task_count: int,
    elapsed_ms: int,
    current_step: int,
    total_steps: int,
    history_summaries: Optional[List[Dict[str, Any]]] = None,
    subject_model: str = "",
    task_count: int = 0,
    judge_count: int = 0,
    subject_run_count: int = 1,
    judge_run_count: int = 1,
    now_ms: Optional[float] = None,
) -> Dict[str, Any]:
    """Return ``{eta_ms, eta_status}`` for SSE progress.

    Status vocabulary:
    - ``measured`` — in-run wall pace dominates (or sole signal)
    - ``history_blend`` — measured + history prior mixed
    - ``history`` — history prior only
    - ``step_fallback`` — step ratio only
    - ``unavailable`` — no estimate
    """
    remaining = int(remaining_task_count or 0)
    completed = int(completed_task_count or 0)

    if remaining <= 0:
        return {"eta_ms": 0, "eta_status": "measured"}

    measured = measured_remaining_ms(
        elapsed_ms=elapsed_ms,
        completed_task_count=completed,
        remaining_task_count=remaining,
    )
    effective_task_count = task_count if task_count > 0 else max(completed + remaining, 1)
    history = history_wall_remaining_ms(
        list(history_summaries or []),
        subject_model=subject_model,
        task_count=effective_task_count,
        judge_count=judge_count,
        subject_run_count=subject_run_count,
        judge_run_count=judge_run_count,
        remaining_task_count=remaining,
        now_ms=now_ms,
    )

    if measured is not None and history is not None:
        alpha = measured_blend_alpha(completed)
        # intent: DEC-002 — measured dominates; clamp runaway history unit rates
        factor = HISTORY_BLEND_CLAMP_FACTOR
        lo = measured / factor
        hi = measured * factor
        history_clamped = min(max(history, int(lo)), int(hi))
        eta = int(alpha * measured + (1.0 - alpha) * history_clamped)
        status = "measured" if alpha >= MEASURED_STATUS_THRESHOLD else "history_blend"
        return {"eta_ms": max(0, eta), "eta_status": status}

    if measured is not None:
        return {"eta_ms": max(0, measured), "eta_status": "measured"}

    if history is not None:
        return {"eta_ms": max(0, history), "eta_status": "history"}

    step = step_fallback_remaining_ms(
        elapsed_ms=elapsed_ms,
        current_step=current_step,
        total_steps=total_steps,
    )
    if step is not None:
        return {"eta_ms": max(0, step), "eta_status": "step_fallback"}

    return {"eta_ms": None, "eta_status": "unavailable"}
