"""汎用 OpenAI 互換アダプタ（registry エントリ用）。"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI, OpenAIError

from .base import (
    CompletionResult,
    LLMAdapter,
    LLMError,
    NativeCompletionResult,
    NativeToolCall,
    NativeToolsNotSupportedError,
    UsageMetrics,
)
from .openrouter_adapter import extract_api_reasoning_from_message


class OpenAICompatibleAdapter(LLMAdapter):
    """任意 base_url + API key の OpenAI Chat Completions アダプタ。

    intent: DEC-001/005 (Core/openai-compat-anthropic-providers) —
    OpenRouter 固有ゲートは profile=openrouter のときだけ（本クラスは汎用）。
    """

    def __init__(
        self,
        *,
        provider_id: str,
        api_key: Optional[str],
        base_url: str,
        profile: Optional[str] = None,
    ):
        self.PROVIDER = provider_id
        self._provider_id = provider_id
        self._profile = profile
        self._api_key = api_key
        self._base_url = str(base_url or "").strip().rstrip("/")
        self._client: Optional[OpenAI] = None
        if self._api_key and self._base_url:
            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)

    def is_available(self) -> bool:
        return bool(self._api_key) and self._client is not None and bool(self._base_url)

    def _normalize_model_name(self, model: str) -> str:
        prefix = f"{self._provider_id}/"
        if model.startswith(prefix):
            return model[len(prefix) :]
        # openrouter aliases when this adapter is used for openrouter id
        if self._provider_id == "openrouter":
            if model.startswith("openrouter/"):
                return model.split("/", 1)[1]
            if model.startswith("or/"):
                return model.split("/", 1)[1]
        return model

    @staticmethod
    def _should_use_max_completion_tokens(model: str) -> bool:
        from core.model_parameter_support import uses_max_completion_tokens

        return uses_max_completion_tokens("openai", model)

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        return self.complete_with_model(
            model=f"{self._provider_id}/default",
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
        temperature: Optional[float] = 0.0,
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
        temperature: Optional[float] = 0.0,
        max_tokens: int = 1024,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> CompletionResult:
        if not self.is_available() or self._client is None:
            raise LLMError(f"{self._provider_id}: APIキーまたは base_url が未設定です")

        normalized_model = self._normalize_model_name(model)
        try:
            kwargs: Dict[str, Any] = {
                "model": normalized_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            from core.model_parameter_support import apply_temperature

            apply_temperature(
                kwargs,
                provider=self._provider_id,
                model=model,
                temperature=temperature,
            )
            if self._should_use_max_completion_tokens(normalized_model):
                kwargs["max_completion_tokens"] = max_tokens
            else:
                kwargs["max_tokens"] = max_tokens
            if extra_params:
                kwargs["extra_body"] = extra_params

            start = time.perf_counter()
            response = self._client.chat.completions.create(**kwargs)
            duration_ms = int((time.perf_counter() - start) * 1000)

            message = response.choices[0].message
            raw_content = message.content or ""
            text, api_reasoning = extract_api_reasoning_from_message(
                message, raw_content
            )
            usage = getattr(response, "usage", None)
            return CompletionResult(
                text=text,
                usage=UsageMetrics(
                    provider=self._provider_id,
                    model=model,
                    input_tokens=getattr(usage, "prompt_tokens", None),
                    output_tokens=getattr(usage, "completion_tokens", None),
                    total_tokens=getattr(usage, "total_tokens", None),
                    duration_ms=duration_ms,
                )
                if usage is not None
                else None,
                api_reasoning=api_reasoning,
            )
        except OpenAIError as e:
            raise LLMError(f"{self._provider_id} APIエラー: {str(e)}") from e
        except Exception as e:
            raise LLMError(f"予期しないエラー: {str(e)}") from e

    def supports_native_tools(self) -> bool:
        return True

    def complete_with_model_native_tools(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: Optional[float] = 0.0,
        max_tokens: int = 4096,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> NativeCompletionResult:
        if not self.is_available() or self._client is None:
            raise LLMError(f"{self._provider_id}: APIキーまたは base_url が未設定です")

        normalized_model = self._normalize_model_name(model)
        try:
            kwargs: Dict[str, Any] = {
                "model": normalized_model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
            }
            from core.model_parameter_support import apply_temperature

            apply_temperature(
                kwargs,
                provider=self._provider_id,
                model=model,
                temperature=temperature,
            )
            if self._should_use_max_completion_tokens(normalized_model):
                kwargs["max_completion_tokens"] = max_tokens
            else:
                kwargs["max_tokens"] = max_tokens
            if extra_params:
                kwargs["extra_body"] = extra_params

            start = time.perf_counter()
            response = self._client.chat.completions.create(**kwargs)
            duration_ms = int((time.perf_counter() - start) * 1000)

            message = response.choices[0].message
            tool_calls = []
            for tc in message.tool_calls or []:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(
                    NativeToolCall(id=tc.id, name=tc.function.name, arguments=args)
                )

            usage = getattr(response, "usage", None)
            return NativeCompletionResult(
                content=message.content,
                tool_calls=tool_calls,
                usage=UsageMetrics(
                    provider=self._provider_id,
                    model=model,
                    input_tokens=getattr(usage, "prompt_tokens", None),
                    output_tokens=getattr(usage, "completion_tokens", None),
                    total_tokens=getattr(usage, "total_tokens", None),
                    duration_ms=duration_ms,
                )
                if usage is not None
                else None,
            )
        except OpenAIError as e:
            err = str(e)
            if "tool" in err.lower() or "function" in err.lower():
                raise NativeToolsNotSupportedError(
                    f"{self._provider_id} tool calling非対応: {err}"
                ) from e
            raise LLMError(f"{self._provider_id} APIエラー: {err}") from e
        except Exception as e:
            raise LLMError(f"予期しないエラー: {str(e)}") from e
