"""model_parameter_support と OpenAICompatible temperature omit のテスト。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from adapters.openai_compatible_adapter import OpenAICompatibleAdapter
from core import model_parameter_support as mps


class TestModelParameterSupport(unittest.TestCase):
    def tearDown(self) -> None:
        mps.set_openrouter_supported_parameters_cache(None)

    def test_openai_gpt56_luna_disallows_temperature(self) -> None:
        self.assertFalse(
            mps.allows("openai", "openai/gpt-5.6-luna", "temperature")
        )
        self.assertFalse(mps.allows("openai", "gpt-5.6-luna", "temperature"))
        self.assertFalse(mps.allows("openai", "gpt-5", "temperature"))
        self.assertFalse(mps.allows("openai", "o3-mini", "temperature"))

    def test_openai_gpt4o_allows_temperature(self) -> None:
        self.assertTrue(mps.allows("openai", "gpt-4o", "temperature"))
        self.assertTrue(mps.allows("openai", "openai/gpt-4o-mini", "temperature"))

    def test_google_gemini3_disallows_temperature(self) -> None:
        self.assertFalse(
            mps.allows("google-ai-studio", "gemini-3.5-flash", "temperature")
        )
        self.assertFalse(
            mps.allows(
                "openrouter",
                "openrouter/google/gemini-3.5-flash",
                "temperature",
            )
        )

    def test_openrouter_catalog_supported_parameters(self) -> None:
        mps.set_openrouter_supported_parameters_cache(
            {
                "anthropic/claude-sonnet-5": {"max_tokens", "tools"},
                "google/gemini-2.5-flash": {"temperature", "max_tokens"},
            }
        )
        self.assertFalse(
            mps.allows(
                "openrouter",
                "openrouter/anthropic/claude-sonnet-5",
                "temperature",
            )
        )
        self.assertTrue(
            mps.allows(
                "openrouter",
                "openrouter/google/gemini-2.5-flash",
                "temperature",
            )
        )
        # gemini-3: static unsafe wins even if catalog lists temperature
        mps.set_openrouter_supported_parameters_cache(
            {
                "google/gemini-3.5-flash": {"temperature", "max_tokens"},
            }
        )
        self.assertFalse(
            mps.allows(
                "openrouter",
                "openrouter/google/gemini-3.5-flash",
                "temperature",
            )
        )

    def test_unknown_temperature_omitted(self) -> None:
        self.assertFalse(
            mps.allows("custom-proxy", "mystery-model", "temperature")
        )

    def test_ac002_reasoning_effort_uses_xhigh_ceiling_and_high_fallback(self) -> None:
        cases = [
            ("openai", "openai/gpt-5.6-luna", "xhigh"),
            ("openai", "openai/gpt-5.1-codex-max", "xhigh"),
            ("openai", "openai/gpt-5.1", "high"),
            ("openai", "openai/gpt-5-pro", "high"),
            ("google-ai-studio", "google-ai-studio/gemini-3.5-flash", "high"),
            ("google-ai-studio", "google-ai-studio/gemini-2.5-pro", "high"),
            ("anthropic", "anthropic/claude-opus-4-8", "xhigh"),
            ("anthropic", "anthropic/claude-sonnet-5", "xhigh"),
            ("anthropic", "anthropic/claude-sonnet-4-6", "high"),
            ("anthropic", "anthropic/claude-opus-4-5-20251101", "high"),
        ]
        for provider, model, expected in cases:
            with self.subTest(provider=provider, model=model):
                self.assertEqual(
                    mps.reasoning_effort_for_model(provider, model), expected
                )

    def test_inv002_reasoning_effort_omits_unsupported_and_never_returns_max(self) -> None:
        unsupported = [
            ("openai", "openai/gpt-4o"),
            ("google-ai-studio", "google-ai-studio/gemini-2.0-flash"),
            ("anthropic", "anthropic/claude-sonnet-4-5-20250929"),
            ("custom-proxy", "custom-proxy/reasoning-model"),
        ]
        for provider, model in unsupported:
            with self.subTest(provider=provider, model=model):
                self.assertIsNone(mps.reasoning_effort_for_model(provider, model))

        known = [
            ("openai", "openai/gpt-5.6-sol"),
            ("anthropic", "anthropic/claude-opus-4-7"),
            ("google-ai-studio", "google-ai-studio/gemini-3.1-pro-preview"),
        ]
        self.assertNotIn(
            "max",
            [mps.reasoning_effort_for_model(provider, model) for provider, model in known],
        )

    def test_ac002_openai_compatible_adapter_forwards_reasoning_effort_top_level(self) -> None:
        for provider_id, model, expected in [
            ("openai", "openai/gpt-5.6-luna", "xhigh"),
            (
                "google-ai-studio",
                "google-ai-studio/gemini-3.5-flash",
                "high",
            ),
        ]:
            with self.subTest(provider=provider_id):
                adapter = OpenAICompatibleAdapter(
                    provider_id=provider_id,
                    api_key="sk-test-key-for-openai-adapter",
                    base_url="https://example.invalid/v1",
                )
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "ok"
                mock_response.choices[0].message.reasoning = None
                mock_response.choices[0].message.reasoning_details = None
                mock_response.usage = None
                mock_client.chat.completions.create.return_value = mock_response
                adapter._client = mock_client

                extra_params = adapter.reasoning_effort_params(model)
                self.assertEqual(extra_params, {"reasoning_effort": expected})
                adapter.complete_with_model_result(
                    model=model,
                    system_prompt="sys",
                    user_prompt="user",
                    extra_params=extra_params,
                )
                kwargs = mock_client.chat.completions.create.call_args.kwargs
                self.assertEqual(kwargs.get("reasoning_effort"), expected)
                self.assertNotIn("extra_body", kwargs)

    def test_ac003_custom_openai_compatible_adapter_omits_effort(self) -> None:
        adapter = OpenAICompatibleAdapter(
            provider_id="custom-proxy",
            api_key="sk-test-key-for-custom-adapter",
            base_url="https://example.invalid/v1",
        )
        self.assertIsNone(
            adapter.reasoning_effort_params("custom-proxy/reasoning-model")
        )

    def test_openai_compatible_adapter_omits_temperature_for_gpt56(self) -> None:
        adapter = OpenAICompatibleAdapter(
            provider_id="openai",
            api_key="sk-test-key-for-openai-adapter",
            base_url="https://api.openai.com/v1",
        )
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        mock_response.choices[0].message.reasoning = None
        mock_response.choices[0].message.reasoning_details = None
        mock_response.usage = None
        mock_client.chat.completions.create.return_value = mock_response
        adapter._client = mock_client

        adapter.complete_with_model_result(
            model="openai/gpt-5.6-luna",
            system_prompt="sys",
            user_prompt="user",
            temperature=0.6,
        )
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertNotIn("temperature", kwargs)
        self.assertEqual(kwargs["model"], "gpt-5.6-luna")
        self.assertIn("max_completion_tokens", kwargs)

    def test_openai_compatible_adapter_sends_temperature_for_gpt4o(self) -> None:
        adapter = OpenAICompatibleAdapter(
            provider_id="openai",
            api_key="sk-test-key-for-openai-adapter",
            base_url="https://api.openai.com/v1",
        )
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        mock_response.choices[0].message.reasoning = None
        mock_response.choices[0].message.reasoning_details = None
        mock_response.usage = None
        mock_client.chat.completions.create.return_value = mock_response
        adapter._client = mock_client

        adapter.complete_with_model_result(
            model="openai/gpt-4o",
            system_prompt="sys",
            user_prompt="user",
            temperature=0.6,
        )
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs.get("temperature"), 0.6)

    def test_ac003_opencode_go_uses_gateway_chat_completion_shape(self) -> None:
        adapter = OpenAICompatibleAdapter(
            provider_id="opencode-go",
            api_key="opencode-test-key",
            base_url="https://opencode.ai/zen/go/v1",
        )
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        mock_response.choices[0].message.reasoning = None
        mock_response.choices[0].message.reasoning_details = None
        mock_response.usage = None
        mock_client.chat.completions.create.return_value = mock_response
        adapter._client = mock_client

        adapter.complete_with_model_result(
            model="opencode-go/gpt-5.6-luna",
            system_prompt="sys",
            user_prompt="user",
            temperature=0.6,
            max_tokens=321,
        )

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-5.6-luna")
        self.assertEqual(kwargs["max_tokens"], 321)
        self.assertNotIn("max_completion_tokens", kwargs)
        self.assertNotIn("temperature", kwargs)


if __name__ == "__main__":
    unittest.main()
