"""公式プロバイダ向け静的価格表（USD / token）。

intent: DEC-007 / INV-001 (Core/openai-compat-anthropic-providers) —
openai / anthropic / google の推定は本表のみ。OpenRouter catalog へフォールバックしない。
価格は as_of 時点の公開表からの転記。未掲載モデルは None。
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

# Prices are USD per token (same unit as OpenRouter catalog floats).
# Source pages checked 2026-07-23:
# - https://developers.openai.com/api/docs/pricing
# - https://platform.claude.com/docs/en/about-claude/pricing
# - Google AI Studio / Gemini API pricing (common Flash/Pro rates)

AS_OF = "2026-07-23"

PricingTuple = Tuple[float, float, str]  # input, output, pricing_source


def _per_mtok(input_usd: float, output_usd: float) -> Tuple[float, float]:
    return input_usd / 1_000_000.0, output_usd / 1_000_000.0


def _table(source: str, rows: Dict[str, Tuple[float, float]]) -> Dict[str, PricingTuple]:
    out: Dict[str, PricingTuple] = {}
    for model, (inp, outp) in rows.items():
        pi, po = _per_mtok(inp, outp)
        out[model.lower()] = (pi, po, source)
    return out


# input/output USD per 1M tokens
_OPENAI = _table(
    "openai_static",
    {
        "gpt-4.1": (2.0, 8.0),
        "gpt-4.1-mini": (0.4, 1.6),
        "gpt-4.1-nano": (0.1, 0.4),
        "gpt-4o": (2.5, 10.0),
        "gpt-4o-mini": (0.15, 0.6),
        "o1": (15.0, 60.0),
        "o1-mini": (1.1, 4.4),
        "o3-mini": (1.1, 4.4),
        "gpt-5": (1.25, 10.0),
    },
)

_ANTHROPIC = _table(
    "anthropic_static",
    {
        "claude-opus-4-8": (5.0, 25.0),
        "claude-opus-4-7": (5.0, 25.0),
        "claude-opus-4-6": (5.0, 25.0),
        "claude-opus-4-5": (5.0, 25.0),
        "claude-sonnet-5": (2.0, 10.0),  # intro through 2026-08-31
        "claude-sonnet-4-6": (3.0, 15.0),
        "claude-sonnet-4-5": (3.0, 15.0),
        "claude-haiku-4-5": (1.0, 5.0),
        # common API ids
        "claude-3-5-sonnet-20241022": (3.0, 15.0),
        "claude-3-5-haiku-20241022": (0.8, 4.0),
        "claude-3-opus-20240229": (15.0, 75.0),
    },
)

_GOOGLE = _table(
    "google_static",
    {
        "gemini-2.5-flash": (0.30, 2.50),
        "gemini-2.5-flash-lite": (0.10, 0.40),
        "gemini-2.5-pro": (1.25, 10.0),
        "gemini-2.0-flash": (0.10, 0.40),
        "gemini-1.5-flash": (0.075, 0.30),
        "gemini-1.5-pro": (1.25, 5.0),
    },
)

_TABLES: Dict[str, Dict[str, PricingTuple]] = {
    "openai": _OPENAI,
    "anthropic": _ANTHROPIC,
    "google": _GOOGLE,
}


def _normalize_model_id(model: str) -> str:
    text = str(model or "").strip().lower()
    # strip registry prefix if present: openai/gpt-4o → gpt-4o
    for prefix in (
        "openai/",
        "anthropic/",
        "google-ai-studio/",
        "google/",
        "openrouter/",
        "or/",
    ):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    # dated snapshots: gpt-4o-2024-08-06 → try exact then family
    return text


def lookup_static_pricing(
    pricing_profile: str, model: str
) -> Optional[PricingTuple]:
    """Return (input_price, output_price, source) or None if unknown.

    Never consults OpenRouter catalog (INV-001).
    """
    table = _TABLES.get(pricing_profile)
    if not table:
        return None

    normalized = _normalize_model_id(model)
    if normalized in table:
        return table[normalized]

    # progressive prefix trim for dated ids: gpt-4o-2024-08-06 → gpt-4o
    parts = normalized.split("-")
    while len(parts) > 1:
        parts = parts[:-1]
        candidate = "-".join(parts)
        if candidate in table:
            return table[candidate]

    # anthropic: claude-sonnet-4-5-20250929 style
    for key in table:
        if normalized.startswith(key):
            return table[key]

    return None
