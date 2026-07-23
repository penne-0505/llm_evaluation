"""Judge reliability thresholds and hero-score aggregation.

intent: DEC-002 (Core/exclude-unreliable-judges) — single module for exclusion
criteria and reason codes; frontend maps codes to labels only (INV-002).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

# intent: DEC-002 — thresholds fixed here; do not scatter magic numbers
HIGH_VARIANCE_STD_THRESHOLD = 5.0
CROSS_JUDGE_DIVERGENCE_RANGE_THRESHOLD = 15.0

REASON_HIGH_VARIANCE = "high_variance"
REASON_LOW_CONFIDENCE = "low_confidence"
REASON_CRITICAL_FAIL = "critical_fail"
REASON_CROSS_JUDGE_DIVERGENCE = "cross_judge_divergence"

REASON_CODES = (
    REASON_HIGH_VARIANCE,
    REASON_LOW_CONFIDENCE,
    REASON_CRITICAL_FAIL,
    REASON_CROSS_JUDGE_DIVERGENCE,
)


def _as_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _task_judge_means(
    task: Mapping[str, Any],
) -> List[Tuple[str, float, Mapping[str, Any]]]:
    """Return (judge_id, total_score_mean, aggregated) for judges with aggregated data."""
    rows: List[Tuple[str, float, Mapping[str, Any]]] = []
    judge_results = task.get("judge_results") or {}
    if not isinstance(judge_results, Mapping):
        return rows
    for judge_id, result in judge_results.items():
        if not isinstance(result, Mapping):
            continue
        agg = result.get("aggregated")
        if not isinstance(agg, Mapping):
            continue
        mean = _as_float(agg.get("total_score_mean"))
        if mean is None:
            continue
        rows.append((str(judge_id), mean, agg))
    return rows


def collect_unreliable_judges(
    tasks: Sequence[Mapping[str, Any]],
) -> Dict[str, List[str]]:
    """Map judge lineage → unique reason codes (DEC-001/002).

    A lineage is flagged if any task×judge cell matches a criterion, or if it
    participates in a task whose judge-mean range exceeds the divergence threshold.
    """
    reasons: Dict[str, Set[str]] = {}

    def add(judge_id: str, code: str) -> None:
        reasons.setdefault(judge_id, set()).add(code)

    for task in tasks:
        rows = _task_judge_means(task)
        for judge_id, _mean, agg in rows:
            std = _as_float(agg.get("total_score_std")) or 0.0
            if std > HIGH_VARIANCE_STD_THRESHOLD:
                add(judge_id, REASON_HIGH_VARIANCE)

            conf = agg.get("confidence_distribution") or {}
            if isinstance(conf, Mapping) and int(conf.get("low") or 0) > 0:
                add(judge_id, REASON_LOW_CONFIDENCE)

            if bool(agg.get("critical_fail")):
                add(judge_id, REASON_CRITICAL_FAIL)

        if len(rows) >= 2:
            means = [mean for _jid, mean, _agg in rows]
            if max(means) - min(means) > CROSS_JUDGE_DIVERGENCE_RANGE_THRESHOLD:
                for judge_id, _mean, _agg in rows:
                    add(judge_id, REASON_CROSS_JUDGE_DIVERGENCE)

    ordered: Dict[str, List[str]] = {}
    for judge_id in sorted(reasons):
        codes = reasons[judge_id]
        ordered[judge_id] = [code for code in REASON_CODES if code in codes]
    return ordered


def collect_total_scores(
    tasks: Sequence[Mapping[str, Any]],
    *,
    excluded_judges: Optional[Iterable[str]] = None,
) -> List[float]:
    """Collect per task×judge total_score_mean values (0 is kept; missing skipped)."""
    excluded: Set[str] = set(excluded_judges or ())
    scores: List[float] = []
    for task in tasks:
        for judge_id, mean, _agg in _task_judge_means(task):
            if judge_id in excluded:
                continue
            scores.append(mean)
    return scores


def _round_score(value: float) -> float:
    return round(value, 1)


def _hero_from_scores(
    scores: Sequence[float],
    *,
    empty_as_null: bool,
) -> Tuple[Optional[float], Optional[float]]:
    # intent-invariant: INV-001 — empty under exclude-ON must be null, never 0
    if not scores:
        if empty_as_null:
            return None, None
        return 0.0, 0.0
    average = _round_score(sum(scores) / len(scores))
    best = _round_score(max(scores))
    return average, best


def compute_score_aggregation(
    tasks: Sequence[Mapping[str, Any]],
    *,
    exclude_unreliable_judges: bool = False,
) -> Dict[str, Any]:
    """Compute hero scores and exclusion metadata for a completed-tasks list.

    When ``exclude_unreliable_judges`` is False, average/best match the legacy
    all-judge average (empty → 0). When True and no included scores remain,
    average/best are null (DEC-004 / INV-001).
    """
    unreliable = collect_unreliable_judges(tasks)
    excluded_ids = set(unreliable) if exclude_unreliable_judges else set()

    before_scores = collect_total_scores(tasks)
    after_scores = collect_total_scores(tasks, excluded_judges=excluded_ids)

    average_before, best_before = _hero_from_scores(before_scores, empty_as_null=False)
    average_after, best_after = _hero_from_scores(
        after_scores,
        empty_as_null=exclude_unreliable_judges,
    )

    all_judge_ids: Set[str] = set()
    for task in tasks:
        for judge_id, _mean, _agg in _task_judge_means(task):
            all_judge_ids.add(judge_id)

    included = sorted(all_judge_ids - excluded_ids)
    all_excluded = bool(exclude_unreliable_judges and all_judge_ids and not included)

    if exclude_unreliable_judges:
        average_score, best_score = average_after, best_after
    else:
        average_score, best_score = average_before, best_before

    return {
        "exclude_unreliable_judges": bool(exclude_unreliable_judges),
        "average_score": average_score,
        "best_score": best_score,
        "score_aggregation": {
            "average_score_before": average_before,
            "average_score_after": average_after if exclude_unreliable_judges else average_before,
            "best_score_before": best_before,
            "best_score_after": best_after if exclude_unreliable_judges else best_before,
            "excluded_judges": [
                {"judge_id": judge_id, "reasons": list(unreliable[judge_id])}
                for judge_id in sorted(excluded_ids)
            ],
            "included_judges": included,
            "all_excluded": all_excluded,
            # Candidates always listed so UI can explain OFF vs would-be exclusions
            "unreliable_candidates": [
                {"judge_id": judge_id, "reasons": codes}
                for judge_id, codes in unreliable.items()
            ],
        },
    }
