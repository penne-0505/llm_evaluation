"""usage 集計と推定コスト計算"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.model_catalog import ModelCatalog


def summarize_benchmark_usage(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """保存済み task 結果から usage サマリーを構築する。"""
    usage_records: List[Dict[str, Any]] = []

    for task in tasks:
        usage_records.extend(_subject_usage_records_from_task(task))

        for judge_result in task.get("judge_results", {}).values():
            for run in judge_result.get("runs", []):
                usage = run.get("usage")
                if isinstance(usage, dict):
                    usage_records.append(usage)

    return summarize_usage_records(usage_records)


def summarize_subject_usage(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """被検モデル（subject）のみの usage サマリーを構築する。"""
    usage_records: List[Dict[str, Any]] = []

    for task in tasks:
        usage_records.extend(_subject_usage_records_from_task(task))

    return summarize_usage_records(usage_records)


def _subject_usage_records_from_task(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    """task から subject usage レコードを取り出す。

    intent: DEC-003 (Core/subject-multi-run-judge-batch) — subject_runs[] がある場合は
    run 単位を優先し、合算済み subject_usage との二重計上を避ける。
    """
    runs = task.get("subject_runs")
    if isinstance(runs, list) and runs:
        records: List[Dict[str, Any]] = []
        for run in runs:
            if not isinstance(run, dict):
                continue
            usage = run.get("subject_usage")
            if isinstance(usage, dict):
                records.append(usage)
        if records:
            return records

    subject_usage = task.get("subject_usage")
    if isinstance(subject_usage, dict):
        return [subject_usage]
    return []


def summarize_judge_usage(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Judge モデルのみの usage サマリーを構築する。"""
    usage_records: List[Dict[str, Any]] = []

    for task in tasks:
        for judge_result in task.get("judge_results", {}).values():
            for run in judge_result.get("runs", []):
                usage = run.get("usage")
                if isinstance(usage, dict):
                    usage_records.append(usage)

    return summarize_usage_records(usage_records)


def summarize_task_timing(tasks: List[Dict[str, Any]]) -> Optional[Dict[str, int]]:
    """通常タスクの task_timing を合算する。

    intent: DEC-001/002 (Core/time-roi-task-timing) — ROI 分母は wall-clock ではなく
    タスク単位 subject+judge 合算。いずれかのタスクに task_timing が無い場合は None
    （AC-003: 暗黙フォールバック禁止）。
    """
    if not tasks:
        return {
            "subject_duration_ms": 0,
            "judge_duration_ms": 0,
            "total_duration_ms": 0,
        }

    subject_duration_ms = 0
    judge_duration_ms = 0
    for task in tasks:
        timing = task.get("task_timing")
        if not isinstance(timing, dict):
            return None
        subject_duration_ms += _coerce_int(timing.get("subject_duration_ms"))
        judge_duration_ms += _coerce_int(timing.get("judge_duration_ms"))

    return {
        "subject_duration_ms": subject_duration_ms,
        "judge_duration_ms": judge_duration_ms,
        "total_duration_ms": subject_duration_ms + judge_duration_ms,
    }


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
                "duration_ms": 0,
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

        duration_ms = _coerce_int(usage.get("duration_ms"))
        group["duration_ms"] += duration_ms
        totals["total_duration_ms"] += duration_ms

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


def _extract_pricing(entry: Optional[Dict[str, Any]]) -> Optional[Tuple[float, float, str]]:
    if not entry:
        return None
    pricing = entry.get("pricing", {})
    prompt_price = _coerce_float(pricing.get("prompt"))
    completion_price = _coerce_float(pricing.get("completion"))
    if prompt_price is None or completion_price is None:
        return None
    return prompt_price, completion_price, "openrouter_catalog"


_PROVIDER_TO_VENDOR = {
    "openai": "openai",
    "anthropic": "anthropic",
    "gemini": "google",
    "lmstudio": "lmstudio",
}


def _lookup_pricing(
    provider: str, model: str
) -> Optional[Tuple[float, float, str]]:
    # 1. OpenRouter プロバイダの場合は直接検索
    if provider == "openrouter":
        pricing = _extract_pricing(ModelCatalog.find_model_entry(provider, model))
        if pricing:
            return pricing

    # 2. その他のプロバイダ: OpenRouter カタログをフォールバックとして使用
    # OpenRouter は通常 {vendor}/{model} 形式でモデルを登録している
    candidates = []

    # provider名がOpenRouter上のvendor名と一致する場合
    if provider in ("openai", "anthropic", "google", "meta", "mistral", "microsoft", "deepseek", "x-ai"):
        candidates.append(f"{provider}/{model}")

    # provider → vendor マッピングを使った検索 (例: gemini → google)
    vendor = _PROVIDER_TO_VENDOR.get(provider)
    if vendor and vendor != provider:
        candidates.append(f"{vendor}/{model}")

    # モデル名が既に vendor/model 形式の場合 (例: openai/gpt-4o)
    if "/" in model and not model.startswith(("openrouter/", "lmstudio/")):
        candidates.append(model)

    # provider名をプレフィックスに付けた場合（lmstudioなどの特殊ケース）
    candidates.append(f"{provider}/{model}")

    for candidate in candidates:
        pricing = _extract_pricing(ModelCatalog.find_model_entry("openrouter", candidate))
        if pricing:
            return pricing

    return None


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
        "total_duration_ms": 0,
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
