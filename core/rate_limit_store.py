"""プロバイダ別レート制限の推奨デフォルトと永続化。

intent: DEC-004 (Core/concurrent-evaluation-jobs) — max_requests / window_seconds、
Settings 編集可、未設定は推奨デフォルト（未知は保守的既定）。secret は混ぜない。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from core.app_paths import AppPaths

# 推奨デフォルト（検証時に実値を verification へ残す）
RECOMMENDED_DEFAULTS: Dict[str, Dict[str, int]] = {
    "openrouter": {"max_requests": 30, "window_seconds": 60},
    "openai": {"max_requests": 60, "window_seconds": 60},
    "anthropic": {"max_requests": 40, "window_seconds": 60},
    "google-ai-studio": {"max_requests": 30, "window_seconds": 60},
    "lmstudio": {"max_requests": 120, "window_seconds": 60},
}

# 未知プロバイダ用の保守的既定（INV-003）
UNKNOWN_PROVIDER_DEFAULT: Dict[str, int] = {
    "max_requests": 20,
    "window_seconds": 60,
}


@dataclass(frozen=True)
class RateLimitConfig:
    max_requests: int
    window_seconds: int
    is_default: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
            "is_default": self.is_default,
        }


def _clamp_limit(max_requests: int, window_seconds: int) -> tuple[int, int]:
    max_requests = max(1, min(int(max_requests), 10_000))
    window_seconds = max(1, min(int(window_seconds), 3600))
    return max_requests, window_seconds


def recommended_for(provider_id: str) -> RateLimitConfig:
    raw = RECOMMENDED_DEFAULTS.get(provider_id) or UNKNOWN_PROVIDER_DEFAULT
    max_requests, window_seconds = _clamp_limit(
        raw["max_requests"], raw["window_seconds"]
    )
    return RateLimitConfig(
        max_requests=max_requests,
        window_seconds=window_seconds,
        is_default=True,
    )


class RateLimitStore:
    """非 secret のレート制限上書きを app-local JSON に保存する。"""

    FILE_PATH: Path | None = None

    @classmethod
    def _file_path(cls) -> Path:
        return cls.FILE_PATH or AppPaths.rate_limits_file()

    @classmethod
    def load_overrides(cls) -> Dict[str, Dict[str, int]]:
        path = cls._file_path()
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        providers = data.get("providers")
        if not isinstance(providers, dict):
            return {}
        result: Dict[str, Dict[str, int]] = {}
        for provider_id, raw in providers.items():
            if not isinstance(provider_id, str) or not isinstance(raw, dict):
                continue
            try:
                max_requests, window_seconds = _clamp_limit(
                    int(raw["max_requests"]), int(raw["window_seconds"])
                )
            except (KeyError, TypeError, ValueError):
                continue
            result[provider_id] = {
                "max_requests": max_requests,
                "window_seconds": window_seconds,
            }
        return result

    @classmethod
    def save_overrides(cls, providers: Dict[str, Dict[str, int]]) -> None:
        cleaned: Dict[str, Dict[str, int]] = {}
        for provider_id, raw in providers.items():
            pid = str(provider_id).strip()
            if not pid or not isinstance(raw, dict):
                continue
            try:
                max_requests, window_seconds = _clamp_limit(
                    int(raw["max_requests"]), int(raw["window_seconds"])
                )
            except (KeyError, TypeError, ValueError):
                continue
            cleaned[pid] = {
                "max_requests": max_requests,
                "window_seconds": window_seconds,
            }
        path = cls._file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"providers": cleaned}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def clear_overrides(cls) -> None:
        cls.save_overrides({})

    @classmethod
    def resolve(cls, provider_id: str) -> RateLimitConfig:
        pid = str(provider_id or "").strip() or "unknown"
        overrides = cls.load_overrides()
        if pid in overrides:
            raw = overrides[pid]
            return RateLimitConfig(
                max_requests=raw["max_requests"],
                window_seconds=raw["window_seconds"],
                is_default=False,
            )
        return recommended_for(pid)

    @classmethod
    def list_effective(
        cls, provider_ids: Optional[list[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        ids = list(provider_ids or [])
        for builtin in RECOMMENDED_DEFAULTS:
            if builtin not in ids:
                ids.append(builtin)
        overrides = cls.load_overrides()
        for pid in overrides:
            if pid not in ids:
                ids.append(pid)
        result: Dict[str, Dict[str, Any]] = {}
        for pid in ids:
            effective = cls.resolve(pid)
            recommended = recommended_for(pid)
            result[pid] = {
                **effective.to_dict(),
                "recommended": {
                    "max_requests": recommended.max_requests,
                    "window_seconds": recommended.window_seconds,
                },
            }
        return result
