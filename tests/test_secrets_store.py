"""Official provider API key aliases and secret persistence tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from core.secrets_store import SecretsStore


def test_ac002_official_cloud_provider_env_aliases() -> None:
    assert SecretsStore.env_key_for_provider("ollama-cloud") == "OLLAMA_API_KEY"
    assert SecretsStore.env_key_for_provider("opencode-go") == "OPENCODE_API_KEY"
    assert SecretsStore.provider_id_from_env_key("OLLAMA_API_KEY") == "ollama-cloud"
    assert SecretsStore.provider_id_from_env_key("OPENCODE_API_KEY") == "opencode-go"


def test_ac002_official_environment_keys_are_loaded_without_generic_aliases() -> None:
    with tempfile.TemporaryDirectory() as tmp, patch.object(
        SecretsStore, "FILE_PATH", Path(tmp) / "secrets.toml"
    ), patch.dict(
        os.environ,
        {
            "OLLAMA_API_KEY": "ollama-test-key",
            "OPENCODE_API_KEY": "opencode-test-key",
        },
        clear=True,
    ):
        existing = SecretsStore.load_existing()

    assert existing["ollama-cloud"] == "ollama-test-key"
    assert existing["opencode-go"] == "opencode-test-key"


def test_ac002_ui_persistence_uses_official_secret_names() -> None:
    with tempfile.TemporaryDirectory() as tmp, patch.object(
        SecretsStore, "FILE_PATH", Path(tmp) / "secrets.toml"
    ), patch.dict(os.environ, {}, clear=True):
        SecretsStore.save_provider_secret("ollama-cloud", "ollama-ui-test")
        SecretsStore.save_provider_secret("opencode-go", "opencode-ui-test")
        persisted = SecretsStore.FILE_PATH.read_text(encoding="utf-8")
        loaded = SecretsStore.load_existing()

    assert 'OLLAMA_API_KEY = "ollama-ui-test"' in persisted
    assert 'OPENCODE_API_KEY = "opencode-ui-test"' in persisted
    assert "PROVIDER_OLLAMA_CLOUD_API_KEY" not in persisted
    assert "PROVIDER_OPENCODE_GO_API_KEY" not in persisted
    assert loaded["ollama-cloud"] == "ollama-ui-test"
    assert loaded["opencode-go"] == "opencode-ui-test"
