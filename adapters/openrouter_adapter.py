"""OpenRouter APIアダプタ（OpenAI互換）"""

import os
from typing import Optional

from openai import OpenAI, OpenAIError

from .base import CompletionResult, LLMAdapter, LLMError, UsageMetrics


class OpenRouterAdapter(LLMAdapter):
    """
    OpenRouter API用アダプタ

    OpenRouterはOpenAI APIと互換性があるため、
    ベースURLとAPIキーのみを変更してOpenAIクライアントを使用する。
    """

    BASE_URL = "https://openrouter.ai/api/v1"
    PROVIDER = "openrouter"

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: OpenRouter APIキー（Noneの場合は環境変数から取得）
        """
        self._api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self._client: Optional[OpenAI] = None

        if self._api_key:
            self._client = OpenAI(api_key=self._api_key, base_url=self.BASE_URL)

    def is_available(self) -> bool:
        """APIキーが設定されているか確認"""
        return self._api_key is not None and len(self._api_key) > 20

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """
        OpenRouter APIを使用してテキスト生成を実行

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
        model = os.getenv("JUDGE_OPENROUTER_MODEL", "openai/gpt-4o")
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
            raise LLMError("OpenRouter APIキーが設定されていません")

        if self._client is None:
            raise LLMError("OpenRouterクライアントが初期化されていません")

        normalized_model = self._normalize_model_name(model)

        try:
            response = self._client.chat.completions.create(
                model=normalized_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            usage = getattr(response, "usage", None)
            return CompletionResult(
                text=response.choices[0].message.content or "",
                usage=UsageMetrics(
                    provider=self.PROVIDER,
                    model=model,
                    input_tokens=getattr(usage, "prompt_tokens", None),
                    output_tokens=getattr(usage, "completion_tokens", None),
                    total_tokens=getattr(usage, "total_tokens", None),
                )
                if usage is not None
                else None,
            )

        except OpenAIError as e:
            raise LLMError(f"OpenRouter APIエラー: {str(e)}") from e
        except Exception as e:
            raise LLMError(f"予期しないエラー: {str(e)}") from e

    @staticmethod
    def _normalize_model_name(model: str) -> str:
        if model.startswith("openrouter/"):
            return model.split("/", 1)[1]
        if model.startswith("or/"):
            return model.split("/", 1)[1]
        return model
