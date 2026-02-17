"""LLMアダプタの基底クラスと例外定義"""

from abc import ABC, abstractmethod
from typing import Optional


class LLMError(Exception):
    """LLM呼び出しエラー"""

    pass


class LLMAdapter(ABC):
    """LLMプロバイダー用抽象基底クラス"""

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
