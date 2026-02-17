"""Streamlit secrets read/write helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional


class SecretsStore:
    """Persist API keys to .streamlit/secrets.toml."""

    FILE_PATH = Path(".streamlit/secrets.toml")
    KEYS = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }

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
    def _read_file(cls) -> Dict[str, Dict[str, str]]:
        if not cls.FILE_PATH.exists():
            return {}
        content = cls.FILE_PATH.read_text(encoding="utf-8")
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
        cls.FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        lines = ["[secrets]"]
        for key, value in sorted(data.get("secrets", {}).items()):
            escaped = str(value).replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
        content = "\n".join(lines) + "\n"
        cls.FILE_PATH.write_text(content, encoding="utf-8")
