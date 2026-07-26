"""index.json の並行更新に対する regression test。

対象: Core-Bug-71 / _docs/intent/Core/result-index-integrity/decision.md

本番の並行構造を模す。
  - POST /api/run は async def → event loop thread で ResultStorage.save()
  - GET / DELETE /api/results は同期 def → FastAPI の threadpool thread
両者が index を read-modify-write するため、排他が無いと lost update と破損が起きる。

競合の強制方法について。修正前の再現では `_load_index` に barrier を置いて
両スレッドを揃えたが、ロック導入後は「ロック保持中に barrier で待つ」形になり
デッドロックする。そのためここでは、ロック区間の内側（`_load_index`）に短い sleep を
入れて保持時間を伸ばし、後続スレッドがロック待ちに入る状況を作る。
排他が無い実装では、この sleep 中に他スレッドが古い index を読んで上書きするため落ちる。
"""

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List

from core.result_storage import ResultStorage


def _make_result(run_id: str) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "target_model": run_id,
        "judge_models": ["judge"],
        "executed_at": "2026-07-26T00:00:00Z",
        "tasks": [],
        "holistic_tasks": [],
        "average_score": 1,
        "best_score": 1,
    }


class TestResultIndexConcurrency(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.results_dir = Path(self._tmp.name)
        ResultStorage.RESULTS_DIR = self.results_dir
        self._original_load = ResultStorage._load_index.__func__

    def tearDown(self) -> None:
        ResultStorage._load_index = classmethod(self._original_load)
        ResultStorage.RESULTS_DIR = None
        self._tmp.cleanup()

    def _slow_down_critical_section(self, seconds: float = 0.02) -> None:
        """ロック区間の内側を遅くし、他スレッドを確実にロック待ちへ入らせる。"""
        original = self._original_load

        def slow_load(cls):
            index = original(cls)
            time.sleep(seconds)
            return index

        ResultStorage._load_index = classmethod(slow_load)

    def _read_index(self) -> List[Dict[str, Any]]:
        return json.loads(ResultStorage.index_file().read_text(encoding="utf-8"))

    def test_concurrent_saves_do_not_lose_entries(self) -> None:
        """AC-001 / INV-002: 並行 save の結果がどれも index から失われない。"""
        self._slow_down_critical_section()

        run_ids = [f"run{i}" for i in range(6)]
        threads = [
            threading.Thread(target=ResultStorage.save, args=(_make_result(rid),))
            for rid in run_ids
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        indexed = {entry.get("run_id") for entry in self._read_index()}
        for rid in run_ids:
            self.assertIn(rid, indexed, f"{rid} が index から失われた")

    def test_concurrent_save_and_delete_stay_consistent(self) -> None:
        """AC-001 / AC-003: save と delete が交錯しても index が実態と一致する。"""
        victim_path = ResultStorage.save(_make_result("victim"))
        ResultStorage.save(_make_result("keeper"))

        self._slow_down_critical_section()

        saver = threading.Thread(
            target=ResultStorage.save, args=(_make_result("newrun"),)
        )
        deleter = threading.Thread(target=ResultStorage.delete, args=(victim_path,))
        saver.start()
        deleter.start()
        saver.join()
        deleter.join()

        indexed = {entry.get("run_id") for entry in self._read_index()}
        self.assertIn("newrun", indexed, "保存した run が index から失われた")
        self.assertIn("keeper", indexed, "無関係な run が巻き添えで消えた")
        self.assertNotIn(
            "victim", indexed, "削除した結果の entry が index に残っている"
        )

    def test_index_file_always_parses_under_concurrency(self) -> None:
        """AC-002 / INV-001: 並行更新中に index.json が壊れた状態で観測されない。"""
        self._slow_down_critical_section(seconds=0.005)

        stop = threading.Event()
        parse_failures: List[str] = []

        def reader() -> None:
            index_file = ResultStorage.index_file()
            while not stop.is_set():
                if index_file.exists():
                    try:
                        json.loads(index_file.read_text(encoding="utf-8"))
                    except json.JSONDecodeError as exc:
                        parse_failures.append(str(exc))
                time.sleep(0.001)

        reader_thread = threading.Thread(target=reader, daemon=True)
        reader_thread.start()

        writers = [
            threading.Thread(target=ResultStorage.save, args=(_make_result(f"r{i}"),))
            for i in range(8)
        ]
        for t in writers:
            t.start()
        for t in writers:
            t.join()

        stop.set()
        reader_thread.join(timeout=2)

        self.assertEqual(parse_failures, [], "index.json が壊れた状態で観測された")

    def test_save_index_leaves_previous_content_on_failure(self) -> None:
        """INV-001: 書き込みが途中で失敗しても、既存の index が壊れない。"""
        ResultStorage.save(_make_result("before"))
        before = self._read_index()

        original_dump = json.dump

        def failing_dump(obj, fp, **kwargs):
            fp.write('[{"partial": ')
            raise RuntimeError("simulated write failure")

        json.dump = failing_dump
        try:
            with self.assertRaises(RuntimeError):
                ResultStorage._save_index([{"run_id": "after"}])
        finally:
            json.dump = original_dump

        self.assertEqual(
            self._read_index(), before, "失敗した書き込みが既存 index を壊した"
        )

    def test_failed_write_does_not_leave_temp_files(self) -> None:
        """一時ファイルが失敗時に残らない（結果一覧の走査を汚さない）。"""
        ResultStorage.save(_make_result("before"))

        original_dump = json.dump

        def failing_dump(obj, fp, **kwargs):
            raise RuntimeError("simulated write failure")

        json.dump = failing_dump
        try:
            with self.assertRaises(RuntimeError):
                ResultStorage._save_index([{"run_id": "after"}])
        finally:
            json.dump = original_dump

        leftovers = list(self.results_dir.glob(".index-*.tmp"))
        self.assertEqual(leftovers, [], f"一時ファイルが残っている: {leftovers}")


if __name__ == "__main__":
    unittest.main()
