"""ProviderRegistry の seed / slug / 削除制約テスト。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.provider_registry import (
    ANTHROPIC_PRESET_ID,
    GOOGLE_AI_STUDIO_PRESET_ID,
    OPENAI_PRESET_ID,
    OPENROUTER_PRESET_ID,
    ProviderRegistry,
)


class TestProviderRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        ProviderRegistry.FILE_PATH = Path(self._tmp.name) / "provider_registry.json"

    def tearDown(self) -> None:
        ProviderRegistry.FILE_PATH = None

    def test_load_seeds_builtin_set_a(self) -> None:
        providers = ProviderRegistry.load()
        ids = [p.id for p in providers]
        self.assertEqual(
            ids[:4],
            [
                OPENROUTER_PRESET_ID,
                OPENAI_PRESET_ID,
                GOOGLE_AI_STUDIO_PRESET_ID,
                ANTHROPIC_PRESET_ID,
            ],
        )
        by_id = {p.id: p for p in providers}
        self.assertEqual(by_id[OPENROUTER_PRESET_ID].profile, "openrouter")
        self.assertEqual(by_id[OPENAI_PRESET_ID].pricing_profile, "openai")
        self.assertEqual(by_id[GOOGLE_AI_STUDIO_PRESET_ID].pricing_profile, "google")
        self.assertEqual(by_id[ANTHROPIC_PRESET_ID].kind, "anthropic")
        self.assertTrue(all(by_id[i].builtin for i in ids[:4]))

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
            },
        )

    def test_cannot_delete_builtins(self) -> None:
        ProviderRegistry.load()
        for provider_id in (
            OPENROUTER_PRESET_ID,
            OPENAI_PRESET_ID,
            GOOGLE_AI_STUDIO_PRESET_ID,
            ANTHROPIC_PRESET_ID,
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
        with self.assertRaises(ValueError):
            ProviderRegistry.add(
                display_name="X",
                kind="openai_compatible",
                provider_id="openai",
                base_url="https://example.com/v1",
            )


if __name__ == "__main__":
    unittest.main()
