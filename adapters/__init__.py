"""LLMアダプタモジュール

このモジュールは OpenRouter と LM Studio に対する統一的なインターフェースを提供します。
"""

from typing import Optional, Dict, Type, List

from .base import CompletionResult, LLMAdapter, LLMError, UsageMetrics
from .openrouter_adapter import OpenRouterAdapter
from .lmstudio_adapter import LMStudioAdapter

__all__ = [
    "LLMAdapter",
    "LLMError",
    "CompletionResult",
    "UsageMetrics",
    "OpenRouterAdapter",
    "LMStudioAdapter",
    "get_adapter_for_model",
    "get_all_available_adapters",
    "get_available_judge_adapters",
]


def get_adapter_for_model(
    model_name: str, api_key: Optional[str] = None
) -> Optional[LLMAdapter]:
    """
    モデル名から適切なアダプタを返す

    判定ルール:
    - openrouter/*, or/* → OpenRouterAdapter
    - lmstudio/* → LMStudioAdapter

    Args:
        model_name: LLMモデル名

    Returns:
        対応するアダプタインスタンス、またはNone
    """
    model_lower = model_name.lower()

    if any(model_lower.startswith(p) for p in ["openrouter/", "or/"]):
        return OpenRouterAdapter(api_key=api_key)
    elif model_lower.startswith("lmstudio/"):
        return LMStudioAdapter(api_key=api_key)

    return None


def get_all_available_adapters() -> Dict[str, LLMAdapter]:
    """
    設定されているAPIキーを持つ全アダプタを返す

    Returns:
        ファミリー名をキーとするアダプタの辞書
        例: {"openrouter": OpenRouterAdapter(), "lmstudio": LMStudioAdapter()}
    """
    adapters = {}

    openrouter = OpenRouterAdapter()
    if openrouter.is_available():
        adapters["openrouter"] = openrouter

    lmstudio = LMStudioAdapter()
    if lmstudio.is_available():
        adapters["lmstudio"] = lmstudio

    return adapters


def get_available_judge_adapters(
    models: List[str], api_keys: Optional[Dict[str, str]] = None
) -> Dict[str, LLMAdapter]:
    """
    judgeモデルリストに対応するアダプタを返す

    Args:
        models: judgeモデル名のリスト

    Returns:
        モデル名をキーとするアダプタ辞書
    """
    adapters = {}
    api_keys = api_keys or {}
    for model in models:
        adapter = get_adapter_for_model(
            model, api_key=_resolve_api_key(model, api_keys)
        )
        if adapter and adapter.is_available():
            adapters[model] = adapter
    return adapters


def _resolve_api_key(model_name: str, api_keys: Dict[str, str]) -> Optional[str]:
    model_lower = model_name.lower()
    if any(model_lower.startswith(p) for p in ["openrouter/", "or/"]):
        return api_keys.get("openrouter")
    if model_lower.startswith("lmstudio/"):
        return api_keys.get("lmstudio")
    return None
