"""同時評価ジョブの登録と上限。

intent: DEC-001 (Core/concurrent-evaluation-jobs) — 同時 running は最大 MAX_CONCURRENT。
"""

from __future__ import annotations

import threading
from typing import Dict, List


class ActiveRunRegistry:
    """プロセス内の active 評価ジョブ集合。"""

    MAX_CONCURRENT = 3

    _lock = threading.Lock()
    _active: Dict[str, float] = {}

    @classmethod
    def reset_for_tests(cls) -> None:
        with cls._lock:
            cls._active.clear()

    @classmethod
    def active_count(cls) -> int:
        with cls._lock:
            return len(cls._active)

    @classmethod
    def active_run_ids(cls) -> List[str]:
        with cls._lock:
            return list(cls._active.keys())

    @classmethod
    def try_start(cls, run_id: str) -> bool:
        """枠があれば登録して True。上限到達時は False（登録しない）。"""
        with cls._lock:
            if run_id in cls._active:
                return True
            if len(cls._active) >= cls.MAX_CONCURRENT:
                return False
            import time

            cls._active[run_id] = time.monotonic()
            return True

    @classmethod
    def finish(cls, run_id: str) -> None:
        with cls._lock:
            cls._active.pop(run_id, None)
