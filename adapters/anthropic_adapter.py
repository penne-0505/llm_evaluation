"""Anthropic Messages API アダプタ（registry anthropic kind 用）。"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from anthropic import APIError, Anthropic

from .base import (
    CompletionResult,
    LLMAdapter,
    LLMError,
    NativeCompletionResult,
    NativeToolCall,
    NativeToolsNotSupportedError,
    UsageMetrics,
)

# create kwargs に extra_params をマージするとき上書きしないキー
_RESERVED_CREATE_KEYS = frozenset(
    {"model", "messages", "system", "max_tokens", "tools", "tool_choice"}
)


def _block_attr(block: Any, name: str) -> Any:
    if isinstance(block, dict):
        return block.get(name)
    return getattr(block, name, None)


def _extract_text_and_reasoning(content: Any) -> Tuple[str, Optional[str]]:
    """Messages content から text / thinking を分離する。"""
    if content is None:
        return "", None
    if isinstance(content, str):
        return content, None

    texts: List[str] = []
    reasonings: List[str] = []
    blocks = content if isinstance(content, list) else [content]
    for block in blocks:
        btype = _block_attr(block, "type")
        if btype == "thinking":
            thinking = _block_attr(block, "thinking")
            if isinstance(thinking, str) and thinking.strip():
                reasonings.append(thinking.strip())
            continue
        if btype == "text":
            text = _block_attr(block, "text")
            if isinstance(text, str) and text:
                texts.append(text)
            continue
        # 文字列ブロック等のフォールバック
        if isinstance(block, str) and block:
            texts.append(block)

    api_reasoning = "\n\n".join(reasonings) if reasonings else None
    return "\n".join(texts), api_reasoning


def _convert_openai_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """OpenAI function tools → Anthropic tools（input_schema）。"""
    converted: List[Dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if "input_schema" in tool and "name" in tool:
            converted.append(
                {
                    "name": tool["name"],
                    "description": tool.get("description") or "",
                    "input_schema": tool.get("input_schema")
                    or {"type": "object", "properties": {}},
                }
            )
            continue
        fn = tool.get("function")
        if isinstance(fn, dict) and fn.get("name"):
            converted.append(
                {
                    "name": fn["name"],
                    "description": fn.get("description") or "",
                    "input_schema": fn.get("parameters")
                    or {"type": "object", "properties": {}},
                }
            )
            continue
        if tool.get("name"):
            converted.append(
                {
                    "name": tool["name"],
                    "description": tool.get("description") or "",
                    "input_schema": tool.get("parameters")
                    or tool.get("input_schema")
                    or {"type": "object", "properties": {}},
                }
            )
    return converted


def _parse_tool_arguments(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _convert_openai_messages(
    messages: List[Dict[str, Any]],
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """OpenAI Chat messages → Anthropic system + messages（best-effort）。"""
    system_parts: List[str] = []
    out: List[Dict[str, Any]] = []

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")

        if role == "system":
            if isinstance(content, str) and content.strip():
                system_parts.append(content.strip())
            continue

        if role == "user":
            out.append({"role": "user", "content": content if content is not None else ""})
            continue

        if role == "assistant":
            blocks: List[Dict[str, Any]] = []
            if isinstance(content, str) and content:
                blocks.append({"type": "text", "text": content})
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        blocks.append(item)
                    elif isinstance(item, str) and item:
                        blocks.append({"type": "text", "text": item})
            for tc in msg.get("tool_calls") or []:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id") or "",
                        "name": fn.get("name") or tc.get("name") or "",
                        "input": _parse_tool_arguments(
                            fn.get("arguments", tc.get("input", {}))
                        ),
                    }
                )
            out.append({"role": "assistant", "content": blocks if blocks else ""})
            continue

        if role == "tool":
            tool_result = {
                "type": "tool_result",
                "tool_use_id": msg.get("tool_call_id") or "",
                "content": content
                if isinstance(content, str)
                else json.dumps(content, ensure_ascii=False),
            }
            if (
                out
                and out[-1].get("role") == "user"
                and isinstance(out[-1].get("content"), list)
                and out[-1]["content"]
                and isinstance(out[-1]["content"][0], dict)
                and out[-1]["content"][0].get("type") == "tool_result"
            ):
                out[-1]["content"].append(tool_result)
            else:
                out.append({"role": "user", "content": [tool_result]})
            continue

        out.append({"role": str(role or "user"), "content": content if content is not None else ""})

    system = "\n\n".join(system_parts) if system_parts else None
    return system, out


def _extract_native_tool_calls(content: Any) -> Tuple[Optional[str], List[NativeToolCall]]:
    texts: List[str] = []
    tool_calls: List[NativeToolCall] = []
    if content is None:
        return None, tool_calls
    if isinstance(content, str):
        return content or None, tool_calls

    blocks = content if isinstance(content, list) else [content]
    for block in blocks:
        btype = _block_attr(block, "type")
        if btype == "tool_use":
            raw_input = _block_attr(block, "input")
            args = raw_input if isinstance(raw_input, dict) else _parse_tool_arguments(raw_input)
            tool_calls.append(
                NativeToolCall(
                    id=str(_block_attr(block, "id") or ""),
                    name=str(_block_attr(block, "name") or ""),
                    arguments=args,
                )
            )
            continue
        if btype == "text":
            text = _block_attr(block, "text")
            if isinstance(text, str) and text:
                texts.append(text)
    return ("\n".join(texts) if texts else None), tool_calls


class AnthropicAdapter(LLMAdapter):
    """Anthropic Messages API 用アダプタ。

    intent: DEC-006 (Core/openai-compat-anthropic-providers) — Messages で
    complete / native tool_use / thinking→api_reasoning。caching・Batches は非保証。
    """

    PROVIDER = "anthropic"

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider_id: str = "anthropic",
        base_url: Optional[str] = None,
    ):
        """
        Args:
            api_key: Anthropic APIキー（None の場合は ANTHROPIC_API_KEY）
            provider_id: registry 上のプロバイダ id（usage.provider に使う）
            base_url: 省略時は SDK 既定（公式）。互換ゲートウェイ向けに上書き可
        """
        self.PROVIDER = provider_id
        self._provider_id = provider_id
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._base_url = (str(base_url).strip().rstrip("/") if base_url else None) or None
        self._client: Optional[Anthropic] = None

        if self._api_key:
            if self._base_url:
                self._client = Anthropic(api_key=self._api_key, base_url=self._base_url)
            else:
                self._client = Anthropic(api_key=self._api_key)

    def is_available(self) -> bool:
        """APIキーが設定されているか確認（長さ > 10）。"""
        return self._api_key is not None and len(self._api_key) > 10

    def _normalize_model_name(self, model: str) -> str:
        prefix = f"{self._provider_id}/"
        if model.startswith(prefix):
            return model[len(prefix) :]
        # 組み込み anthropic 向けのよくある表記
        if model.startswith("anthropic/"):
            return model.split("/", 1)[1]
        return model

    @staticmethod
    def _merge_extra_params(
        kwargs: Dict[str, Any], extra_params: Optional[Dict[str, Any]]
    ) -> None:
        """thinking 等を create kwargs へ慎重にマージ（予約キーは上書きしない）。"""
        if not extra_params:
            return
        for key, value in extra_params.items():
            if key in _RESERVED_CREATE_KEYS:
                continue
            kwargs[key] = value

    def _usage_metrics(
        self, model: str, usage: Any, duration_ms: int
    ) -> Optional[UsageMetrics]:
        if usage is None:
            return None
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        total = None
        if input_tokens is not None or output_tokens is not None:
            total = int(input_tokens or 0) + int(output_tokens or 0)
        return UsageMetrics(
            provider=self.PROVIDER,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            cache_creation_input_tokens=getattr(
                usage, "cache_creation_input_tokens", None
            ),
            cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", None),
            duration_ms=duration_ms,
        )

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        model = os.getenv(
            "JUDGE_ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"
        )
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
            raise LLMError(f"{self._provider_id}: APIキーが設定されていません")

        normalized_model = self._normalize_model_name(model)
        try:
            kwargs: Dict[str, Any] = {
                "model": normalized_model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }
            from core.model_parameter_support import apply_temperature

            apply_temperature(
                kwargs,
                provider=self._provider_id,
                model=model,
                temperature=temperature,
            )
            self._merge_extra_params(kwargs, extra_params)

            start = time.perf_counter()
            response = self._client.messages.create(**kwargs)
            duration_ms = int((time.perf_counter() - start) * 1000)

            text, api_reasoning = _extract_text_and_reasoning(
                getattr(response, "content", None)
            )
            return CompletionResult(
                text=text,
                usage=self._usage_metrics(
                    model, getattr(response, "usage", None), duration_ms
                ),
                api_reasoning=api_reasoning,
            )
        except APIError as e:
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
            raise LLMError(f"{self._provider_id}: APIキーが設定されていません")

        normalized_model = self._normalize_model_name(model)
        system, anthropic_messages = _convert_openai_messages(messages)
        anthropic_tools = _convert_openai_tools(tools)

        try:
            kwargs: Dict[str, Any] = {
                "model": normalized_model,
                "max_tokens": max_tokens,
                "messages": anthropic_messages,
                "tools": anthropic_tools,
            }
            if system:
                kwargs["system"] = system
            from core.model_parameter_support import apply_temperature

            apply_temperature(
                kwargs,
                provider=self._provider_id,
                model=model,
                temperature=temperature,
            )
            self._merge_extra_params(kwargs, extra_params)

            start = time.perf_counter()
            response = self._client.messages.create(**kwargs)
            duration_ms = int((time.perf_counter() - start) * 1000)

            content, tool_calls = _extract_native_tool_calls(
                getattr(response, "content", None)
            )
            return NativeCompletionResult(
                content=content,
                tool_calls=tool_calls,
                usage=self._usage_metrics(
                    model, getattr(response, "usage", None), duration_ms
                ),
            )
        except APIError as e:
            err = str(e)
            if "tool" in err.lower():
                raise NativeToolsNotSupportedError(
                    f"{self._provider_id} tool calling非対応: {err}"
                ) from e
            raise LLMError(f"{self._provider_id} APIエラー: {err}") from e
        except NativeToolsNotSupportedError:
            raise
        except Exception as e:
            raise LLMError(f"予期しないエラー: {str(e)}") from e
