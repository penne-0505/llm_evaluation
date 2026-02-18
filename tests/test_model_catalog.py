"""ModelCatalog のTTL挙動テスト"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.model_catalog import ModelCatalog


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class TestModelCatalogTTL(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.cache_path = Path(self._tmp_dir.name) / "models.json"
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
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
                    "openai": {"models": ["gpt-cache"]},
                    "anthropic": {"models": []},
                    "gemini": {"models": ["gemini-cache"]},
                    "openrouter": {"models": []},
                },
                "errors": {},
                "missing_keys": [],
            }
        )

        with (
            patch.object(ModelCatalog, "CACHE_PATH", self.cache_path),
            patch(
                "core.model_catalog.SecretsStore.load_existing",
                return_value={"gemini": "test-key"},
            ),
            patch.object(ModelCatalog, "_fetch_openai_models") as fetch_openai_mock,
            patch.object(
                ModelCatalog, "_fetch_anthropic_models"
            ) as fetch_anthropic_mock,
            patch.object(ModelCatalog, "_fetch_gemini_models") as fetch_gemini_mock,
            patch.object(
                ModelCatalog, "_fetch_openrouter_models"
            ) as fetch_openrouter_mock,
        ):
            catalog = ModelCatalog.update(force=False, ttl_seconds=3600)

        fetch_openai_mock.assert_not_called()
        fetch_anthropic_mock.assert_not_called()
        fetch_gemini_mock.assert_not_called()
        fetch_openrouter_mock.assert_not_called()
        self.assertEqual(catalog["providers"]["gemini"]["models"], ["gemini-cache"])
        self.assertEqual(catalog["providers"]["openai"]["models"], [])
        self.assertIn("OPENAI_API_KEY", catalog["missing_keys"])

    def test_fetches_when_cache_is_stale(self):
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        self._write_cache(
            {
                "updated_at": _iso(old_time),
                "providers": {
                    "openai": {"models": ["old-model"]},
                    "anthropic": {"models": []},
                    "gemini": {"models": []},
                    "openrouter": {"models": []},
                },
                "errors": {},
                "missing_keys": [],
            }
        )

        with (
            patch.object(ModelCatalog, "CACHE_PATH", self.cache_path),
            patch(
                "core.model_catalog.SecretsStore.load_existing",
                return_value={"openai": "sk-test"},
            ),
            patch.object(
                ModelCatalog, "_fetch_openai_models", return_value=["gpt-fresh"]
            ) as fetch_openai_mock,
            patch.object(
                ModelCatalog, "_fetch_anthropic_models"
            ) as fetch_anthropic_mock,
            patch.object(ModelCatalog, "_fetch_gemini_models") as fetch_gemini_mock,
            patch.object(
                ModelCatalog, "_fetch_openrouter_models"
            ) as fetch_openrouter_mock,
        ):
            catalog = ModelCatalog.update(force=False, ttl_seconds=30)

        fetch_openai_mock.assert_called_once()
        fetch_anthropic_mock.assert_not_called()
        fetch_gemini_mock.assert_not_called()
        fetch_openrouter_mock.assert_not_called()
        self.assertEqual(catalog["providers"]["openai"]["models"], ["gpt-fresh"])

    def test_force_refresh_bypasses_fresh_ttl(self):
        now = datetime.now(timezone.utc)
        self._write_cache(
            {
                "updated_at": _iso(now),
                "providers": {
                    "openai": {"models": ["gpt-cache"]},
                    "anthropic": {"models": []},
                    "gemini": {"models": []},
                    "openrouter": {"models": []},
                },
                "errors": {},
                "missing_keys": [],
            }
        )

        with (
            patch.object(ModelCatalog, "CACHE_PATH", self.cache_path),
            patch(
                "core.model_catalog.SecretsStore.load_existing",
                return_value={"openai": "sk-test"},
            ),
            patch.object(
                ModelCatalog, "_fetch_openai_models", return_value=["gpt-forced"]
            ) as fetch_openai_mock,
            patch.object(ModelCatalog, "_fetch_anthropic_models"),
            patch.object(ModelCatalog, "_fetch_gemini_models"),
            patch.object(ModelCatalog, "_fetch_openrouter_models"),
        ):
            catalog = ModelCatalog.update(force=True, ttl_seconds=99999)

        fetch_openai_mock.assert_called_once()
        self.assertEqual(catalog["providers"]["openai"]["models"], ["gpt-forced"])

    def test_ttl_hit_recomputes_missing_keys_from_current_secrets(self):
        now = datetime.now(timezone.utc)
        self._write_cache(
            {
                "updated_at": _iso(now),
                "providers": {
                    "openai": {"models": ["gpt-cache"]},
                    "anthropic": {"models": ["claude-cache"]},
                    "gemini": {"models": []},
                    "openrouter": {"models": []},
                },
                "errors": {},
                "missing_keys": [],
            }
        )

        with (
            patch.object(ModelCatalog, "CACHE_PATH", self.cache_path),
            patch("core.model_catalog.SecretsStore.load_existing", return_value={}),
        ):
            catalog = ModelCatalog.update(force=False, ttl_seconds=3600)

        self.assertEqual(catalog["providers"]["openai"]["models"], [])
        self.assertEqual(catalog["providers"]["anthropic"]["models"], [])
        self.assertIn("OPENAI_API_KEY", catalog["missing_keys"])
        self.assertIn("ANTHROPIC_API_KEY", catalog["missing_keys"])

    def test_ttl_env_value_is_used(self):
        now = datetime.now(timezone.utc)
        self._write_cache(
            {
                "updated_at": _iso(now),
                "providers": {
                    "openai": {"models": ["gpt-cache"]},
                    "anthropic": {"models": []},
                    "gemini": {"models": []},
                    "openrouter": {"models": []},
                },
                "errors": {},
                "missing_keys": [],
            }
        )

        with (
            patch.object(ModelCatalog, "CACHE_PATH", self.cache_path),
            patch(
                "core.model_catalog.SecretsStore.load_existing",
                return_value={"openai": "sk-test"},
            ),
            patch.object(ModelCatalog, "_fetch_openai_models") as fetch_openai_mock,
            patch.dict(
                os.environ,
                {ModelCatalog.TTL_ENV_NAME: "7200"},
                clear=False,
            ),
        ):
            catalog = ModelCatalog.update(force=False)

        fetch_openai_mock.assert_not_called()
        self.assertEqual(catalog["providers"]["openai"]["models"], ["gpt-cache"])


if __name__ == "__main__":
    unittest.main()
