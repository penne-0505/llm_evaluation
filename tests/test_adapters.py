"""アダプタ層のテスト"""

import os
import sys
from unittest.mock import patch, MagicMock

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters import (
    get_adapter_for_model,
    get_all_available_adapters,
    OpenRouterAdapter,
    LMStudioAdapter,
    LLMError,
)


def test_adapter_factory():
    """アダプタファクトリ関数のテスト"""
    print("\n=== アダプタファクトリテスト ===")

    test_cases = [
        ("openrouter/openai/gpt-4o", OpenRouterAdapter),
        ("or/anthropic/claude-3-opus", OpenRouterAdapter),
        ("lmstudio/openai/gpt-oss-20b", LMStudioAdapter),
        ("gpt-4o", None),
        ("claude-sonnet-4-5-20250929", None),
        ("gemini-1.5-pro", None),
        ("unknown-model", None),
    ]

    for model_name, expected_type in test_cases:
        adapter = get_adapter_for_model(model_name)
        if expected_type is None:
            assert adapter is None, f"{model_name}: Noneが期待される"
            print(f"✓ {model_name} → None")
        else:
            assert isinstance(adapter, expected_type), (
                f"{model_name}: {expected_type.__name__}が期待される"
            )
            print(f"✓ {model_name} → {type(adapter).__name__}")

    print("アダプタファクトリテスト完了")


def test_adapter_availability_without_keys():
    """APIキーなし時のアダプタ可用性テスト"""
    print("\n=== APIキーなし時の可用性テスト ===")

    # 環境変数をクリア
    with patch.dict(os.environ, {}, clear=True):
        openrouter = OpenRouterAdapter()

        assert not openrouter.is_available(), "OpenRouter: APIキーなしでFalse"

        print("✓ OpenRouter: unavailable (no key)")

    print("APIキーなし時の可用性テスト完了")


def test_adapter_availability_with_keys():
    """APIキーあり時のアダプタ可用性テスト"""
    print("\n=== APIキーあり時の可用性テスト ===")

    test_env = {
        "OPENROUTER_API_KEY": "sk-or-v1-test12345678901234567890",
    }

    with patch.dict(os.environ, test_env, clear=True):
        openrouter = OpenRouterAdapter()

        assert openrouter.is_available(), "OpenRouter: 有効なAPIキーでTrue"

        print("✓ OpenRouter: available (with key)")

    print("APIキーあり時の可用性テスト完了")


def test_error_handling():
    """エラーハンドリングテスト"""
    print("\n=== エラーハンドリングテスト ===")

    with patch.dict(os.environ, {}, clear=True):
        openrouter = OpenRouterAdapter()

        try:
            openrouter.complete("system", "user")
            assert False, "APIキーなしでLLMErrorが発生すべき"
        except LLMError as e:
            print(f"✓ OpenRouter: APIキーなしでLLMError発生 - {e}")

    print("エラーハンドリングテスト完了")


def test_get_all_available_adapters():
    """全アダプタ取得関数のテスト"""
    print("\n=== 全アダプタ取得テスト ===")

    # APIキーなし + LM Studio base_url なし
    with (
        patch.dict(os.environ, {}, clear=True),
        patch(
            "adapters.lmstudio_adapter.ProviderConfigStore.load_provider",
            return_value={},
        ),
    ):
        adapters = get_all_available_adapters()
        assert len(adapters) == 0, "APIキーなしで空の辞書"
        print("✓ APIキーなし: 空の辞書を返す")

    # APIキーあり（openrouterのみ）
    with (
        patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-test12345678901234567890"}, clear=True),
        patch(
            "adapters.lmstudio_adapter.ProviderConfigStore.load_provider",
            return_value={},
        ),
    ):
        adapters = get_all_available_adapters()
        assert len(adapters) == 1, "1つのAPIキーで1つのアダプタ"
        assert "openrouter" in adapters, "OpenRouterが含まれる"
        print("✓ APIキー1つ: openrouterのみ含まれる")

    print("全アダプタ取得テスト完了")


