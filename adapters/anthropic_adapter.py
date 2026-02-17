"""Anthropic APIアダプタ"""

import os
from typing import Optional

from anthropic import Anthropic, AnthropicError

from .base import LLMAdapter, LLMError


class AnthropicAdapter(LLMAdapter):
    """Anthropic API用アダプタ"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: Anthropic APIキー（Noneの場合は環境変数から取得）
        """
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._client: Optional[Anthropic] = None

        if self._api_key:
            self._client = Anthropic(api_key=self._api_key)

    def is_available(self) -> bool:
        """APIキーが設定されているか確認"""
        return self._api_key is not None and self._api_key.startswith("sk-ant-")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """
        Anthropic APIを使用してテキスト生成を実行

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
        model = os.getenv("JUDGE_ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
        return self.complete_with_model(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def complete_with_model(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        if not self.is_available():
            raise LLMError("Anthropic APIキーが設定されていません")

        if self._client is None:
            raise LLMError("Anthropicクライアントが初期化されていません")

        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            content = response.content
            if content and len(content) > 0:
                return str(content[0])
            return ""

        except AnthropicError as e:
            raise LLMError(f"Anthropic APIエラー: {str(e)}") from e
        except Exception as e:
            raise LLMError(f"予期しないエラー: {str(e)}") from e
