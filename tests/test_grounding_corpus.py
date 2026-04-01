"""Grounding corpus の保存ストアテスト"""

import tempfile
import unittest
from pathlib import Path

from core.grounding_corpus import GroundingCorpusStore


class TestGroundingCorpusStore(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.records_dir = Path(self._tmp_dir.name) / "grounding_corpus"
        self.records_dir.mkdir(parents=True, exist_ok=True)

        self._orig_records_dir = GroundingCorpusStore.RECORDS_DIR
        self._orig_index_file = GroundingCorpusStore.INDEX_FILE
        GroundingCorpusStore.RECORDS_DIR = self.records_dir
        GroundingCorpusStore.INDEX_FILE = self.records_dir / "index.json"

    def tearDown(self) -> None:
        GroundingCorpusStore.RECORDS_DIR = self._orig_records_dir
        GroundingCorpusStore.INDEX_FILE = self._orig_index_file
        self._tmp_dir.cleanup()

    def test_save_load_and_list_records(self):
        record = {
            "id": "record-1",
            "query": "latest ai chip news",
            "captured_at": "2026-04-04T10:00:00Z",
            "search_results": {"results": [{"url": "https://example.com/a"}]},
            "documents": [
                {
                    "url": "https://example.com/a",
                    "title": "Example A",
                    "text": "document body",
                    "source_type": "article",
                }
            ],
            "notes": "verified source",
        }

        saved_path = GroundingCorpusStore.save(record)
        loaded = GroundingCorpusStore.load(saved_path)
        summaries = GroundingCorpusStore.list_records()

        self.assertEqual(saved_path.name, "record-1.json")
        self.assertEqual(loaded["query"], "latest ai chip news")
        self.assertEqual(loaded["documents"][0]["title"], "Example A")
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["id"], "record-1")
        self.assertEqual(summaries[0]["document_count"], 1)
        self.assertEqual(summaries[0]["search_result_count"], 1)


if __name__ == "__main__":
    unittest.main()
