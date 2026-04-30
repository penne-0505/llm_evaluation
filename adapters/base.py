"""LLMアダプタの基底クラスと例外定義"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class LLMError(Exception):
    """LLM呼び出しエラー"""

    pass


class NativeToolsNotSupportedError(LLMError):
    """モデルまたはアダプタがネイティブtool callingに非対応"""

    pass


@dataclass
class UsageMetrics:
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    duration_ms: int | None = None

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "duration_ms": self.duration_ms,
        }


@dataclass
class CompletionResult:
    text: str
    usage: UsageMetrics | None = None


@dataclass
class NativeToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class NativeCompletionResult:
    content: Optional[str]
    tool_calls: List[NativeToolCall] = field(default_factory=list)
    usage: Optional[UsageMetrics] = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class LLMAdapter(ABC):
    """LLMプロバイダー用抽象基底クラス"""

    PROVIDER = "unknown"

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """
        テキスト生成を実行する

        Args:
            system_prompt: システムプロンプト
            user_prompt: ユーザープロンプト
            temperature: 温度パラメータ
            max_tokens: 最大トークン数

        Returns:
            生成されたテキスト

        Raises:
            LLMError: API呼び出し失敗時
        """
        pass

    def complete_result(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> CompletionResult:
        return CompletionResult(
            text=self.complete(system_prompt, user_prompt, temperature, max_tokens)
        )

    @abstractmethod
    def is_available(self) -> bool:
        """APIキーが設定されているか確認"""
        pass

    @abstractmethod
    def complete_with_model(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """
        指定モデルでテキスト生成を実行する

        Args:
            model: 使用するモデル名
            system_prompt: システムプロンプト
            user_prompt: ユーザープロンプト
            temperature: 温度パラメータ
            max_tokens: 最大トークン数

        Returns:
            生成されたテキスト

        Raises:
            LLMError: API呼び出し失敗時
        """
        pass

    def complete_with_model_result(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> CompletionResult:
        return CompletionResult(
            text=self.complete_with_model(
                model, system_prompt, user_prompt, temperature, max_tokens
            )
        )

    def is_reasoning_opt_in(self, model: str) -> bool:
        """モデルがopt-inでreasoningを有効にできるか判定（デフォルトFalse）"""
        return False

    def supports_native_tools(self) -> bool:
        return False

    def complete_with_model_native_tools(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> NativeCompletionResult:
        raise NativeToolsNotSupportedError(
            f"{self.__class__.__name__} does not support native tool calling"
        )
