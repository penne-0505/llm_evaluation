"""OpenAI APIアダプタ"""

import os
from typing import Optional

from openai import OpenAI, OpenAIError

from .base import LLMAdapter, LLMError


class OpenAIAdapter(LLMAdapter):
    """OpenAI API用アダプタ"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: OpenAI APIキー（Noneの場合は環境変数から取得）
        """
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client: Optional[OpenAI] = None

        if self._api_key:
            self._client = OpenAI(api_key=self._api_key)

    def is_available(self) -> bool:
        """APIキーが設定されているか確認"""
        return self._api_key is not None and self._api_key.startswith("sk-")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """
        OpenAI APIを使用してテキスト生成を実行

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
        model = os.getenv("JUDGE_OPENAI_MODEL", "gpt-4o")
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
            raise LLMError("OpenAI APIキーが設定されていません")

        if self._client is None:
            raise LLMError("OpenAIクライアントが初期化されていません")

        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            return response.choices[0].message.content or ""

        except OpenAIError as e:
            raise LLMError(f"OpenAI APIエラー: {str(e)}") from e
        except Exception as e:
            raise LLMError(f"予期しないエラー: {str(e)}") from e
