"""アダプタ層のテスト"""

import os
import sys
from unittest.mock import patch, MagicMock

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters import (
    get_adapter_for_model,
    get_all_available_adapters,
    OpenAIAdapter,
    AnthropicAdapter,
    GeminiAdapter,
    OpenRouterAdapter,
    LLMError,
)


def test_adapter_factory():
    """アダプタファクトリ関数のテスト"""
    print("\n=== アダプタファクトリテスト ===")

    test_cases = [
        ("gpt-4o", OpenAIAdapter),
        ("o1-preview", OpenAIAdapter),
        ("o3-mini", OpenAIAdapter),
        ("claude-sonnet-4-5-20250929", AnthropicAdapter),
        ("gemini-1.5-pro", GeminiAdapter),
        ("openrouter/openai/gpt-4o", OpenRouterAdapter),
        ("or/anthropic/claude-3-opus", OpenRouterAdapter),
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
        openai = OpenAIAdapter()
        anthropic = AnthropicAdapter()
        gemini = GeminiAdapter()

        assert not openai.is_available(), "OpenAI: APIキーなしでFalse"
        assert not anthropic.is_available(), "Anthropic: APIキーなしでFalse"
        assert not gemini.is_available(), "Gemini: APIキーなしでFalse"

        print("✓ OpenAI: unavailable (no key)")
        print("✓ Anthropic: unavailable (no key)")
        print("✓ Gemini: unavailable (no key)")

    print("APIキーなし時の可用性テスト完了")


def test_adapter_availability_with_keys():
    """APIキーあり時のアダプタ可用性テスト"""
    print("\n=== APIキーあり時の可用性テスト ===")

    test_env = {
        "OPENAI_API_KEY": "sk-test123456789",
        "ANTHROPIC_API_KEY": "sk-ant-test123",
        "GEMINI_API_KEY": "test-gemini-key-12345",
        "OPENROUTER_API_KEY": "sk-or-v1-test12345678901234567890",
    }

    with patch.dict(os.environ, test_env, clear=True):
        openai = OpenAIAdapter()
        anthropic = AnthropicAdapter()
        gemini = GeminiAdapter()
        openrouter = OpenRouterAdapter()

        assert openai.is_available(), "OpenAI: 有効なAPIキーでTrue"
        assert anthropic.is_available(), "Anthropic: 有効なAPIキーでTrue"
        assert gemini.is_available(), "Gemini: 有効なAPIキーでTrue"
        assert openrouter.is_available(), "OpenRouter: 有効なAPIキーでTrue"

        print("✓ OpenAI: available (with key)")
        print("✓ Anthropic: available (with key)")
        print("✓ Gemini: available (with key)")
        print("✓ OpenRouter: available (with key)")

    print("APIキーあり時の可用性テスト完了")


def test_error_handling():
    """エラーハンドリングテスト"""
    print("\n=== エラーハンドリングテスト ===")

    with patch.dict(os.environ, {}, clear=True):
        openai = OpenAIAdapter()

        try:
            openai.complete("system", "user")
            assert False, "APIキーなしでLLMErrorが発生すべき"
        except LLMError as e:
            print(f"✓ OpenAI: APIキーなしでLLMError発生 - {e}")

    print("エラーハンドリングテスト完了")


def test_get_all_available_adapters():
    """全アダプタ取得関数のテスト"""
    print("\n=== 全アダプタ取得テスト ===")

    # APIキーなし
    with patch.dict(os.environ, {}, clear=True):
        adapters = get_all_available_adapters()
        assert len(adapters) == 0, "APIキーなしで空の辞書"
        print("✓ APIキーなし: 空の辞書を返す")

    # APIキーあり（1つ）
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=True):
        adapters = get_all_available_adapters()
        assert len(adapters) == 1, "1つのAPIキーで1つのアダプタ"
        assert "openai" in adapters, "OpenAIが含まれる"
        print("✓ APIキー1つ: openaiのみ含まれる")

    # APIキーあり（全て）
    test_env = {
        "OPENAI_API_KEY": "sk-test123",
        "ANTHROPIC_API_KEY": "sk-ant-test123",
        "GEMINI_API_KEY": "test-gemini-key-12345",
        "OPENROUTER_API_KEY": "sk-or-v1-test12345678901234567890",
    }
    with patch.dict(os.environ, test_env, clear=True):
        adapters = get_all_available_adapters()
        assert len(adapters) == 4, "全APIキーで4つのアダプタ"
        assert all(
            k in adapters for k in ["openai", "anthropic", "gemini", "openrouter"]
        )
        print("✓ APIキー全て: 4つのアダプタが含まれる")

    print("全アダプタ取得テスト完了")


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
