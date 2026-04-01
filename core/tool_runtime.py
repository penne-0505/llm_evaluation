"""被験モデル向けのローカル tool runtime"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


TOOL_CALL_PATTERN = re.compile(
    r"^\s*<tool_call>\s*(\{.*\})\s*</tool_call>\s*$", re.DOTALL
)
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_.\-/]+")


@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolRuntimeConfig:
    enabled_tools: List[str]
    fixture_path: Path
    max_steps: int = 4
    max_result_chars: int = 6000

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

        return cls(
            enabled_tools=[str(item) for item in enabled_tools],
            fixture_path=Path(fixture_path),
            max_steps=max(1, int(data.get("max_steps") or 4)),
            max_result_chars=max(500, int(data.get("max_result_chars") or 6000)),
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


class LocalToolRuntime:
    def __init__(self, config: ToolRuntimeConfig):
        self.config = config
        self._fixture: Optional[Dict[str, Any]] = None

    def render_tool_instruction(self) -> str:
        tools = ", ".join(f"`{name}`" for name in self.config.enabled_tools)
        return (
            "必要ならローカル検索ツールを使ってから回答してください。\n"
            f"利用可能なツール: {tools}\n"
            "ツールを使う場合は、回答本文ではなく次の形式だけを返してください。\n"
            "<tool_call>\n"
            '{"name":"web-search","arguments":{"query":"..."}}\n'
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

        if call.name == "web-search":
            query = str(call.arguments.get("query") or "").strip()
            return {
                "name": call.name,
                "ok": True,
                "query": query,
                "results": self._search(query),
            }

        if call.name == "open-document":
            doc_id = str(
                call.arguments.get("doc_id")
                or call.arguments.get("id")
                or call.arguments.get("url")
                or ""
            ).strip()
            return self._open_document(doc_id)

        return {
            "name": call.name,
            "ok": False,
            "error": f"unsupported tool: {call.name}",
        }

    def summarize_result(self, result: Dict[str, Any]) -> str:
        if not result.get("ok"):
            return str(result.get("error") or "tool error")

        if result.get("name") == "web-search":
            titles = [
                str(item.get("title") or item.get("url") or "")
                for item in result.get("results", [])[:3]
            ]
            return "; ".join(title for title in titles if title) or "0 results"

        if result.get("name") == "open-document":
            return str(result.get("title") or result.get("url") or "document")

        return "ok"

    def render_tool_result(self, result: Dict[str, Any]) -> str:
        payload = json.dumps(result, ensure_ascii=False)
        if len(payload) > self.config.max_result_chars:
            payload = payload[: self.config.max_result_chars] + "..."
        return f"<tool_result>\n{payload}\n</tool_result>"

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

    def _documents_by_id(self) -> Dict[str, Dict[str, Any]]:
        by_id: Dict[str, Dict[str, Any]] = {}
        for document in self._documents():
            if not isinstance(document, dict):
                continue
            doc_id = str(
                document.get("id")
                or document.get("doc_id")
                or document.get("url")
                or ""
            ).strip()
            if doc_id:
                by_id[doc_id] = document
        return by_id

    def _search(self, query: str) -> List[Dict[str, Any]]:
        documents = self._documents_by_id()
        query_tokens = self._tokenize(query)
        scored: List[tuple[int, int, str, Dict[str, Any]]] = []

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
                doc_id = str(
                    item.get("doc_id") or url or f"result-{snapshot_index}-{index}"
                )
                document = documents.get(doc_id) or documents.get(url) or {}
                text = str(document.get("text") or "")
                haystack = " ".join(
                    [snapshot_query, title, snippet, url, text[:400]]
                ).lower()
                score = self._score(query_tokens, haystack)
                scored.append(
                    (
                        -score,
                        int(item.get("rank") or index),
                        title or url,
                        {
                            "doc_id": doc_id,
                            "title": title,
                            "url": url,
                            "snippet": snippet,
                            "rank": int(item.get("rank") or (index + 1)),
                            "score": score,
                            "source_query": snapshot_query,
                            "source_query_index": snapshot_index,
                        },
                    )
                )

        scored.sort(key=lambda entry: entry[:3])
        return [entry[3] for entry in scored[:5]]

    def _open_document(self, doc_id: str) -> Dict[str, Any]:
        document = self._documents_by_id().get(doc_id)
        if document is None:
            return {
                "name": "open-document",
                "ok": False,
                "error": f"document not found: {doc_id}",
            }

        return {
            "name": "open-document",
            "ok": True,
            "doc_id": doc_id,
            "title": document.get("title"),
            "url": document.get("url"),
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
