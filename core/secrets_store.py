"""Streamlit secrets read/write helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

from core.app_paths import AppPaths


class _FileSecretBackend:
    """将来の keychain 対応に備えたファイル保存バックエンド。"""

    def __init__(self, file_path: Path):
        self.file_path = file_path

    def read_text(self) -> str:
        return self.file_path.read_text(encoding="utf-8")

    def exists(self) -> bool:
        return self.file_path.exists()

    def write_text(self, content: str) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(content, encoding="utf-8")


class SecretsStore:
    """Persist API keys to an app-local secrets file."""

    FILE_PATH: Path | None = None
    KEYS = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    OPENROUTER_MANAGEMENT_ENV_KEY = "OPENROUTER_MANAGEMENT_KEY"

    @classmethod
    def _file_path(cls) -> Path:
        return cls.FILE_PATH or AppPaths.secrets_file()

    @classmethod
    def _legacy_file_path(cls) -> Path:
        return AppPaths.repo_path(".streamlit", "secrets.toml")

    @classmethod
    def _backend(cls, path: Path | None = None) -> _FileSecretBackend:
        return _FileSecretBackend(path or cls._file_path())

    @classmethod
    def load_existing(cls) -> Dict[str, str]:
        """Load existing keys (secrets.toml has priority over env)."""
        data = cls._read_file()
        secrets = data.get("secrets", {})
        results: Dict[str, str] = {}
        for provider, env_key in cls.KEYS.items():
            if env_key in secrets:
                results[provider] = str(secrets[env_key])
            elif env_key in os.environ:
                results[provider] = os.environ[env_key]
        return results

    @classmethod
    def save(cls, values: Dict[str, Optional[str]]) -> None:
        """Save provided keys into secrets.toml."""
        data = cls._read_file()
        secrets = data.get("secrets", {})

        for provider, env_key in cls.KEYS.items():
            value = values.get(provider)
            if value:
                secrets[env_key] = value

        data["secrets"] = secrets
        cls._write_file(data)

    @classmethod
    def clear(cls, providers: Dict[str, bool]) -> None:
        """Remove keys for selected providers."""
        data = cls._read_file()
        secrets = data.get("secrets", {})
        for provider, enabled in providers.items():
            if not enabled:
                continue
            env_key = cls.KEYS.get(provider)
            if env_key and env_key in secrets:
                secrets.pop(env_key, None)
        data["secrets"] = secrets
        cls._write_file(data)

    @classmethod
    def load_openrouter_management_key(cls) -> str | None:
        data = cls._read_file()
        secrets = data.get("secrets", {})
        if cls.OPENROUTER_MANAGEMENT_ENV_KEY in secrets:
            return str(secrets[cls.OPENROUTER_MANAGEMENT_ENV_KEY])
        return os.environ.get(cls.OPENROUTER_MANAGEMENT_ENV_KEY)

    @classmethod
    def save_openrouter_management_key(cls, value: str) -> None:
        data = cls._read_file()
        secrets = data.get("secrets", {})
        secrets[cls.OPENROUTER_MANAGEMENT_ENV_KEY] = value
        data["secrets"] = secrets
        cls._write_file(data)

    @classmethod
    def clear_openrouter_management_key(cls) -> None:
        data = cls._read_file()
        secrets = data.get("secrets", {})
        secrets.pop(cls.OPENROUTER_MANAGEMENT_ENV_KEY, None)
        data["secrets"] = secrets
        cls._write_file(data)

    @classmethod
    def _read_file(cls) -> Dict[str, Dict[str, str]]:
        backend = cls._backend()
        if backend.exists():
            content = backend.read_text()
        else:
            legacy_path = cls._legacy_file_path()
            legacy_backend = cls._backend(legacy_path)
            if not legacy_backend.exists():
                return {}
            content = legacy_backend.read_text()

        data: Dict[str, Dict[str, str]] = {"secrets": {}}
        current_section = None
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                current_section = stripped[1:-1]
                data.setdefault(current_section, {})
                continue
            if "=" in stripped:
                key, value = stripped.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"')
                if current_section is None:
                    current_section = "secrets"
                    data.setdefault(current_section, {})
                data[current_section][key] = value
        return data

    @classmethod
    def _write_file(cls, data: Dict[str, Dict[str, str]]) -> None:
        lines = ["[secrets]"]
        for key, value in sorted(data.get("secrets", {}).items()):
            escaped = str(value).replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
        content = "\n".join(lines) + "\n"
        cls._backend().write_text(content)
