"""Anthropic APIアダプタ"""

import os
from typing import Optional

from anthropic import Anthropic, AnthropicError

from .base import CompletionResult, LLMAdapter, LLMError, UsageMetrics


class AnthropicAdapter(LLMAdapter):
    """Anthropic API用アダプタ"""

    PROVIDER = "anthropic"

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
        return self.complete_with_model_result(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        ).text

    def complete_with_model_result(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> CompletionResult:
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
            usage = getattr(response, "usage", None)
            text = ""
            if content and len(content) > 0:
                text = getattr(content[0], "text", None) or str(content[0])

            cache_creation = getattr(usage, "cache_creation_input_tokens", None)
            cache_read = getattr(usage, "cache_read_input_tokens", None)
            input_tokens = getattr(usage, "input_tokens", None)
            output_tokens = getattr(usage, "output_tokens", None)
            total_tokens = None
            numeric_values = [
                value
                for value in [input_tokens, output_tokens, cache_creation, cache_read]
                if isinstance(value, int)
            ]
            if numeric_values:
                total_tokens = sum(numeric_values)

            return CompletionResult(
                text=text,
                usage=UsageMetrics(
                    provider=self.PROVIDER,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cache_creation_input_tokens=cache_creation,
                    cache_read_input_tokens=cache_read,
                )
                if usage is not None
                else None,
            )

        except AnthropicError as e:
            raise LLMError(f"Anthropic APIエラー: {str(e)}") from e
        except Exception as e:
            raise LLMError(f"予期しないエラー: {str(e)}") from e
