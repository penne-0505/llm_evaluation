"""被験モデル向けのローカル tool runtime"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


TOOL_CALL_PATTERN = re.compile(
    r"^\s*<tool_call>\s*(\{.*\})\s*</tool_call>\s*$", re.DOTALL
)
TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any]


_VALID_TOOL_MODES = ("native", "text", "auto")


@dataclass
class ToolRuntimeConfig:
    enabled_tools: List[str]
    fixture_path: Path
    max_steps: int = 4
    max_result_chars: int = 6000
    tool_mode: Literal["native", "text", "auto"] = "text"

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["ToolRuntimeConfig"]:
        if not isinstance(data, dict):
            return None

        enabled_tools = data.get("enabled_tools")
        fixture_path = data.get("fixture_path")
        if not isinstance(enabled_tools, list) or not enabled_tools:
            return None
        if not isinstance(fixture_path, str) or not fixture_path.strip():
            return None

        raw_mode = str(data.get("tool_mode") or "text")
        tool_mode: Literal["native", "text", "auto"] = (
            raw_mode if raw_mode in _VALID_TOOL_MODES else "text"  # type: ignore[assignment]
        )

        return cls(
            enabled_tools=[str(item) for item in enabled_tools],
            fixture_path=Path(fixture_path),
            max_steps=max(1, int(data.get("max_steps") or 4)),
            max_result_chars=max(500, int(data.get("max_result_chars") or 6000)),
            tool_mode=tool_mode,
        )


def parse_tool_call(text: str) -> Optional[ToolCall]:
    match = TOOL_CALL_PATTERN.match(text or "")
    if match is None:
        return None

    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    name = payload.get("name")
    arguments = payload.get("arguments") or {}
    if not isinstance(name, str) or not name.strip():
        return None
    if not isinstance(arguments, dict):
        return None

    return ToolCall(name=name.strip(), arguments=arguments)


_OPENAI_TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "web_search": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "ウェブ検索を実行し、関連する結果を返す。各結果には url、title、snippet が含まれる。詳細なページ内容を読みたい場合は、結果の url を fetch_webpage に渡してください。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "検索クエリ"},
                },
                "required": ["query"],
            },
        },
    },
    "fetch_webpage": {
        "type": "function",
        "function": {
            "name": "fetch_webpage",
            "description": "指定した URL の Web ページを取得して全文を返す。web_search の結果にある url フィールドを使用してください。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "取得する Web ページの URL"},
                },
                "required": ["url"],
            },
        },
    },
}


class LocalToolRuntime:
    def __init__(self, config: ToolRuntimeConfig):
        self.config = config
        self._fixture: Optional[Dict[str, Any]] = None

    def build_openai_tools_schema(self) -> List[Dict[str, Any]]:
        return [
            _OPENAI_TOOL_SCHEMAS[name]
            for name in self.config.enabled_tools
            if name in _OPENAI_TOOL_SCHEMAS
        ]

    def render_tool_instruction(self) -> str:
        tools = ", ".join(f"`{name}`" for name in self.config.enabled_tools)
        return (
            "必要ならローカル検索ツールを使ってから回答してください。\n"
            f"利用可能なツール: {tools}\n"
            "ツールを使う場合は、回答本文ではなく次の形式だけを返してください。\n"
            "<tool_call>\n"
            '{"name":"web_search","arguments":{"query":"..."}}\n'
            "</tool_call>\n"
            "最終回答では通常の文章だけを返し、参照した根拠の title または URL を明記してください。"
        )

    def execute(self, call: ToolCall) -> Dict[str, Any]:
        if call.name not in self.config.enabled_tools:
            return {
                "name": call.name,
                "ok": False,
                "error": f"unknown tool: {call.name}",
            }

        if call.name == "web_search":
            query = str(call.arguments.get("query") or "").strip()
            return {
                "name": call.name,
                "ok": True,
                "query": query,
                "results": self._search(query),
            }

        if call.name == "fetch_webpage":
            url = str(call.arguments.get("url") or "").strip()
            return self._fetch_webpage(url)

        return {
            "name": call.name,
            "ok": False,
            "error": f"unsupported tool: {call.name}",
        }

    def summarize_result(self, result: Dict[str, Any]) -> str:
        if not result.get("ok"):
            return str(result.get("error") or "tool error")

        if result.get("name") == "web_search":
            titles = [
                str(item.get("title") or item.get("url") or "")
                for item in result.get("results", [])[:3]
            ]
            return "; ".join(title for title in titles if title) or "0 results"

        if result.get("name") == "fetch_webpage":
            return str(result.get("title") or result.get("url") or "document")

        return "ok"

    def render_tool_result(self, result: Dict[str, Any]) -> str:
        payload = json.dumps(result, ensure_ascii=False)
        if len(payload) > self.config.max_result_chars:
            payload = payload[: self.config.max_result_chars] + "..."
        return f"<tool_result>\n{payload}\n</tool_result>"

    def format_result_for_trace(self, result: Dict[str, Any]) -> str:
        payload = json.dumps(result, ensure_ascii=False)
        if len(payload) > self.config.max_result_chars:
            payload = payload[: self.config.max_result_chars] + "..."
        return payload

    def _load_fixture(self) -> Dict[str, Any]:
        if self._fixture is None:
            with self.config.fixture_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("tool fixture must be a JSON object")
            self._fixture = data
        return self._fixture

    def _documents(self) -> List[Dict[str, Any]]:
        fixture = self._load_fixture()
        documents = fixture.get("documents")
        return documents if isinstance(documents, list) else []

    def _query_snapshots(self) -> List[Dict[str, Any]]:
        fixture = self._load_fixture()
        snapshots = fixture.get("query_snapshots")
        if isinstance(snapshots, list):
            return snapshots

        legacy_results = fixture.get("search_results")
        if isinstance(legacy_results, dict):
            return [
                {
                    "query": fixture.get("query", ""),
                    "results": legacy_results.get("results", []),
                }
            ]

        return []

    def _documents_by_url(self) -> Dict[str, Dict[str, Any]]:
        by_url: Dict[str, Dict[str, Any]] = {}
        for document in self._documents():
            if not isinstance(document, dict):
                continue
            url = str(document.get("url") or "").strip()
            if url:
                by_url[url] = document
        return by_url

    def _search(self, query: str) -> List[Dict[str, Any]]:
        documents = self._documents_by_url()
        query_tokens = self._tokenize(query)
        best_by_url: Dict[str, tuple[int, int, str, Dict[str, Any]]] = {}

        for snapshot_index, snapshot in enumerate(self._query_snapshots()):
            if not isinstance(snapshot, dict):
                continue
            snapshot_query = str(snapshot.get("query") or "")
            raw_results = snapshot.get("results")
            if not isinstance(raw_results, list):
                continue

            for index, item in enumerate(raw_results):
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "")
                snippet = str(item.get("snippet") or item.get("content") or "")
                url = str(item.get("url") or "")
                document = documents.get(url) or {}
                text = str(document.get("text") or "")
                haystack = " ".join(
                    [snapshot_query, title, snippet, url, text[:400]]
                ).lower()
                score = self._score(query_tokens, haystack)
                if score <= 0:
                    continue

                # 同じ URL はより高いスコアのものだけを保持
                if url in best_by_url and best_by_url[url][0] >= score:
                    continue

                best_by_url[url] = (
                    score,
                    int(item.get("rank") or index),
                    title or url,
                    {
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                        "rank": int(item.get("rank") or (index + 1)),
                        "score": score,
                        "source_query": snapshot_query,
                        "source_query_index": snapshot_index,
                    },
                )

        scored = [
            (-entry[0], entry[1], entry[2], entry[3])
            for entry in best_by_url.values()
        ]
        scored.sort(key=lambda entry: entry[:3])
        return [entry[3] for entry in scored[:5]]

    def _fetch_webpage(self, url: str) -> Dict[str, Any]:
        document = self._documents_by_url().get(url)
        if document is None:
            return {
                "name": "fetch_webpage",
                "ok": False,
                "error": f"page not found: {url}",
            }

        return {
            "name": "fetch_webpage",
            "ok": True,
            "url": url,
            "title": document.get("title"),
            "source_type": document.get("source_type"),
            "published_at": document.get("published_at"),
            "fetch_status": document.get("fetch_status"),
            "notes": document.get("notes"),
            "text": document.get("text"),
        }

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [token.lower() for token in TOKEN_PATTERN.findall(text or "") if token]

    @classmethod
    def _score(cls, query_tokens: List[str], haystack: str) -> int:
        if not query_tokens:
            return 0
        score = 0
        for token in query_tokens:
            if token in haystack:
                score += max(1, len(token.split("-")))
        return score
