"""OpenRouter APIアダプタ（OpenAI互換）"""

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from openai import OpenAI, OpenAIError

from .base import (
    CompletionResult,
    LLMAdapter,
    LLMError,
    NativeCompletionResult,
    NativeToolCall,
    NativeToolsNotSupportedError,
    UsageMetrics,
    strip_thinking_tags,
)


def _coerce_message_field(message: Any, name: str) -> Any:
    if message is None:
        return None
    if isinstance(message, dict):
        return message.get(name)
    value = getattr(message, name, None)
    if value is not None:
        return value
    model_extra = getattr(message, "model_extra", None)
    if isinstance(model_extra, dict):
        return model_extra.get(name)
    return None


# intent: DEC-001 (Core/claude-gemini-judge-thinking) — Anthropic native leaks
# may use `thinking`; OpenRouter CC uses text/summary (same keys as OpenAI path).
_REASONING_DETAIL_TEXT_KEYS = ("text", "summary", "content", "reasoning", "thinking")


def _format_reasoning_details(details: Any) -> Optional[str]:
    if not details:
        return None
    if isinstance(details, str):
        return details.strip() or None

    texts: List[str] = []
    items = details if isinstance(details, list) else [details]
    for item in items:
        if isinstance(item, str):
            if item.strip():
                texts.append(item.strip())
            continue
        if isinstance(item, dict):
            for key in _REASONING_DETAIL_TEXT_KEYS:
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    texts.append(value.strip())
                    break
            continue
        for key in _REASONING_DETAIL_TEXT_KEYS:
            value = getattr(item, key, None)
            if isinstance(value, str) and value.strip():
                texts.append(value.strip())
                break
    if texts:
        return "\n\n".join(texts)
    try:
        serialized = json.dumps(details, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        serialized = str(details)
    return serialized.strip() or None


def extract_api_reasoning_from_message(
    message: Any, content: str
) -> Tuple[str, Optional[str]]:
    """
    Chat Completions message から API thinking を抽出し、パース用 text を正規化する。

    intent: DEC-002 / DEC-003 (Core/openai-judge-thinking) — CC fields first,
    <thinking> tag fallback only when fields are empty; always strip tags for parse.
    intent: DEC-001 (Core/claude-gemini-judge-thinking) — same helper for Anthropic /
    Gemini via OpenRouter-normalized reasoning / reasoning_details (no native SDK).
    """
    cleaned_content, tag_reasoning = strip_thinking_tags(content or "")

    reasoning = _coerce_message_field(message, "reasoning")
    api_reasoning: Optional[str] = None
    if isinstance(reasoning, str) and reasoning.strip():
        api_reasoning = reasoning.strip()
    else:
        details = _coerce_message_field(message, "reasoning_details")
        if isinstance(details, (list, dict, str)):
            api_reasoning = _format_reasoning_details(details)

    # intent: DEC-003 — tag extract only when normalized CC fields are empty
    if not api_reasoning:
        api_reasoning = tag_reasoning

    return cleaned_content, api_reasoning


class OpenRouterAdapter(LLMAdapter):
    """
    OpenRouter API用アダプタ

    OpenRouterはOpenAI APIと互換性があるため、
    ベースURLとAPIキーのみを変更してOpenAIクライアントを使用する。
    """

    BASE_URL = "https://openrouter.ai/api/v1"
    PROVIDER = "openrouter"
    _models_cache: Optional[Dict[str, Any]] = None

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
        temperature: Optional[float] = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """
        OpenRouter APIを使用してテキスト生成を実行

        Args:
            system_prompt: システムプロンプト
            user_prompt: ユーザープロンプト
            temperature: 温度パラメータ（None は送信しない）
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

    @staticmethod
    def _should_use_max_completion_tokens(model: str) -> bool:
        """max_completion_tokens が必要なモデルかどうかを判定"""
        lower = model.lower()
        return any(lower.startswith(p) for p in ("o1", "o3", "o4", "gpt-5"))

    def complete_with_model_result(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = 0.0,
        max_tokens: int = 1024,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> CompletionResult:
        if not self.is_available():
            raise LLMError("OpenRouter APIキーが設定されていません")

        if self._client is None:
            raise LLMError("OpenRouterクライアントが初期化されていません")

        normalized_model = self._normalize_model_name(model)

        try:
            kwargs: Dict[str, Any] = {
                "model": normalized_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            if (
                temperature is not None
                and self._supports_parameter(normalized_model, "temperature") is not False
            ):
                kwargs["temperature"] = temperature
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
            # intent: DEC-002 (Core/openai-judge-thinking) — stay on Chat Completions;
            # extract message.reasoning / reasoning_details (Responses API deferred)
            text, api_reasoning = extract_api_reasoning_from_message(
                message, raw_content
            )
            usage = getattr(response, "usage", None)
            return CompletionResult(
                text=text,
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
                api_reasoning=api_reasoning,
            )

        except OpenAIError as e:
            raise LLMError(f"OpenRouter APIエラー: {str(e)}") from e
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
            raise LLMError("OpenRouter APIキーが設定されていません")

        normalized_model = self._normalize_model_name(model)

        try:
            kwargs: Dict[str, Any] = {
                "model": normalized_model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
            }
            if (
                temperature is not None
                and self._supports_parameter(normalized_model, "temperature") is not False
            ):
                kwargs["temperature"] = temperature
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
                tool_calls.append(NativeToolCall(id=tc.id, name=tc.function.name, arguments=args))

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
                ) if usage is not None else None,
            )

        except OpenAIError as e:
            err = str(e)
            if "tool" in err.lower() or "function" in err.lower():
                raise NativeToolsNotSupportedError(f"OpenRouter tool calling非対応: {err}") from e
            raise LLMError(f"OpenRouter APIエラー: {err}") from e
        except Exception as e:
            raise LLMError(f"予期しないエラー: {str(e)}") from e

    @classmethod
    def _fetch_models_cache(cls) -> Optional[Dict[str, Any]]:
        if cls._models_cache is not None:
            return cls._models_cache
        try:
            resp = requests.get("https://openrouter.ai/api/v1/models", timeout=30)
            resp.raise_for_status()
            data = resp.json()
            cls._models_cache = {m["id"]: m for m in data.get("data", [])}
            return cls._models_cache
        except Exception:
            return None

    def is_reasoning_opt_in(self, model: str) -> bool:
        models = self._fetch_models_cache()
        if models is None:
            return False
        normalized = self._normalize_model_name(model)
        info = models.get(normalized)
        if not info:
            return False
        supports = "reasoning" in info.get("supported_parameters", [])
        always_on = normalized.endswith(":thinking")
        return supports and not always_on

    def _supports_parameter(self, model: str, parameter: str) -> Optional[bool]:
        """OpenRouter catalog が既知なら、未対応 parameter を送信しない。"""
        models = self._fetch_models_cache()
        if models is None:
            return None
        normalized = self._normalize_model_name(model)
        info = models.get(normalized)
        if not info:
            return None
        return parameter in info.get("supported_parameters", [])

    @staticmethod
    def _normalize_model_name(model: str) -> str:
        if model.startswith("openrouter/"):
            return model.split("/", 1)[1]
        if model.startswith("or/"):
            return model.split("/", 1)[1]
        return model
