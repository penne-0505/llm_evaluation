"""LM Studio OpenAI-compatible API アダプタ"""

import json
import os
import time
from typing import Any, Dict, List, Optional

import requests
from openai import OpenAI, OpenAIError

from core.provider_config_store import ProviderConfigStore

from .base import (
    CompletionResult,
    LLMAdapter,
    LLMError,
    NativeCompletionResult,
    NativeToolCall,
    NativeToolsNotSupportedError,
    UsageMetrics,
)


class LMStudioAdapter(LLMAdapter):
    """LM Studio OpenAI-compatible endpoint 用アダプタ"""

    PROVIDER = "lmstudio"
    DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
    PLACEHOLDER_API_KEY = "lm-studio"
    _models_cache: Optional[Dict[str, Any]] = None

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self._api_key = api_key
        self._base_url = self._normalize_base_url(base_url or self._load_base_url())
        self._client: Optional[OpenAI] = None

        if self._base_url:
            self._client = OpenAI(
                api_key=self._api_key or self.PLACEHOLDER_API_KEY,
                base_url=self._base_url,
            )

    def _load_base_url(self) -> Optional[str]:
        config = ProviderConfigStore.load_provider(self.PROVIDER)
        return str(config.get("base_url") or "").strip() or os.getenv(
            "LMSTUDIO_BASE_URL"
        )

    @classmethod
    def _normalize_base_url(cls, base_url: Optional[str]) -> Optional[str]:
        if base_url is None:
            return None
        normalized = str(base_url).strip().rstrip("/")
        if not normalized:
            return None
        if normalized.endswith("/v1"):
            return normalized
        return f"{normalized}/v1"

    @staticmethod
    def _normalize_model_name(model: str) -> str:
        if model.startswith("lmstudio/"):
            return model.split("/", 1)[1]
        return model

    def is_available(self) -> bool:
        return self._client is not None and bool(self._base_url)

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        model = os.getenv("JUDGE_LMSTUDIO_MODEL", "lmstudio/local-model")
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
            raise LLMError("LM Studio の base URL が設定されていません")

        normalized_model = self._normalize_model_name(model)

        try:
            kwargs: Dict[str, Any] = {
                "model": normalized_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
            }
            if temperature is not None:
                kwargs["temperature"] = temperature
            if extra_params:
                kwargs["extra_body"] = extra_params

            start = time.perf_counter()
            response = self._client.chat.completions.create(**kwargs)
            duration_ms = int((time.perf_counter() - start) * 1000)

            usage = getattr(response, "usage", None)
            return CompletionResult(
                text=response.choices[0].message.content or "",
                usage=UsageMetrics(
                    provider=self.PROVIDER,
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
            raise LLMError(f"LM Studio APIエラー: {str(e)}") from e
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
            raise LLMError("LM Studio の base URL が設定されていません")

        normalized_model = self._normalize_model_name(model)

        try:
            kwargs: Dict[str, Any] = {
                "model": normalized_model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "max_tokens": max_tokens,
            }
            if temperature is not None:
                kwargs["temperature"] = temperature
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
                    NativeToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args,
                    )
                )

            usage = getattr(response, "usage", None)
            return NativeCompletionResult(
                content=message.content,
                tool_calls=tool_calls,
                usage=UsageMetrics(
                    provider=self.PROVIDER,
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
                    f"LM Studio tool calling非対応: {err}"
                ) from e
            raise LLMError(f"LM Studio APIエラー: {err}") from e
        except Exception as e:
            raise LLMError(f"予期しないエラー: {str(e)}") from e

    def _fetch_models_cache(self) -> Optional[Dict[str, Any]]:
        if LMStudioAdapter._models_cache is not None:
            return LMStudioAdapter._models_cache
        if not self._base_url:
            return None
        # /v1 エンドポイントを除き、ネイティブ /api/v1/models を使用
        base = self._base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        url = f"{base}/api/v1/models"
        token = self._api_key or self.PLACEHOLDER_API_KEY
        try:
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            LMStudioAdapter._models_cache = {
                m["key"]: m for m in data.get("models", [])
            }
            return LMStudioAdapter._models_cache
        except Exception:
            return None

    def is_reasoning_opt_in(self, model: str) -> bool:
        """capabilities.reasoning.default が off のときのみ True。

        default が on、または capability なしの場合は False。
        False のとき engine は reasoning.effort を送らず、LM Studio 側デフォルトに委ねる。
        """
        models = self._fetch_models_cache()
        if models is None:
            return False
        normalized = self._normalize_model_name(model)
        info = models.get(normalized)
        if not info:
            return False
        reasoning = info.get("capabilities", {}).get("reasoning")
        if reasoning is None:
            return False
        return reasoning.get("default") == "off"
