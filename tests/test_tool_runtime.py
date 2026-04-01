"""tool runtime の単体テスト"""

import json
import tempfile
import unittest
from pathlib import Path

from core.tool_runtime import LocalToolRuntime, ToolRuntimeConfig, parse_tool_call


class TestToolRuntime(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.fixture_path = Path(self._tmp_dir.name) / "fixture.json"
        self.fixture_path.write_text(
            json.dumps(
                {
                    "query_snapshots": [
                        {
                            "query": "deep research model update",
                            "results": [
                                {
                                    "rank": 1,
                                    "doc_id": "doc-a",
                                    "title": "Deep Research shopping update",
                                    "url": "https://example.com/a",
                                    "content": "shopping feature, internal model unchanged",
                                },
                                {
                                    "rank": 2,
                                    "doc_id": "doc-b",
                                    "title": "GPT-5.2 release",
                                    "url": "https://example.com/b",
                                    "content": "general release note",
                                },
                            ],
                        }
                    ],
                    "documents": [
                        {
                            "id": "doc-a",
                            "url": "https://example.com/a",
                            "title": "Deep Research shopping update",
                            "text": "The internal Deep Research model remained unchanged.",
                        },
                        {
                            "id": "doc-b",
                            "url": "https://example.com/b",
                            "title": "GPT-5.2 release",
                            "text": "This is a general model release note.",
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.runtime = LocalToolRuntime(
            ToolRuntimeConfig(
                enabled_tools=["web-search", "open-document"],
                fixture_path=self.fixture_path,
            )
        )

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_parse_tool_call_accepts_expected_shape(self):
        tool_call = parse_tool_call(
            '<tool_call>{"name":"web-search","arguments":{"query":"deep research"}}</tool_call>'
        )

        self.assertIsNotNone(tool_call)
        assert tool_call is not None
        self.assertEqual(tool_call.name, "web-search")
        self.assertEqual(tool_call.arguments["query"], "deep research")

    def test_parse_tool_call_rejects_extra_text(self):
        self.assertIsNone(
            parse_tool_call(
                'before<tool_call>{"name":"web-search","arguments":{}}</tool_call>'
            )
        )

    def test_web_search_returns_ranked_results(self):
        tool_call = parse_tool_call(
            '<tool_call>{"name":"web-search","arguments":{"query":"deep research shopping"}}</tool_call>'
        )
        assert tool_call is not None
        result = self.runtime.execute(tool_call)

        self.assertTrue(result["ok"])
        self.assertEqual(result["results"][0]["doc_id"], "doc-a")
        self.assertEqual(
            result["results"][0]["source_query"], "deep research model update"
        )

    def test_open_document_returns_document_body(self):
        tool_call = parse_tool_call(
            '<tool_call>{"name":"open-document","arguments":{"doc_id":"doc-a"}}</tool_call>'
        )
        assert tool_call is not None
        result = self.runtime.execute(tool_call)

        self.assertTrue(result["ok"])
        self.assertIn("unchanged", result["text"])


if __name__ == "__main__":
    unittest.main()
