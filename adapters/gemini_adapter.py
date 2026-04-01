"""Gemini APIアダプタ"""

import os
from typing import Any, Optional

import importlib

from .base import CompletionResult, LLMAdapter, LLMError, UsageMetrics


class GeminiAdapter(LLMAdapter):
    """Google Gemini API用アダプタ"""

    PROVIDER = "gemini"

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: Gemini APIキー（Noneの場合は環境変数から取得）
        """
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._model = None
        self._client = None

        if self._api_key:
            genai = self._load_genai()
            self._client = getattr(genai, "Client")(api_key=self._api_key)

    def is_available(self) -> bool:
        """APIキーが設定されているか確認"""
        return self._api_key is not None and len(self._api_key) > 10

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """
        Gemini APIを使用してテキスト生成を実行

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
        model_name = os.getenv("JUDGE_GEMINI_MODEL", "gemini-1.5-pro")
        return self.complete_with_model(
            model=model_name,
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
            raise LLMError("Gemini APIキーが設定されていません")

        try:
            if self._client is None:
                genai = self._load_genai()
                self._client = getattr(genai, "Client")(api_key=self._api_key)

            response = self._client.models.generate_content(
                model=model,
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )

            usage = getattr(response, "usage_metadata", None) or getattr(
                response, "usage", None
            )
            return CompletionResult(
                text=getattr(response, "text", "") or "",
                usage=UsageMetrics(
                    provider=self.PROVIDER,
                    model=model,
                    input_tokens=getattr(usage, "prompt_token_count", None),
                    output_tokens=getattr(usage, "candidates_token_count", None),
                    total_tokens=getattr(usage, "total_token_count", None),
                )
                if usage is not None
                else None,
            )

        except Exception as e:
            if self._is_genai_api_error(e):
                raise LLMError(f"Gemini APIエラー: {str(e)}") from e
            raise LLMError(f"予期しないエラー: {str(e)}") from e

    @staticmethod
    def _load_genai() -> Any:
        return importlib.import_module("google.genai")

    @staticmethod
    def _is_genai_api_error(error: Exception) -> bool:
        try:
            genai_errors = importlib.import_module("google.genai.errors")
        except ModuleNotFoundError:
            return False

        api_error_type = getattr(genai_errors, "APIError", None)
        return isinstance(api_error_type, type) and isinstance(error, api_error_type)
