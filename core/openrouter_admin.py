"""OpenRouter management key helpers."""

from __future__ import annotations

import json
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OpenRouterAdminError(Exception):
    """OpenRouter credits API 呼び出し失敗。"""


def fetch_credits(api_key: str) -> Dict[str, Any]:
    request = Request(
        "https://openrouter.ai/api/v1/credits",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="ignore")
        raise OpenRouterAdminError(
            f"OpenRouter credits API error: {error.code} {detail}".strip()
        ) from error
    except URLError as error:
        raise OpenRouterAdminError(
            f"OpenRouter credits API unreachable: {error.reason}"
        ) from error
    except Exception as error:
        raise OpenRouterAdminError(
            f"OpenRouter credits API unexpected error: {error}"
        ) from error

    data = payload.get("data") or {}
    total_credits = data.get("total_credits")
    total_usage = data.get("total_usage")
    remaining = None
    if isinstance(total_credits, (int, float)) and isinstance(total_usage, (int, float)):
        remaining = round(float(total_credits) - float(total_usage), 8)
    return {
        "total_credits": total_credits,
        "total_usage": total_usage,
        "remaining_credits": remaining,
    }
