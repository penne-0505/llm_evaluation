"""usage 集計と推定コスト計算"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.model_catalog import ModelCatalog


def summarize_benchmark_usage(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """保存済み task 結果から usage サマリーを構築する。"""
    usage_records: List[Dict[str, Any]] = []

    for task in tasks:
        subject_usage = task.get("subject_usage")
        if isinstance(subject_usage, dict):
            usage_records.append(subject_usage)

        for judge_result in task.get("judge_results", {}).values():
            for run in judge_result.get("runs", []):
                usage = run.get("usage")
                if isinstance(usage, dict):
                    usage_records.append(usage)

    return summarize_usage_records(usage_records)


def summarize_usage_records(usage_records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """usage レコード群をモデル単位に集計し、価格が分かるものだけ推定コストを計算する。"""
    grouped: dict[Tuple[str, str], Dict[str, Any]] = {}
    totals = _empty_usage_totals()
    unpriced_models: set[str] = set()

    for usage in usage_records:
        provider = str(usage.get("provider") or "unknown")
        model = str(usage.get("model") or "unknown")
        key = (provider, model)

        if key not in grouped:
            grouped[key] = {
                "provider": provider,
                "model": model,
                "call_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "estimated_cost_usd": 0.0,
                "priced_call_count": 0,
                "unpriced_call_count": 0,
                "pricing_source": None,
            }

        group = grouped[key]
        group["call_count"] += 1
        totals["call_count"] += 1

        for token_key in (
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        ):
            value = _coerce_int(usage.get(token_key))
            group[token_key] += value
            totals[token_key] += value

        estimated_cost, pricing_source = estimate_usage_cost(usage)
        if estimated_cost is None:
            group["unpriced_call_count"] += 1
            totals["unpriced_call_count"] += 1
            unpriced_models.add(f"{provider}:{model}")
        else:
            group["estimated_cost_usd"] += estimated_cost
            group["priced_call_count"] += 1
            group["pricing_source"] = group["pricing_source"] or pricing_source
            totals["estimated_cost_usd"] += estimated_cost
            totals["priced_call_count"] += 1

    calls = []
    for item in sorted(grouped.values(), key=lambda row: (row["provider"], row["model"])):
        item["estimated_cost_usd"] = (
            round(item["estimated_cost_usd"], 8)
            if item["priced_call_count"] > 0
            else None
        )
        calls.append(item)

    pricing_status = "unavailable"
    if totals["priced_call_count"] > 0 and totals["unpriced_call_count"] == 0:
        pricing_status = "available"
    elif totals["priced_call_count"] > 0:
        pricing_status = "partial"

    totals["estimated_cost_usd"] = (
        round(totals["estimated_cost_usd"], 8)
        if totals["priced_call_count"] > 0
        else None
    )
    totals["pricing_status"] = pricing_status
    totals["unpriced_models"] = sorted(unpriced_models)

    return {
        "calls": calls,
        "totals": totals,
    }


def estimate_usage_cost(usage: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    """単一 usage レコードの推定コストを返す。価格不明なら None。"""
    provider = str(usage.get("provider") or "unknown")
    model = str(usage.get("model") or "unknown")
    pricing = _lookup_pricing(provider, model)
    if pricing is None:
        return None, None

    input_price, output_price, pricing_source = pricing
    input_tokens = _coerce_int(usage.get("input_tokens"))
    output_tokens = _coerce_int(usage.get("output_tokens"))

    estimated_cost = (input_tokens * input_price) + (output_tokens * output_price)
    return estimated_cost, pricing_source


def _lookup_pricing(
    provider: str, model: str
) -> Optional[Tuple[float, float, str]]:
    if provider != "openrouter":
        return None

    entry = ModelCatalog.find_model_entry(provider, model)
    if not entry:
        return None

    pricing = entry.get("pricing", {})
    prompt_price = _coerce_float(pricing.get("prompt"))
    completion_price = _coerce_float(pricing.get("completion"))
    if prompt_price is None or completion_price is None:
        return None

    return prompt_price, completion_price, "openrouter_catalog"


def _empty_usage_totals() -> Dict[str, Any]:
    return {
        "call_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "estimated_cost_usd": 0.0,
        "priced_call_count": 0,
        "unpriced_call_count": 0,
    }


def _coerce_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
