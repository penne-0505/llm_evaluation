"""SecretsStore 拡張: registry id 単位の API key（既存 KEYS 互換）。"""

from __future__ import annotations

import os
import re
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
        "lmstudio": "LMSTUDIO_API_TOKEN",
    }
    # intent: DEC-010 — google-ai-studio は既存 GEMINI_API_KEY スタブへ写像
    PROVIDER_ENV_ALIASES = {
        "google-ai-studio": "GEMINI_API_KEY",
    }
    OPENROUTER_MANAGEMENT_ENV_KEY = "OPENROUTER_MANAGEMENT_KEY"
    _PROVIDER_ENV_RE = re.compile(r"^PROVIDER_([A-Z0-9_]+)_API_KEY$")

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
    def env_key_for_provider(cls, provider_id: str) -> str:
        """registry id → secrets.toml / env キー名。

        intent: DEC-008 (Core/openai-compat-anthropic-providers) — 固定 KEYS を優先し、
        それ以外は PROVIDER_<ID>_API_KEY。
        """
        pid = str(provider_id or "").strip()
        if pid in cls.KEYS:
            return cls.KEYS[pid]
        if pid in cls.PROVIDER_ENV_ALIASES:
            return cls.PROVIDER_ENV_ALIASES[pid]
        normalized = pid.upper().replace("-", "_")
        return f"PROVIDER_{normalized}_API_KEY"

    @classmethod
    def provider_id_from_env_key(cls, env_key: str) -> Optional[str]:
        for provider, key in cls.KEYS.items():
            if key == env_key:
                if provider == "gemini":
                    return "google-ai-studio"
                return provider
        for provider, key in cls.PROVIDER_ENV_ALIASES.items():
            if key == env_key:
                return provider
        match = cls._PROVIDER_ENV_RE.match(env_key)
        if match:
            return match.group(1).lower().replace("_", "-")
        return None

    @classmethod
    def load_existing(cls) -> Dict[str, str]:
        """Load existing keys (secrets.toml has priority over env).

        戻り値のキーは provider id（openrouter / openai / google-ai-studio 等）。
        後方互換のため `gemini` も、値があれば残す。
        """
        data = cls._read_file()
        secrets = data.get("secrets", {})
        results: Dict[str, str] = {}

        def _put(provider_id: str, value: str) -> None:
            if value:
                results[provider_id] = value

        for provider, env_key in cls.KEYS.items():
            value = None
            if env_key in secrets:
                value = str(secrets[env_key])
            elif env_key in os.environ:
                value = os.environ[env_key]
            if not value:
                continue
            if provider == "gemini":
                _put("gemini", value)
                _put("google-ai-studio", value)
            else:
                _put(provider, value)

        for env_key, raw in {**secrets, **dict(os.environ)}.items():
            if not cls._PROVIDER_ENV_RE.match(str(env_key)):
                continue
            provider_id = cls.provider_id_from_env_key(str(env_key))
            if provider_id and provider_id not in results:
                # secrets 優先
                if env_key in secrets:
                    _put(provider_id, str(secrets[env_key]))
                elif env_key in os.environ:
                    _put(provider_id, str(os.environ[env_key]))

        return results

    @classmethod
    def load_provider_secret(cls, provider_id: str) -> Optional[str]:
        existing = cls.load_existing()
        value = existing.get(provider_id)
        if value:
            return value
        # gemini ↔ google-ai-studio
        if provider_id == "google-ai-studio":
            return existing.get("gemini")
        if provider_id == "gemini":
            return existing.get("google-ai-studio")
        return None

    @classmethod
    def save(cls, values: Dict[str, Optional[str]]) -> None:
        """Save provided keys into secrets.toml（provider id キー）。"""
        data = cls._read_file()
        secrets = data.get("secrets", {})

        for provider, value in values.items():
            if not value:
                continue
            env_key = cls.env_key_for_provider(str(provider))
            secrets[env_key] = value

        data["secrets"] = secrets
        cls._write_file(data)

    @classmethod
    def save_provider_secret(cls, provider_id: str, value: str) -> None:
        cls.save({provider_id: value})

    @classmethod
    def clear(cls, providers: Dict[str, bool]) -> None:
        """Remove keys for selected providers."""
        data = cls._read_file()
        secrets = data.get("secrets", {})
        for provider, enabled in providers.items():
            if not enabled:
                continue
            env_key = cls.env_key_for_provider(str(provider))
            secrets.pop(env_key, None)
            # google-ai-studio クリア時は GEMINI も落とす（同一キー）
            if provider == "google-ai-studio":
                secrets.pop(cls.KEYS["gemini"], None)
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
    def clear_provider_secret(cls, provider: str) -> None:
        cls.clear({provider: True})

    @classmethod
    def ensure_builtin_secret_aliases(cls) -> None:
        """起動時: 既存 KEYS を registry builtin id で読める状態にする（ファイル改変は最小）。

        intent: DEC-008 — OPENROUTER_API_KEY 等は既に KEYS 経由で load される。
        google-ai-studio は GEMINI_API_KEY エイリアス。追加書き込みは不要。
        """
        # load_existing の副作用確認用。将来写像書き込みが必要ならここに置く。
        cls.load_existing()

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
