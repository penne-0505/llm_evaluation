"""LLMアダプタモジュール

OpenRouter / LM Studio / registry（openai_compatible・anthropic）への統一インターフェース。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# base / adapter を先に公開してから core を import する（benchmark_engine ↔ adapters の循環回避）
from .anthropic_adapter import AnthropicAdapter
from .base import CompletionResult, LLMAdapter, LLMError, UsageMetrics
from .lmstudio_adapter import LMStudioAdapter
from .openai_compatible_adapter import OpenAICompatibleAdapter
from .openrouter_adapter import OpenRouterAdapter

from core.provider_registry import ProviderEntry, ProviderRegistry
from core.secrets_store import SecretsStore

__all__ = [
    "LLMAdapter",
    "LLMError",
    "CompletionResult",
    "UsageMetrics",
    "OpenRouterAdapter",
    "LMStudioAdapter",
    "OpenAICompatibleAdapter",
    "AnthropicAdapter",
    "get_adapter_for_model",
    "get_all_available_adapters",
    "get_available_judge_adapters",
    "parse_model_provider",
    "resolve_api_key_for_model",
]


def parse_model_provider(model_name: str) -> Tuple[Optional[str], str]:
    """モデル ID から (provider_id, remainder) を返す。

    intent: DEC-003 — `{provider_id}/{upstream}`。`or/` は openrouter エイリアス。
    """
    name = str(model_name or "").strip()
    if not name or "/" not in name:
        return None, name
    prefix, rest = name.split("/", 1)
    lower = prefix.lower()
    if lower == "or":
        return "openrouter", rest
    if lower == "lmstudio":
        return "lmstudio", rest
    return lower, rest


def resolve_api_key_for_model(
    model_name: str, api_keys: Optional[Dict[str, str]] = None
) -> Optional[str]:
    api_keys = api_keys or {}
    provider_id, _ = parse_model_provider(model_name)
    if not provider_id:
        return None
    if provider_id in api_keys and api_keys[provider_id]:
        return api_keys[provider_id]
    return SecretsStore.load_provider_secret(provider_id)


def _entry_for_provider(provider_id: str) -> Optional[ProviderEntry]:
    if provider_id == "lmstudio":
        return None
    for preset in ProviderRegistry.builtin_presets():
        if preset.id == provider_id:
            return preset
    return ProviderRegistry.get(provider_id)


def get_adapter_for_model(
    model_name: str, api_key: Optional[str] = None
) -> Optional[LLMAdapter]:
    """
    モデル名から適切なアダプタを返す。

    - lmstudio/* → LMStudioAdapter
    - openrouter/* | or/* → OpenRouterAdapter（profile 固有ロジック維持）
    - registry openai_compatible → OpenAICompatibleAdapter
    - registry anthropic → AnthropicAdapter
    """
    provider_id, _ = parse_model_provider(model_name)
    if not provider_id:
        return None

    if provider_id == "lmstudio":
        return LMStudioAdapter(api_key=api_key)

    if provider_id == "openrouter":
        # intent: DEC-005 — OpenRouter 固有は既存アダプタを維持
        return OpenRouterAdapter(api_key=api_key)

    entry = _entry_for_provider(provider_id)
    if entry is None:
        return None

    key = api_key if api_key is not None else SecretsStore.load_provider_secret(entry.id)

    if entry.kind == "anthropic":
        return AnthropicAdapter(
            api_key=key,
            provider_id=entry.id,
            base_url=entry.base_url,
        )

    if entry.kind == "openai_compatible":
        if not entry.base_url:
            return None
        if entry.profile == "openrouter":
            return OpenRouterAdapter(api_key=key)
        return OpenAICompatibleAdapter(
            provider_id=entry.id,
            api_key=key,
            base_url=entry.base_url,
            profile=entry.profile,
        )

    return None


def get_all_available_adapters() -> Dict[str, LLMAdapter]:
    adapters: Dict[str, LLMAdapter] = {}

    openrouter = OpenRouterAdapter()
    if openrouter.is_available():
        adapters["openrouter"] = openrouter

    lmstudio = LMStudioAdapter()
    if lmstudio.is_available():
        adapters["lmstudio"] = lmstudio

    for entry in ProviderRegistry.list_providers():
        if entry.id in adapters:
            continue
        if entry.id == "openrouter":
            continue
        key = SecretsStore.load_provider_secret(entry.id)
        adapter = get_adapter_for_model(f"{entry.id}/probe", api_key=key)
        if adapter and adapter.is_available():
            adapters[entry.id] = adapter

    return adapters


def get_available_judge_adapters(
    models: List[str], api_keys: Optional[Dict[str, str]] = None
) -> Dict[str, LLMAdapter]:
    adapters = {}
    api_keys = api_keys or {}
    for model in models:
        adapter = get_adapter_for_model(
            model, api_key=resolve_api_key_for_model(model, api_keys)
        )
        if adapter and adapter.is_available():
            adapters[model] = adapter
    return adapters
