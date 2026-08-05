"""ProviderRegistry の seed / slug / 削除制約テスト。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.provider_registry import (
    ANTHROPIC_PRESET_ID,
    GOOGLE_AI_STUDIO_PRESET_ID,
    OPENAI_PRESET_ID,
    OPENROUTER_PRESET_ID,
    OLLAMA_CLOUD_DEFAULT_BASE_URL,
    OLLAMA_CLOUD_PRESET_ID,
    OPENCODE_GO_DEFAULT_BASE_URL,
    OPENCODE_GO_PRESET_ID,
    ProviderEntry,
    ProviderRegistry,
)


class TestProviderRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        ProviderRegistry.FILE_PATH = Path(self._tmp.name) / "provider_registry.json"

    def tearDown(self) -> None:
        ProviderRegistry.FILE_PATH = None

    def test_ac001_load_seeds_official_builtin_providers(self) -> None:
        providers = ProviderRegistry.load()
        ids = [p.id for p in providers]
        self.assertEqual(
            ids[:6],
            [
                OPENROUTER_PRESET_ID,
                OPENAI_PRESET_ID,
                GOOGLE_AI_STUDIO_PRESET_ID,
                ANTHROPIC_PRESET_ID,
                OLLAMA_CLOUD_PRESET_ID,
                OPENCODE_GO_PRESET_ID,
            ],
        )
        by_id = {p.id: p for p in providers}
        self.assertEqual(by_id[OPENROUTER_PRESET_ID].profile, "openrouter")
        self.assertEqual(by_id[OPENAI_PRESET_ID].pricing_profile, "openai")
        self.assertEqual(by_id[GOOGLE_AI_STUDIO_PRESET_ID].pricing_profile, "google")
        self.assertEqual(by_id[ANTHROPIC_PRESET_ID].kind, "anthropic")
        self.assertEqual(
            by_id[OLLAMA_CLOUD_PRESET_ID].base_url,
            OLLAMA_CLOUD_DEFAULT_BASE_URL,
        )
        self.assertEqual(
            by_id[OPENCODE_GO_PRESET_ID].base_url,
            OPENCODE_GO_DEFAULT_BASE_URL,
        )
        self.assertEqual(by_id[OLLAMA_CLOUD_PRESET_ID].pricing_profile, "none")
        self.assertEqual(by_id[OPENCODE_GO_PRESET_ID].pricing_profile, "none")
        self.assertTrue(all(by_id[i].builtin for i in ids[:6]))

    def test_ensure_builtins_reseeds_missing(self) -> None:
        ProviderRegistry._write(
            [
                ProviderRegistry.openrouter_preset(),
            ]
        )
        providers = ProviderRegistry.load()
        self.assertEqual(
            {p.id for p in providers},
            {
                OPENROUTER_PRESET_ID,
                OPENAI_PRESET_ID,
                GOOGLE_AI_STUDIO_PRESET_ID,
                ANTHROPIC_PRESET_ID,
                OLLAMA_CLOUD_PRESET_ID,
                OPENCODE_GO_PRESET_ID,
            },
        )

    def test_ac004_existing_custom_entry_is_promoted_without_losing_others(self) -> None:
        ProviderRegistry._write(
            [
                ProviderEntry(
                    id=OLLAMA_CLOUD_PRESET_ID,
                    display_name="My Ollama",
                    kind="anthropic",
                    pricing_profile="openrouter",
                    base_url="https://wrong.example/v1",
                    profile="openrouter",
                    builtin=False,
                ),
                ProviderEntry(
                    id="my-proxy",
                    display_name="My Proxy",
                    kind="openai_compatible",
                    pricing_profile="none",
                    base_url="https://proxy.example/v1",
                    builtin=False,
                ),
            ]
        )

        providers = ProviderRegistry.load()
        by_id = {provider.id: provider for provider in providers}
        promoted = by_id[OLLAMA_CLOUD_PRESET_ID]
        self.assertEqual(promoted.display_name, "My Ollama")
        self.assertTrue(promoted.builtin)
        self.assertEqual(promoted.kind, "openai_compatible")
        self.assertEqual(promoted.pricing_profile, "none")
        self.assertEqual(promoted.base_url, OLLAMA_CLOUD_DEFAULT_BASE_URL)
        self.assertIsNone(promoted.profile)
        self.assertEqual(by_id["my-proxy"].base_url, "https://proxy.example/v1")

        persisted = json.loads(ProviderRegistry.FILE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(persisted["providers"]), 7)

    def test_cannot_delete_builtins(self) -> None:
        ProviderRegistry.load()
        for provider_id in (
            OPENROUTER_PRESET_ID,
            OPENAI_PRESET_ID,
            GOOGLE_AI_STUDIO_PRESET_ID,
            ANTHROPIC_PRESET_ID,
            OLLAMA_CLOUD_PRESET_ID,
            OPENCODE_GO_PRESET_ID,
        ):
            with self.assertRaises(ValueError):
                ProviderRegistry.delete(provider_id)

    def test_add_custom_and_allocate_slug(self) -> None:
        entry = ProviderRegistry.add(
            display_name="My Proxy",
            kind="openai_compatible",
            base_url="https://example.com/v1",
        )
        self.assertEqual(entry.id, "my-proxy")
        self.assertFalse(entry.builtin)
        self.assertEqual(entry.pricing_profile, "none")

        collision = ProviderRegistry.add(
            display_name="My Proxy",
            kind="openai_compatible",
            base_url="https://example.com/v1",
        )
        self.assertEqual(collision.id, "my-proxy-2")

    def test_reserved_id_rejected(self) -> None:
        for provider_id in ("openai", OLLAMA_CLOUD_PRESET_ID, OPENCODE_GO_PRESET_ID):
            with self.subTest(provider_id=provider_id), self.assertRaises(ValueError):
                ProviderRegistry.add(
                    display_name="X",
                    kind="openai_compatible",
                    provider_id=provider_id,
                    base_url="https://example.com/v1",
                )


if __name__ == "__main__":
    unittest.main()
