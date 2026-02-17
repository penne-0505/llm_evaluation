"""LLMアダプタモジュール

このモジュールは複数のLLMプロバイダー（OpenAI, Anthropic, Gemini, OpenRouter）に対する
統一的なインターフェースを提供します。
"""

from typing import Optional, Dict, Type, List

from .base import LLMAdapter, LLMError
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .gemini_adapter import GeminiAdapter
from .openrouter_adapter import OpenRouterAdapter

__all__ = [
    "LLMAdapter",
    "LLMError",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "GeminiAdapter",
    "OpenRouterAdapter",
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
    - gpt-*, o1*, o3*, o4* → OpenAIAdapter
    - claude-* → AnthropicAdapter
    - gemini-* → GeminiAdapter
    - openrouter/*, or/* → OpenRouterAdapter

    Args:
        model_name: LLMモデル名

    Returns:
        対応するアダプタインスタンス、またはNone
    """
    model_lower = model_name.lower()

    if any(model_lower.startswith(p) for p in ["gpt-", "o1", "o3", "o4"]):
        return OpenAIAdapter(api_key=api_key)
    elif model_lower.startswith("claude-"):
        return AnthropicAdapter(api_key=api_key)
    elif model_lower.startswith("gemini-"):
        return GeminiAdapter(api_key=api_key)
    elif any(model_lower.startswith(p) for p in ["openrouter/", "or/"]):
        return OpenRouterAdapter(api_key=api_key)

    return None


def get_all_available_adapters() -> Dict[str, LLMAdapter]:
    """
    設定されているAPIキーを持つ全アダプタを返す

    Returns:
        ファミリー名をキーとするアダプタの辞書
        例: {"openai": OpenAIAdapter(), "anthropic": AnthropicAdapter(), ...}
    """
    adapters = {}

    openai = OpenAIAdapter()
    if openai.is_available():
        adapters["openai"] = openai

    anthropic = AnthropicAdapter()
    if anthropic.is_available():
        adapters["anthropic"] = anthropic

    gemini = GeminiAdapter()
    if gemini.is_available():
        adapters["gemini"] = gemini

    openrouter = OpenRouterAdapter()
    if openrouter.is_available():
        adapters["openrouter"] = openrouter

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
    if any(model_lower.startswith(p) for p in ["gpt-", "o1", "o3", "o4"]):
        return api_keys.get("openai")
    if model_lower.startswith("claude-"):
        return api_keys.get("anthropic")
    if model_lower.startswith("gemini-"):
        return api_keys.get("gemini")
    if any(model_lower.startswith(p) for p in ["openrouter/", "or/"]):
        return api_keys.get("openrouter")
    return None