def test_lmstudio_adapter_availability_with_base_url():
    """LM Studio は base_url があれば利用可能"""
    print("\n=== LM Studio 可用性テスト ===")

    with patch(
        "adapters.lmstudio_adapter.ProviderConfigStore.load_provider",
        return_value={"base_url": "http://127.0.0.1:1234/v1"},
    ):
        adapter = LMStudioAdapter()
        assert adapter.is_available(), "LM Studio: base_url 設定でTrue"
        print("✓ LM Studio: available (with base_url)")


def test_is_reasoning_opt_in_openrouter():
    """OpenRouterAdapter の is_reasoning_opt_in テスト"""
    print("\n=== OpenRouter reasoning opt-in テスト ===")

    adapter = OpenRouterAdapter(api_key="sk-or-v1-test12345678901234567890")

    # キャッシュをクリア
    OpenRouterAdapter._models_cache = None

    mock_data = {
        "data": [
            {
                "id": "anthropic/claude-3.7-sonnet",
                "supported_parameters": ["reasoning", "temperature"],
            },
            {
                "id": "anthropic/claude-3.7-sonnet:thinking",
                "supported_parameters": ["reasoning", "temperature"],
            },
            {
                "id": "openai/gpt-4o",
                "supported_parameters": ["temperature"],
            },
        ]
    }

    with patch("adapters.openrouter_adapter.requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_data
        mock_get.return_value.raise_for_status = MagicMock()

        # reasoning サポートかつ :thinking ではない → True
        assert adapter.is_reasoning_opt_in("anthropic/claude-3.7-sonnet") is True
        print("✓ anthropic/claude-3.7-sonnet → True")

        # :thinking suffix → always on → False
        assert adapter.is_reasoning_opt_in("anthropic/claude-3.7-sonnet:thinking") is False
        print("✓ anthropic/claude-3.7-sonnet:thinking → False")

        # reasoning 非サポート → False
        assert adapter.is_reasoning_opt_in("openai/gpt-4o") is False
        print("✓ openai/gpt-4o → False")

        # 不明なモデル → False
        assert adapter.is_reasoning_opt_in("unknown/model") is False
        print("✓ unknown/model → False")

    # キャッシュが使われていることを確認
    with patch("adapters.openrouter_adapter.requests.get") as mock_get:
        adapter.is_reasoning_opt_in("anthropic/claude-3.7-sonnet")
        mock_get.assert_not_called()
        print("✓ 2回目はキャッシュが使われる")

    OpenRouterAdapter._models_cache = None
    print("OpenRouter reasoning opt-in テスト完了")


def test_is_reasoning_opt_in_lmstudio():
    """LMStudioAdapter の is_reasoning_opt_in テスト"""
    print("\n=== LM Studio reasoning opt-in テスト ===")

    with patch(
        "adapters.lmstudio_adapter.ProviderConfigStore.load_provider",
        return_value={"base_url": "http://127.0.0.1:1234/v1"},
    ):
        adapter = LMStudioAdapter()

    # キャッシュをクリア
    LMStudioAdapter._models_cache = None

    mock_data = {
        "models": [
            {
                "key": "qwen3-30b-a3b",
                "capabilities": {"reasoning": {"default": "off"}},
            },
            {
                "key": "deepseek-r1",
                "capabilities": {"reasoning": {"default": "on"}},
            },
            {
                "key": "llama-3",
                "capabilities": {"chat": True},
            },
        ]
    }

    with patch("adapters.lmstudio_adapter.requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_data
        mock_get.return_value.raise_for_status = MagicMock()

        # default: off → True
        assert adapter.is_reasoning_opt_in("qwen3-30b-a3b") is True
        print("✓ qwen3-30b-a3b → True")

        # default: on → False
        assert adapter.is_reasoning_opt_in("deepseek-r1") is False
        print("✓ deepseek-r1 → False")

        # reasoning capability なし → False
        assert adapter.is_reasoning_opt_in("llama-3") is False
        print("✓ llama-3 → False")

        # 不明なモデル → False
        assert adapter.is_reasoning_opt_in("unknown-model") is False
        print("✓ unknown-model → False")

    # キャッシュが使われていることを確認
    with patch("adapters.lmstudio_adapter.requests.get") as mock_get:
        adapter.is_reasoning_opt_in("qwen3-30b-a3b")
        mock_get.assert_not_called()
        print("✓ 2回目はキャッシュが使われる")

    LMStudioAdapter._models_cache = None
    print("LM Studio reasoning opt-in テスト完了")


def test_extra_body_passed_to_openrouter():
    """extra_params が OpenAI SDK の extra_body として渡される"""
    print("\n=== OpenRouter extra_body テスト ===")

    adapter = OpenRouterAdapter(api_key="sk-or-v1-test12345678901234567890")
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"task_name":"test","task_type":"fact","score":{},"total_score":0}'
    mock_response.choices[0].message.reasoning = None
    mock_response.choices[0].message.reasoning_details = None
    mock_response.usage = None
    mock_client.chat.completions.create.return_value = mock_response
    adapter._client = mock_client

    adapter.complete_with_model_result(
        model="anthropic/claude-3.7-sonnet",
        system_prompt="sys",
        user_prompt="user",
        extra_params={"reasoning": {"effort": "medium"}},
    )

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert "extra_body" in call_kwargs, "extra_body が含まれる"
    assert call_kwargs["extra_body"] == {"reasoning": {"effort": "medium"}}, "extra_body の内容が正しい"
    assert "reasoning" not in call_kwargs, "reasoning がトップレベルに含まれない"
    print("✓ complete_with_model_result: extra_body として渡される")

    # native tools 版も確認
    mock_client.chat.completions.create.reset_mock()
    adapter.complete_with_model_native_tools(
        model="anthropic/claude-3.7-sonnet",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        extra_params={"reasoning": {"effort": "medium"}},
    )
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert "extra_body" in call_kwargs, "native_tools: extra_body が含まれる"
    assert call_kwargs["extra_body"] == {"reasoning": {"effort": "medium"}}, "native_tools: extra_body の内容が正しい"
    print("✓ complete_with_model_native_tools: extra_body として渡される")

    print("OpenRouter extra_body テスト完了")


def _make_openrouter_adapter_with_message(
    *,
    content: str,
    reasoning=None,
    reasoning_details=None,
):
    adapter = OpenRouterAdapter(api_key="sk-or-v1-test12345678901234567890")
    mock_client = MagicMock()
    mock_response = MagicMock()
    message = MagicMock()
    message.content = content
    message.reasoning = reasoning
    message.reasoning_details = reasoning_details
    message.model_extra = None
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = message
    mock_response.usage = None
    mock_client.chat.completions.create.return_value = mock_response
    adapter._client = mock_client
    return adapter


def test_openrouter_extracts_message_reasoning():
    """AC-001 / DEC-002: message.reasoning を CompletionResult.api_reasoning へ"""
    print("\n=== OpenRouter message.reasoning 抽出 ===")
    judge_json = (
        '{"task_name":"test","task_type":"fact","score":{},'
        '"total_score":0,"confidence":"high"}'
    )
    adapter = _make_openrouter_adapter_with_message(
        content=judge_json,
        reasoning="  internal chain of thought  ",
    )
    result = adapter.complete_with_model_result(
        model="openai/o3-mini",
        system_prompt="sys",
        user_prompt="user",
    )
    assert result.text == judge_json
    assert result.api_reasoning == "internal chain of thought"
    print("✓ message.reasoning → api_reasoning")


def test_openrouter_extracts_reasoning_details_when_reasoning_empty():
    """AC-001: reasoning 空時は reasoning_details を結合"""
    print("\n=== OpenRouter reasoning_details 抽出 ===")
    judge_json = '{"task_name":"test","total_score":0}'
    adapter = _make_openrouter_adapter_with_message(
        content=judge_json,
        reasoning="",
        reasoning_details=[
            {"type": "reasoning.text", "text": "step one"},
            {"type": "reasoning.text", "text": "step two"},
        ],
    )
    result = adapter.complete_with_model_result(
        model="deepseek/deepseek-r1",
        system_prompt="sys",
        user_prompt="user",
    )
    assert result.text == judge_json
    assert result.api_reasoning == "step one\n\nstep two"
    print("✓ reasoning_details → api_reasoning")


def test_openrouter_thinking_tag_fallback_and_strip():
    """AC-001 / DEC-003: 正規フィールド空時は <thinking> fallback、content から strip"""
    print("\n=== OpenRouter <thinking> fallback ===")
    from adapters.base import strip_thinking_tags

    cleaned, extracted = strip_thinking_tags(
        "<thinking>hidden plan</thinking>\n"
        '{"task_name":"test","total_score":1,"confidence":"high"}'
    )
    assert extracted == "hidden plan"
    assert cleaned == '{"task_name":"test","total_score":1,"confidence":"high"}'

    adapter = _make_openrouter_adapter_with_message(
        content=(
            "<thinking>tag only path</thinking>\n"
            '{"task_name":"test","total_score":1,"confidence":"high"}'
        ),
        reasoning=None,
        reasoning_details=None,
    )
    result = adapter.complete_with_model_result(
        model="some/reasoning-model",
        system_prompt="sys",
        user_prompt="user",
    )
    assert result.api_reasoning == "tag only path"
    assert "<thinking>" not in result.text
    assert '"total_score":1' in result.text
    print("✓ tag fallback + strip")


def test_openrouter_prefers_message_reasoning_over_thinking_tags():
    """DEC-003: フィールドがあるときはタグを api_reasoning に使わない（strip はする）"""
    print("\n=== OpenRouter reasoning 優先 ===")
    adapter = _make_openrouter_adapter_with_message(
        content=(
            "<thinking>ignored tag</thinking>"
            '{"task_name":"test","total_score":0}'
        ),
        reasoning="field wins",
    )
    result = adapter.complete_with_model_result(
        model="openai/o4-mini",
        system_prompt="sys",
        user_prompt="user",
    )
    assert result.api_reasoning == "field wins"
    assert "<thinking>" not in result.text
    print("✓ field preferred over tags")


def test_openrouter_missing_thinking_still_returns_text():
    """AC-004: thinking 欠落でも text は返り、api_reasoning は None"""
    print("\n=== OpenRouter thinking 欠落 ===")
    judge_json = '{"task_name":"test","total_score":50,"confidence":"medium"}'
    adapter = _make_openrouter_adapter_with_message(content=judge_json)
    result = adapter.complete_with_model_result(
        model="openai/gpt-4o",
        system_prompt="sys",
        user_prompt="user",
    )
    assert result.text == judge_json
    assert result.api_reasoning is None
    print("✓ graceful empty api_reasoning")


def test_openrouter_claude_thinking_suffix_extracts_reasoning_without_extra_params():
    """AC-001 / AC-004 / DEC-003: :thinking は effort 未送信でも reasoning を抽出"""
    print("\n=== Claude :thinking suffix 抽出 ===")
    judge_json = '{"task_name":"test","total_score":80,"confidence":"high"}'
    adapter = _make_openrouter_adapter_with_message(
        content=judge_json,
        reasoning="claude always-on internal plan",
        reasoning_details=[
            {
                "type": "reasoning.text",
                "text": "claude always-on internal plan",
                "format": "anthropic-claude-v1",
            }
        ],
    )
    result = adapter.complete_with_model_result(
        model="anthropic/claude-3.7-sonnet:thinking",
        system_prompt="sys",
        user_prompt="user",
    )
    call_kwargs = adapter._client.chat.completions.create.call_args.kwargs
    assert "extra_body" not in call_kwargs
    assert result.text == judge_json
    assert result.api_reasoning == "claude always-on internal plan"
    print("✓ :thinking suffix → api_reasoning, no extra_body")


def test_openrouter_claude_opt_in_extracts_anthropic_reasoning_details():
    """AC-001 / AC-004: opt-in Claude + anthropic-claude-v1 reasoning_details"""
    print("\n=== Claude opt-in reasoning_details 抽出 ===")
    judge_json = '{"task_name":"test","total_score":90,"confidence":"high"}'
    adapter = _make_openrouter_adapter_with_message(
        content=judge_json,
        reasoning="",
        reasoning_details=[
            {
                "type": "reasoning.text",
                "text": "step A",
                "format": "anthropic-claude-v1",
            },
            {
                "type": "reasoning.text",
                "thinking": "native thinking leak",
                "format": "anthropic-claude-v1",
            },
        ],
    )
    result = adapter.complete_with_model_result(
        model="anthropic/claude-3.7-sonnet",
        system_prompt="sys",
        user_prompt="user",
        extra_params={"reasoning": {"effort": "high"}},
    )
    call_kwargs = adapter._client.chat.completions.create.call_args.kwargs
    assert call_kwargs.get("extra_body") == {"reasoning": {"effort": "high"}}
    assert result.api_reasoning == "step A\n\nnative thinking leak"
    print("✓ Claude opt-in + reasoning_details (incl. thinking key)")


def test_openrouter_gemini_thinking_model_extracts_reasoning():
    """AC-002: Gemini thinking モデルは OpenRouter 正規化フィールドから抽出"""
    print("\n=== Gemini thinking モデル抽出 ===")
    judge_json = '{"task_name":"test","total_score":70,"confidence":"medium"}'
    adapter = _make_openrouter_adapter_with_message(
        content=judge_json,
        reasoning="gemini chain of thought",
        reasoning_details=[
            {
                "type": "reasoning.text",
                "text": "gemini chain of thought",
                "format": "google-gemini-v1",
            }
        ],
    )
    result = adapter.complete_with_model_result(
        model="google/gemini-2.5-flash-preview:thinking",
        system_prompt="sys",
        user_prompt="user",
        extra_params={"reasoning": {"effort": "high"}},
    )
    assert result.text == judge_json
    assert result.api_reasoning == "gemini chain of thought"
    print("✓ Gemini thinking → api_reasoning")


def test_openrouter_gemini_non_thinking_empty_api_reasoning():
    """AC-002 / DEC-002: 非 thinking Gemini は空 api_reasoning、text は返す"""
    print("\n=== Gemini 非 thinking no-support ===")
    judge_json = '{"task_name":"test","total_score":55,"confidence":"low"}'
    adapter = _make_openrouter_adapter_with_message(
        content=judge_json,
        reasoning=None,
        reasoning_details=None,
    )
    result = adapter.complete_with_model_result(
        model="google/gemini-2.0-flash-001",
        system_prompt="sys",
        user_prompt="user",
    )
    assert result.text == judge_json
    assert result.api_reasoning is None
    print("✓ Gemini non-thinking → empty api_reasoning")


def test_openrouter_omits_none_or_unsupported_temperature():
    """None または catalog 上非対応なら temperature を送らない"""
    adapter = OpenRouterAdapter(api_key="sk-or-v1-test12345678901234567890")
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "ok"
    mock_response.choices[0].message.tool_calls = []
    mock_response.usage = None
    mock_client.chat.completions.create.return_value = mock_response
    adapter._client = mock_client

    OpenRouterAdapter._models_cache = {
        "anthropic/claude-sonnet-5": {
            "id": "anthropic/claude-sonnet-5",
            "supported_parameters": ["reasoning", "max_tokens", "tools"],
        },
        "google/gemini-3.5-flash": {
            "id": "google/gemini-3.5-flash",
            "supported_parameters": [
                "reasoning",
                "temperature",
                "max_tokens",
                "tools",
            ],
        },
    }
    try:
        adapter.complete_with_model_result(
            model="openrouter/anthropic/claude-sonnet-5",
            system_prompt="sys",
            user_prompt="user",
            temperature=0.0,
        )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "temperature" not in call_kwargs

        mock_client.chat.completions.create.reset_mock()
        adapter.complete_with_model_native_tools(
            model="openrouter/anthropic/claude-sonnet-5",
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            temperature=0.0,
        )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "temperature" not in call_kwargs

        mock_client.chat.completions.create.reset_mock()
        adapter.complete_with_model_result(
            model="openrouter/google/gemini-3.5-flash",
            system_prompt="sys",
            user_prompt="user",
            temperature=None,
        )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "temperature" not in call_kwargs

        mock_client.chat.completions.create.reset_mock()
        adapter.complete_with_model_native_tools(
            model="openrouter/google/gemini-3.5-flash",
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            temperature=None,
        )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "temperature" not in call_kwargs
    finally:
        OpenRouterAdapter._models_cache = None


def test_lmstudio_omits_none_temperature():
    with patch(
        "adapters.lmstudio_adapter.ProviderConfigStore.load_provider",
        return_value={"base_url": "http://127.0.0.1:1234/v1"},
    ):
        adapter = LMStudioAdapter()

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "ok"
    mock_response.choices[0].message.tool_calls = []
    mock_response.usage = None
    mock_client.chat.completions.create.return_value = mock_response
    adapter._client = mock_client

    adapter.complete_with_model_result(
        model="local-model",
        system_prompt="sys",
        user_prompt="user",
        temperature=None,
    )
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert "temperature" not in call_kwargs

    mock_client.chat.completions.create.reset_mock()
    adapter.complete_with_model_native_tools(
        model="local-model",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        temperature=None,
    )
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert "temperature" not in call_kwargs


def test_extra_body_passed_to_lmstudio():
    """extra_params が LM Studio の extra_body として渡される"""
    print("\n=== LM Studio extra_body テスト ===")

    with patch(
        "adapters.lmstudio_adapter.ProviderConfigStore.load_provider",
        return_value={"base_url": "http://127.0.0.1:1234/v1"},
    ):
        adapter = LMStudioAdapter()

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"task_name":"test","task_type":"fact","score":{},"total_score":0}'
    mock_response.usage = None
    mock_client.chat.completions.create.return_value = mock_response
    adapter._client = mock_client

    adapter.complete_with_model_result(
        model="qwen3-30b-a3b",
        system_prompt="sys",
        user_prompt="user",
        extra_params={"reasoning": {"effort": "medium"}},
    )

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert "extra_body" in call_kwargs, "extra_body が含まれる"
    assert call_kwargs["extra_body"] == {"reasoning": {"effort": "medium"}}, "extra_body の内容が正しい"
    assert "reasoning" not in call_kwargs, "reasoning がトップレベルに含まれない"
    print("✓ complete_with_model_result: extra_body として渡される")

    # native tools 版も確認
    mock_client.chat.completions.create.reset_mock()
    adapter.complete_with_model_native_tools(
        model="qwen3-30b-a3b",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        extra_params={"reasoning": {"effort": "medium"}},
    )
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert "extra_body" in call_kwargs, "native_tools: extra_body が含まれる"
    assert call_kwargs["extra_body"] == {"reasoning": {"effort": "medium"}}, "native_tools: extra_body の内容が正しい"
    print("✓ complete_with_model_native_tools: extra_body として渡される")

    print("LM Studio extra_body テスト完了")


