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


if __name__ == "__main__":
    unittest.main()
