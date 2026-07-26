"""OpenRouter preferred-host helpers.

intent: DEC-001 (Core/openrouter-preferred-host) — pin same host up to N times,
then unrestricted fallback.
intent: DEC-004 (Core/openrouter-preferred-host) — endpoints metrics normalize.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PREFERRED_HOST_ATTEMPTS = 3
OPENROUTER_ENDPOINTS_URL = "https://openrouter.ai/api/v1/models/{author}/{slug}/endpoints"


class OpenRouterEndpointsError(Exception):
    """OpenRouter endpoints API 呼び出し失敗。"""


def parse_openrouter_model_path(model_id: str) -> Optional[Tuple[str, str]]:
    """Return (author, slug) for openrouter-prefixed or author/slug ids."""
    raw = (model_id or "").strip()
    if not raw:
        return None
    if raw.startswith("openrouter/"):
        raw = raw[len("openrouter/") :]
    if raw.startswith("or/"):
        raw = raw[len("or/") :]
    parts = [p for p in raw.split("/") if p]
    if len(parts) < 2:
        return None
    return parts[0], "/".join(parts[1:])


def is_openrouter_model_id(model_id: str) -> bool:
    value = (model_id or "").strip().lower()
    return value.startswith("openrouter/") or value.startswith("or/")


def merge_provider_pin(
    extra_params: Optional[Dict[str, Any]],
    host_slug: str,
) -> Dict[str, Any]:
    """Merge preferred-host pin into extra_body params without dropping siblings."""
    merged: Dict[str, Any] = dict(extra_params or {})
    # intent: DEC-001 — only + allow_fallbacks false keeps retries on the same host
    merged["provider"] = {
        "only": [host_slug],
        "allow_fallbacks": False,
    }
    return merged


def iter_extra_params_attempts(
    base_extra: Optional[Dict[str, Any]],
    preferred_host: Optional[str],
    *,
    preferred_attempts: int = PREFERRED_HOST_ATTEMPTS,
) -> Iterator[Optional[Dict[str, Any]]]:
    """
    Yield extra_params variants: N pinned attempts, then one unrestricted.

    intent-invariant: INV-001 — unrestricted comes only after pinned attempts.
    """
    host = (preferred_host or "").strip()
    if not host:
        yield base_extra
        return
    pinned = merge_provider_pin(base_extra, host)
    attempts = max(1, int(preferred_attempts))
    for _ in range(attempts):
        yield pinned
    yield base_extra


def _per_million(raw: Any) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        return float(raw) * 1_000_000.0
    except (TypeError, ValueError):
        return None


def _percentile_p50(stats: Any) -> Optional[float]:
    if not isinstance(stats, dict):
        return None
    value = stats.get("p50")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_endpoint(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize one OpenRouter endpoint for UI + routing."""
    tag = raw.get("tag") or raw.get("provider_name")
    if not isinstance(tag, str) or not tag.strip():
        return None
    pricing = raw.get("pricing") if isinstance(raw.get("pricing"), dict) else {}
    return {
        "slug": tag.strip(),
        "provider_name": str(raw.get("provider_name") or tag).strip(),
        "quantization": raw.get("quantization"),
        "status": raw.get("status"),
        "tps_p50": _percentile_p50(raw.get("throughput_last_30m")),
        "input_per_million": _per_million(pricing.get("prompt")),
        "output_per_million": _per_million(pricing.get("completion")),
        "cache_read_per_million": _per_million(pricing.get("input_cache_read")),
    }


def fetch_model_endpoints(api_key: str, model_id: str) -> List[Dict[str, Any]]:
    parsed = parse_openrouter_model_path(model_id)
    if parsed is None:
        raise OpenRouterEndpointsError(f"invalid OpenRouter model id: {model_id}")
    author, slug = parsed
    url = OPENROUTER_ENDPOINTS_URL.format(author=author, slug=slug)
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="ignore")
        raise OpenRouterEndpointsError(
            f"OpenRouter endpoints API error: {error.code} {detail}".strip()
        ) from error
    except URLError as error:
        raise OpenRouterEndpointsError(
            f"OpenRouter endpoints API unreachable: {error.reason}"
        ) from error
    except Exception as error:
        raise OpenRouterEndpointsError(
            f"OpenRouter endpoints API unexpected error: {error}"
        ) from error

    data = payload.get("data") if isinstance(payload, dict) else None
    endpoints_raw = []
    if isinstance(data, dict):
        endpoints_raw = data.get("endpoints") or []
    elif isinstance(payload, dict):
        endpoints_raw = payload.get("endpoints") or []
    if not isinstance(endpoints_raw, list):
        return []

    normalized: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in endpoints_raw:
        if not isinstance(item, dict):
            continue
        entry = normalize_endpoint(item)
        if entry is None or entry["slug"] in seen:
            continue
        seen.add(entry["slug"])
        normalized.append(entry)
    return normalized
