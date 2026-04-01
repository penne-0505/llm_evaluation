"""LLMアダプタの基底クラスと例外定義"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


class LLMError(Exception):
    """LLM呼び出しエラー"""

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

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
        }


@dataclass
class CompletionResult:
    text: str
    usage: UsageMetrics | None = None


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
    ) -> CompletionResult:
        return CompletionResult(
            text=self.complete_with_model(
                model, system_prompt, user_prompt, temperature, max_tokens
            )
        )
