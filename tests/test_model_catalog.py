"""ModelCatalog のTTL挙動テスト"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.model_catalog import ModelCatalog
from core.provider_registry import ProviderRegistry


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class TestModelCatalogTTL(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.cache_path = Path(self._tmp_dir.name) / "models.json"
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._registry_path = Path(self._tmp_dir.name) / "provider_registry.json"
        self._orig_registry_path = ProviderRegistry.FILE_PATH
        ProviderRegistry.FILE_PATH = self._registry_path

    def tearDown(self) -> None:
        ProviderRegistry.FILE_PATH = self._orig_registry_path
        self._tmp_dir.cleanup()

    def _write_cache(self, payload: dict) -> None:
        self.cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def test_uses_cache_when_ttl_is_fresh(self):
        now = datetime.now(timezone.utc)
        self._write_cache(
            {
                "updated_at": _iso(now),
                "providers": {
                    "openrouter": {"models": []},
                    "lmstudio": {"models": ["lmstudio/cache-model"]},
                },
                "errors": {},
                "missing_keys": [],
            }
        )

        with (
            patch.object(ModelCatalog, "CACHE_PATH", self.cache_path),
            patch(
                "core.model_catalog.SecretsStore.load_existing",
                return_value={},
            ),
            patch(
                "core.model_catalog.ProviderConfigStore.load_provider",
                return_value={"base_url": "http://127.0.0.1:1234/v1"},
            ),
            patch.object(
                ModelCatalog, "_fetch_openrouter_models"
            ) as fetch_openrouter_mock,
            patch.object(
                ModelCatalog, "_fetch_lmstudio_models"
            ) as fetch_lmstudio_mock,
        ):
            catalog = ModelCatalog.update(force=False, ttl_seconds=3600)

        fetch_openrouter_mock.assert_not_called()
        fetch_lmstudio_mock.assert_not_called()
        self.assertEqual(catalog["providers"]["lmstudio"]["models"], ["lmstudio/cache-model"])
        self.assertEqual(catalog["providers"]["openrouter"]["models"], [])
        self.assertIn("OPENROUTER_API_KEY", catalog["missing_keys"])

    def test_fetches_when_cache_is_stale(self):
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        self._write_cache(
            {
                "updated_at": _iso(old_time),
                "providers": {
                    "openrouter": {"models": ["old-model"]},
                    "lmstudio": {"models": []},
                },
                "errors": {},
                "missing_keys": [],
            }
        )

        with (
            patch.object(ModelCatalog, "CACHE_PATH", self.cache_path),
            patch(
                "core.model_catalog.SecretsStore.load_existing",
                return_value={"openrouter": "sk-or-test"},
            ),
            patch(
                "core.model_catalog.ProviderConfigStore.load_provider",
                return_value={},
            ),
            patch.object(
                ModelCatalog, "_fetch_openrouter_models", return_value=[{"id": "openrouter/new-model"}]
            ) as fetch_openrouter_mock,
            patch.object(ModelCatalog, "_fetch_lmstudio_models") as fetch_lmstudio_mock,
        ):
            catalog = ModelCatalog.update(force=False, ttl_seconds=30)

        fetch_openrouter_mock.assert_called_once()
        fetch_lmstudio_mock.assert_not_called()
        self.assertEqual(catalog["providers"]["openrouter"]["models"], ["openrouter/new-model"])

    def test_force_refresh_bypasses_fresh_ttl(self):
        now = datetime.now(timezone.utc)
        self._write_cache(
            {
                "updated_at": _iso(now),
                "providers": {
                    "openrouter": {"models": ["or-cache"]},
                    "lmstudio": {"models": []},
                },
                "errors": {},
                "missing_keys": [],
            }
        )

        with (
            patch.object(ModelCatalog, "CACHE_PATH", self.cache_path),
            patch(
                "core.model_catalog.SecretsStore.load_existing",
                return_value={"openrouter": "sk-or-test"},
            ),
            patch.object(
                ModelCatalog, "_fetch_openrouter_models", return_value=[{"id": "openrouter/forced"}]
            ) as fetch_openrouter_mock,
            patch.object(ModelCatalog, "_fetch_lmstudio_models"),
        ):
            catalog = ModelCatalog.update(force=True, ttl_seconds=99999)

        fetch_openrouter_mock.assert_called_once()
        self.assertEqual(catalog["providers"]["openrouter"]["models"], ["openrouter/forced"])

    def test_ttl_hit_recomputes_missing_keys_from_current_secrets(self):
        now = datetime.now(timezone.utc)
        self._write_cache(
            {
                "updated_at": _iso(now),
                "providers": {
                    "openrouter": {"models": ["or-cache"]},
                    "lmstudio": {"models": ["lmstudio/cache"]},
                },
                "errors": {},
                "missing_keys": [],
            }
        )

        with (
            patch.object(ModelCatalog, "CACHE_PATH", self.cache_path),
            patch("core.model_catalog.SecretsStore.load_existing", return_value={}),
            patch(
                "core.model_catalog.ProviderConfigStore.load_provider",
                return_value={},
            ),
        ):
            catalog = ModelCatalog.update(force=False, ttl_seconds=3600)

        self.assertEqual(catalog["providers"]["openrouter"]["models"], [])
        self.assertEqual(catalog["providers"]["lmstudio"]["models"], [])
        self.assertIn("OPENROUTER_API_KEY", catalog["missing_keys"])

    def test_ttl_env_value_is_used(self):
        now = datetime.now(timezone.utc)
        self._write_cache(
            {
                "updated_at": _iso(now),
                "providers": {
                    "openrouter": {"models": ["or-cache"]},
                    "lmstudio": {"models": []},
                },
                "errors": {},
                "missing_keys": [],
            }
        )

        with (
            patch.object(ModelCatalog, "CACHE_PATH", self.cache_path),
            patch(
                "core.model_catalog.SecretsStore.load_existing",
                return_value={"openrouter": "sk-or-test"},
            ),
            patch.object(ModelCatalog, "_fetch_openrouter_models") as fetch_openrouter_mock,
            patch.dict(
                os.environ,
                {ModelCatalog.TTL_ENV_NAME: "7200"},
                clear=False,
            ),
        ):
            catalog = ModelCatalog.update(force=False)

        fetch_openrouter_mock.assert_not_called()
        self.assertEqual(catalog["providers"]["openrouter"]["models"], ["or-cache"])

    def test_lmstudio_models_are_prefixed_and_do_not_require_token(self):
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        self._write_cache(
            {
                "updated_at": _iso(old_time),
                "providers": {
                    "openrouter": {"models": []},
                    "lmstudio": {"models": []},
                },
                "errors": {},
                "missing_keys": [],
            }
        )

        with (
            patch.object(ModelCatalog, "CACHE_PATH", self.cache_path),
            patch("core.model_catalog.SecretsStore.load_existing", return_value={}),
            patch(
                "core.model_catalog.ProviderConfigStore.load_provider",
                return_value={"base_url": "http://127.0.0.1:1234/v1"},
            ),
            patch.object(
                ModelCatalog,
                "_fetch_lmstudio_models",
                return_value=[{"id": "lmstudio/openai/gpt-oss-20b"}],
            ) as fetch_lmstudio_mock,
        ):
            catalog = ModelCatalog.update(force=True, ttl_seconds=30)

        fetch_lmstudio_mock.assert_called_once()
        self.assertEqual(
            catalog["providers"]["lmstudio"]["models"],
            ["lmstudio/openai/gpt-oss-20b"],
        )
        self.assertNotIn("LMSTUDIO_API_TOKEN", catalog["missing_keys"])

    def test_lmstudio_fallback_to_cache_when_fetch_fails(self):
        """LM Studio モデル取得に失敗した場合、キャッシュから復元されることを確認"""
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        self._write_cache(
            {
                "updated_at": _iso(old_time),
                "providers": {
                    "openrouter": {"models": ["openrouter/gpt-4o"]},
                    "lmstudio": {
                        "models": ["lmstudio/gemma"],
                        "entries": [{"id": "lmstudio/gemma"}],
                    },
                },
                "errors": {},
                "missing_keys": [],
            }
        )

        with (
            patch.object(ModelCatalog, "CACHE_PATH", self.cache_path),
            patch(
                "core.model_catalog.SecretsStore.load_existing",
                return_value={"openrouter": "sk-or-test"},
            ),
            patch(
                "core.model_catalog.ProviderConfigStore.load_provider",
                return_value={"base_url": "http://127.0.0.1:1234/v1"},
            ),
            patch.object(
                ModelCatalog, "_fetch_openrouter_models", return_value=[{"id": "openrouter/gpt-5.4"}]
            ) as fetch_openrouter_mock,
            patch.object(
                ModelCatalog,
                "_fetch_lmstudio_models",
                side_effect=RuntimeError("connection refused"),
            ) as fetch_lmstudio_mock,
        ):
            catalog = ModelCatalog.update(force=True, ttl_seconds=30)

        fetch_openrouter_mock.assert_called_once()
        fetch_lmstudio_mock.assert_called_once()
        # OpenRouter の新しいモデルが反映される
        self.assertEqual(catalog["providers"]["openrouter"]["models"], ["openrouter/gpt-5.4"])
        # LM Studio はキャッシュから復元される
        self.assertEqual(
            catalog["providers"]["lmstudio"]["models"],
            ["lmstudio/gemma"],
        )
        self.assertIn("lmstudio", catalog["errors"])


if __name__ == "__main__":
    unittest.main()
