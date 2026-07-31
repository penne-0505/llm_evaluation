"""Tests for OpenRouter preferred-host helpers."""

from core.openrouter_preferred_host import (
    PREFERRED_HOST_ATTEMPTS,
    iter_extra_params_attempts,
    merge_provider_pin,
    normalize_endpoint,
    parse_openrouter_model_path,
)


def test_parse_openrouter_model_path():
    assert parse_openrouter_model_path("openrouter/anthropic/claude-sonnet-4") == (
        "anthropic",
        "claude-sonnet-4",
    )
    assert parse_openrouter_model_path("or/openai/gpt-4o") == ("openai", "gpt-4o")
    assert parse_openrouter_model_path("anthropic/claude-sonnet-4") == (
        "anthropic",
        "claude-sonnet-4",
    )
    assert parse_openrouter_model_path("solo") is None


def test_merge_provider_pin_preserves_reasoning():
    merged = merge_provider_pin({"reasoning": {"effort": "xhigh"}}, "together")
    assert merged["reasoning"] == {"effort": "xhigh"}
    assert merged["provider"] == {"only": ["together"], "allow_fallbacks": False}


def test_iter_extra_params_attempts_pin_then_unrestricted():
    # intent-invariant: INV-001
    base = {"reasoning": {"effort": "xhigh"}}
    attempts = list(iter_extra_params_attempts(base, "deepinfra"))
    assert len(attempts) == PREFERRED_HOST_ATTEMPTS + 1
    for pinned in attempts[:-1]:
        assert pinned is not None
        assert pinned["provider"]["only"] == ["deepinfra"]
        assert pinned["provider"]["allow_fallbacks"] is False
        assert pinned["reasoning"] == {"effort": "xhigh"}
    assert attempts[-1] == base
    assert "provider" not in (attempts[-1] or {})


def test_iter_extra_params_attempts_without_host():
    base = {"reasoning": {"effort": "medium"}}
    attempts = list(iter_extra_params_attempts(base, None))
    assert attempts == [base]


def test_normalize_endpoint_metrics():
    normalized = normalize_endpoint(
        {
            "tag": "together",
            "provider_name": "Together",
            "throughput_last_30m": {"p50": 42.5, "p90": 60},
            "pricing": {
                "prompt": "0.000003",
                "completion": "0.000015",
                "input_cache_read": "0.0000003",
            },
        }
    )
    assert normalized is not None
    assert normalized["slug"] == "together"
    assert normalized["provider_name"] == "Together"
    assert normalized["tps_p50"] == 42.5
    assert abs(normalized["input_per_million"] - 3.0) < 1e-9
    assert abs(normalized["output_per_million"] - 15.0) < 1e-9
    assert abs(normalized["cache_read_per_million"] - 0.3) < 1e-9


def test_normalize_endpoint_missing_cache_is_none():
    normalized = normalize_endpoint(
        {
            "tag": "fireworks",
            "provider_name": "Fireworks",
            "pricing": {"prompt": "0.000001", "completion": "0.000002"},
        }
    )
    assert normalized is not None
    assert normalized["cache_read_per_million"] is None
    assert normalized["tps_p50"] is None
