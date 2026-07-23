"""モデル×リクエストパラメータ対応の単一解決層。

intent: DEC-001/002 (Core/model-parameter-support) — adapters/engine はここに問い合わせる。
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set

# Static tables as_of (OpenAI docs / observed API errors). Update when vendors change.
AS_OF = "2026-07-23"

# Parameters we currently reason about
PARAM_TEMPERATURE = "temperature"
PARAM_MAX_COMPLETION_TOKENS = "max_completion_tokens"

# OpenAI model families that reject non-default temperature (observed + docs).
# intent: DEC-002 — 静的表。族マッチで gpt-5.6-luna 等をカバー。
_OPENAI_TEMPERATURE_UNSUPPORTED_PREFIXES = (
    "o1",
    "o3",
    "o4",
    "gpt-5",  # gpt-5, gpt-5.4, gpt-5.6-luna, ...
)

# Models that require max_completion_tokens instead of max_tokens (OpenAI Chat Completions).
_OPENAI_MAX_COMPLETION_PREFIXES = (
    "o1",
    "o3",
    "o4",
    "gpt-5",
)

# Google / OpenRouter Gemini 3.x: engine historically omitted temperature.
_GOOGLE_TEMPERATURE_UNSUPPORTED_SUBSTRINGS = (
    "gemini-3",
)

# Exact-id overrides (normalized upstream id, lowercased): True = may send temperature
_OPENAI_TEMPERATURE_EXACT: Dict[str, bool] = {
    # leave empty; prefixes cover gpt-5 family. gpt-4o etc default True via profile.
}

_OR_SUPPORTED_PARAMS_CACHE: Optional[Dict[str, Set[str]]] = None


def _normalize_model_id(model: str) -> str:
    text = str(model or "").strip().lower()
    for prefix in (
        "openrouter/",
        "or/",
        "openai/",
        "anthropic/",
        "google-ai-studio/",
        "google/",
        "lmstudio/",
    ):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text


def _provider_family(provider: str) -> str:
    p = str(provider or "").strip().lower()
    if p in ("openrouter", "or"):
        return "openrouter"
    if p in ("openai",):
        return "openai"
    if p in ("anthropic",):
        return "anthropic"
    if p in ("google", "google-ai-studio", "gemini"):
        return "google"
    if p in ("lmstudio",):
        return "lmstudio"
    return p or "unknown"


def set_openrouter_supported_parameters_cache(
    cache: Optional[Dict[str, Set[str]]],
) -> None:
    """Test / adapter hook: model_id -> supported parameter names."""
    global _OR_SUPPORTED_PARAMS_CACHE
    _OR_SUPPORTED_PARAMS_CACHE = cache


def _load_openrouter_supported_params(model: str) -> Optional[Set[str]]:
    """Return supported_parameters for an OpenRouter upstream model id, or None if unknown."""
    normalized = _normalize_model_id(model)
    if _OR_SUPPORTED_PARAMS_CACHE is not None:
        # try exact then with/without vendor prefix already normalized
        if normalized in _OR_SUPPORTED_PARAMS_CACHE:
            return _OR_SUPPORTED_PARAMS_CACHE[normalized]
        return None

    # Prefer OpenRouterAdapter class cache (lazy import avoids import cycle).
    try:
        from adapters.openrouter_adapter import OpenRouterAdapter

        models = OpenRouterAdapter._fetch_models_cache()
        if not models:
            return None
        info = models.get(normalized)
        if not info:
            return None
        params = info.get("supported_parameters") or []
        return {str(p) for p in params}
    except Exception:
        return None


def _static_allows_temperature(family: str, normalized_model: str) -> Optional[bool]:
    if family == "openai":
        if normalized_model in _OPENAI_TEMPERATURE_EXACT:
            return _OPENAI_TEMPERATURE_EXACT[normalized_model]
        for prefix in _OPENAI_TEMPERATURE_UNSUPPORTED_PREFIXES:
            if normalized_model == prefix or normalized_model.startswith(prefix + "-"):
                return False
            # gpt-5.6-luna: startswith "gpt-5" via prefix "gpt-5" + next char not needing hyphen
            if prefix == "gpt-5" and normalized_model.startswith("gpt-5"):
                return False
            if prefix.startswith("o") and normalized_model.startswith(prefix):
                return False
        return True

    if family == "google":
        for needle in _GOOGLE_TEMPERATURE_UNSUPPORTED_SUBSTRINGS:
            if needle in normalized_model:
                return False
        return True

    if family == "anthropic":
        # No known blanket temperature ban in static table yet.
        return True

    if family == "lmstudio":
        return True

    return None


def allows(provider: str, model: str, parameter: str) -> bool:
    """Whether the request may include `parameter` for this provider/model.

    intent: DEC-002 — openrouter catalog → static table → safe default.
    For temperature, unknown => False (omit).
    """
    param = str(parameter or "").strip()
    family = _provider_family(provider)
    normalized = _normalize_model_id(model)

    if family == "openrouter":
        # Historic engine omit + OpenAI reasoning via OR: static unsafe wins over catalog
        if param == PARAM_TEMPERATURE:
            if "gemini-3" in normalized:
                return False
            if normalized.startswith("openai/"):
                upstream = normalized.split("/", 1)[1]
                static = _static_allows_temperature("openai", upstream)
                if static is False:
                    return False
            elif "/" not in normalized and normalized.startswith(
                ("gpt-5", "o1", "o3", "o4")
            ):
                static = _static_allows_temperature("openai", normalized)
                if static is False:
                    return False

        supported = _load_openrouter_supported_params(model)
        if supported is not None:
            return param in supported
        # catalog unknown: temperature omit (DEC-002)
        if param == PARAM_TEMPERATURE:
            return False
        return True

    if param == PARAM_TEMPERATURE:
        static = _static_allows_temperature(family, normalized)
        if static is not None:
            return static
        # unknown provider/model: omit temperature
        return False

    if param == PARAM_MAX_COMPLETION_TOKENS:
        return uses_max_completion_tokens(provider, model)

    # unknown parameter: allow (caller decides)
    return True


def uses_max_completion_tokens(provider: str, model: str) -> bool:
    """OpenAI-style models that need max_completion_tokens instead of max_tokens."""
    normalized = _normalize_model_id(model)
    # openrouter/openai/gpt-5.x → gpt-5.x
    if normalized.startswith("openai/"):
        normalized = normalized.split("/", 1)[1]
    for prefix in _OPENAI_MAX_COMPLETION_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix):
            return True
    return False


def should_send_temperature(
    provider: str, model: str, temperature: Optional[float]
) -> bool:
    """True if temperature should be included in the API request kwargs."""
    if temperature is None:
        return False
    return allows(provider, model, PARAM_TEMPERATURE)


def apply_temperature(
    kwargs: Dict[str, Any],
    *,
    provider: str,
    model: str,
    temperature: Optional[float],
) -> None:
    """Add temperature to kwargs only when allowed (INV-001)."""
    # intent-invariant: INV-001 (Core/model-parameter-support) — False ならキーを付けない
    if should_send_temperature(provider, model, temperature):
        kwargs["temperature"] = temperature