def test_lmstudio_effort_passthrough_by_capability():
    """代表3種の capability と extra_body 付与の対応を固定する（Core-Chore-45）。"""
    print("\n=== LM Studio effort passthrough by capability ===")

    with patch(
        "adapters.lmstudio_adapter.ProviderConfigStore.load_provider",
        return_value={"base_url": "http://127.0.0.1:1234/v1"},
    ):
        adapter = LMStudioAdapter()

    LMStudioAdapter._models_cache = None
    mock_data = {
        "models": [
            {
                "key": "opt-in-model",
                "capabilities": {
                    "reasoning": {
                        "default": "off",
                        "allowed_options": ["off", "on"],
                    }
                },
            },
            {
                "key": "default-on-model",
                "capabilities": {
                    "reasoning": {
                        "default": "on",
                        "allowed_options": ["off", "on"],
                    }
                },
            },
            {
                "key": "no-reasoning-model",
                "capabilities": {"chat": True},
            },
        ]
    }

    with patch("adapters.lmstudio_adapter.requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_data
        mock_get.return_value.raise_for_status = MagicMock()

        assert adapter.is_reasoning_opt_in("opt-in-model") is True
        assert adapter.is_reasoning_opt_in("default-on-model") is False
        assert adapter.is_reasoning_opt_in("no-reasoning-model") is False

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "ok"
    mock_response.usage = None
    mock_client.chat.completions.create.return_value = mock_response
    adapter._client = mock_client

    # Engine と同型: opt-in 時のみ {"reasoning": {"effort": "high"}}
    for model_key, expect_opt_in in [
        ("opt-in-model", True),
        ("default-on-model", False),
        ("no-reasoning-model", False),
    ]:
        mock_client.chat.completions.create.reset_mock()
        extra = {"reasoning": {"effort": "high"}} if expect_opt_in else None
        adapter.complete_with_model_result(
            model=model_key,
            system_prompt="sys",
            user_prompt="user",
            extra_params=extra,
        )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        if expect_opt_in:
            assert call_kwargs.get("extra_body") == {
                "reasoning": {"effort": "high"}
            }, model_key
        else:
            assert "extra_body" not in call_kwargs, model_key
        print(
            f"✓ {model_key}: opt_in={expect_opt_in}, "
            f"extra_body={'yes' if expect_opt_in else 'no'}"
        )

    LMStudioAdapter._models_cache = None
    print("LM Studio effort passthrough by capability テスト完了")


def run_all_tests():
    """全テストを実行"""
    print("=" * 50)
    print("アダプタ層テスト開始")
    print("=" * 50)

    try:
        test_adapter_factory()
        test_adapter_availability_without_keys()
        test_adapter_availability_with_keys()
        test_error_handling()
        test_get_all_available_adapters()
        test_lmstudio_adapter_availability_with_base_url()
        test_is_reasoning_opt_in_openrouter()
        test_is_reasoning_opt_in_lmstudio()
        test_extra_body_passed_to_openrouter()
        test_openrouter_extracts_message_reasoning()
        test_openrouter_extracts_reasoning_details_when_reasoning_empty()
        test_openrouter_thinking_tag_fallback_and_strip()
        test_openrouter_prefers_message_reasoning_over_thinking_tags()
        test_openrouter_missing_thinking_still_returns_text()
        test_openrouter_claude_thinking_suffix_extracts_reasoning_without_extra_params()
        test_openrouter_claude_opt_in_extracts_anthropic_reasoning_details()
        test_openrouter_gemini_thinking_model_extracts_reasoning()
        test_openrouter_gemini_non_thinking_empty_api_reasoning()
        test_openrouter_omits_none_or_unsupported_temperature()
        test_lmstudio_omits_none_temperature()
        test_extra_body_passed_to_lmstudio()
        test_lmstudio_effort_passthrough_by_capability()

        print("\n" + "=" * 50)
        print("✅ 全テスト完了")
        print("=" * 50)
        return True

    except AssertionError as e:
        print(f"\n❌ テスト失敗: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 予期しないエラー: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
