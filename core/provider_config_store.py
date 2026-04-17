"""Provider 固有の非 secret 設定を保存する。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from core.app_paths import AppPaths


class ProviderConfigStore:
    """base_url などの非 secret 設定を app-local に保存する。"""

    FILE_PATH: Path | None = None

    @classmethod
    def _file_path(cls) -> Path:
        return cls.FILE_PATH or AppPaths.provider_config_file()

    @classmethod
    def load(cls) -> Dict[str, Any]:
        path = cls._file_path()
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    @classmethod
    def save_provider(cls, provider: str, values: Dict[str, Any]) -> None:
        data = cls.load()
        provider_values = {
            key: value
            for key, value in values.items()
            if value is not None
        }
        data[provider] = provider_values

        file_path = cls._file_path()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load_provider(cls, provider: str) -> Dict[str, Any]:
        data = cls.load()
        values = data.get(provider)
        return values if isinstance(values, dict) else {}

    @classmethod
    def clear_provider(cls, provider: str) -> None:
        data = cls.load()
        if provider in data:
            data.pop(provider, None)
            file_path = cls._file_path()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
