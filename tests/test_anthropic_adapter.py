"""AnthropicAdapter のユニットテスト（モックのみ・ライブ API なし）。"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.anthropic_adapter import AnthropicAdapter
from adapters.base import LLMError, NativeToolCall


def _make_adapter() -> AnthropicAdapter:
    adapter = AnthropicAdapter(api_key="sk-ant-test-key-long-enough", provider_id="anthropic")
    adapter._client = MagicMock()
    return adapter


def test_is_available_requires_key_length():
    assert AnthropicAdapter(api_key=None).is_available() is False
    assert AnthropicAdapter(api_key="short").is_available() is False
    assert AnthropicAdapter(api_key="x" * 11).is_available() is True


def test_complete_returns_text_usage_and_api_reasoning():
    """AC-003 / DEC-006: thinking ブロック → api_reasoning、text + usage。"""
    adapter = _make_adapter()
    thinking = SimpleNamespace(type="thinking", thinking="plan step one")
    text_block = SimpleNamespace(type="text", text="final answer")
    usage = SimpleNamespace(
        input_tokens=12,
        output_tokens=34,
        cache_creation_input_tokens=None,
        cache_read_input_tokens=None,
    )
    response = SimpleNamespace(content=[thinking, text_block], usage=usage)
    adapter._client.messages.create.return_value = response

    result = adapter.complete_with_model_result(
        model="anthropic/claude-sonnet-4-5-20250929",
        system_prompt="sys",
        user_prompt="user",
        temperature=0.0,
        max_tokens=256,
        extra_params={"thinking": {"type": "enabled", "budget_tokens": 1024}},
    )

    assert result.text == "final answer"
    assert result.api_reasoning == "plan step one"
    assert result.usage is not None
    assert result.usage.provider == "anthropic"
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 34
    assert result.usage.total_tokens == 46
    assert result.usage.duration_ms is not None

    call_kwargs = adapter._client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"
    assert call_kwargs["system"] == "sys"
    assert call_kwargs["messages"] == [{"role": "user", "content": "user"}]
    assert call_kwargs["thinking"] == {"type": "enabled", "budget_tokens": 1024}
    assert call_kwargs["max_tokens"] == 256


def test_native_tools_returns_native_tool_call():
    """AC-003 / DEC-006: tool_use → NativeToolCall、OpenAI tools/messages 変換。"""
    adapter = _make_adapter()
    tool_use = SimpleNamespace(
        type="tool_use",
        id="toolu_1",
        name="get_weather",
        input={"city": "Tokyo"},
    )
    text_block = SimpleNamespace(type="text", text="calling tool")
    usage = SimpleNamespace(input_tokens=5, output_tokens=7)
    adapter._client.messages.create.return_value = SimpleNamespace(
        content=[text_block, tool_use], usage=usage
    )

    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                },
            },
        }
    ]
    openai_messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Weather in Tokyo?"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_prev",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"city": "Osaka"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_prev",
            "content": '{"temp": 20}',
        },
        {"role": "user", "content": "and Tokyo?"},
    ]

    result = adapter.complete_with_model_native_tools(
        model="anthropic/claude-3-5-sonnet-latest",
        messages=openai_messages,
        tools=openai_tools,
        temperature=0.0,
        max_tokens=1024,
    )

    assert result.content == "calling tool"
    assert len(result.tool_calls) == 1
    assert isinstance(result.tool_calls[0], NativeToolCall)
    assert result.tool_calls[0].id == "toolu_1"
    assert result.tool_calls[0].name == "get_weather"
    assert result.tool_calls[0].arguments == {"city": "Tokyo"}
    assert result.usage is not None
    assert result.usage.input_tokens == 5

    call_kwargs = adapter._client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-3-5-sonnet-latest"
    assert call_kwargs["system"] == "You are helpful."
    assert call_kwargs["tools"] == [
        {
            "name": "get_weather",
            "description": "Get weather",
            "input_schema": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
            },
        }
    ]
    # assistant tool_calls → tool_use、tool → tool_result
    roles = [m["role"] for m in call_kwargs["messages"]]
    assert "assistant" in roles
    assert any(
        isinstance(m.get("content"), list)
        and m["content"]
        and m["content"][0].get("type") == "tool_result"
        for m in call_kwargs["messages"]
        if m["role"] == "user"
    )


def test_missing_key_raises_llm_error():
    adapter = AnthropicAdapter(api_key=None)
    try:
        adapter.complete_with_model_result(
            model="claude-test",
            system_prompt="s",
            user_prompt="u",
        )
        assert False, "LLMError expected"
    except LLMError as e:
        assert "APIキー" in str(e)


def test_supports_native_tools():
    assert AnthropicAdapter(api_key="x" * 11).supports_native_tools() is True


def test_provider_id_overrides_provider_attr():
    adapter = AnthropicAdapter(
        api_key="x" * 11, provider_id="my-anthropic-proxy", base_url="https://example.com"
    )
    assert adapter.PROVIDER == "my-anthropic-proxy"
