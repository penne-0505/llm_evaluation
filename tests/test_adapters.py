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
        test_extra_body_passed_to_lmstudio()

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
