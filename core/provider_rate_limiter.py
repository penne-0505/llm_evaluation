"""プロセス共有のプロバイダ別レート制限。

intent: DEC-003/005 (Core/concurrent-evaluation-jobs) — provider_id キーの共有
sliding window。レート待ちは cancel_checker で中断可能。
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict, Optional

from core.rate_limit_store import RateLimitStore


class ProviderRateLimiter:
    """評価ジョブ横断で共有するプロバイダ別リミッタ（プロセスシングルトン）。"""

    _lock: asyncio.Lock | None = None
    _timestamps: Dict[str, Deque[float]] = defaultdict(deque)
    # テスト用: 単調時計を差し替え可能
    _time_fn: Callable[[], float] = time.monotonic

    @classmethod
    def reset_for_tests(cls) -> None:
        cls._timestamps = defaultdict(deque)
        cls._lock = None
        cls._time_fn = time.monotonic

    @classmethod
    def set_time_fn(cls, time_fn: Callable[[], float]) -> None:
        cls._time_fn = time_fn

    @classmethod
    def _ensure_lock(cls) -> asyncio.Lock:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    def _prune(cls, provider_id: str, window_seconds: float, now: float) -> Deque[float]:
        bucket = cls._timestamps[provider_id]
        cutoff = now - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        return bucket

    @classmethod
    async def acquire(
        cls,
        provider_id: str,
        *,
        cancel_checker: Optional[Callable[[], None]] = None,
        on_waiting: Optional[Callable[[], None]] = None,
        poll_interval_sec: float = 0.05,
    ) -> None:
        """窓内枠が空くまで待つ。キャンセル時は CancelledError を送出する。"""
        pid = str(provider_id or "").strip() or "unknown"
        notified = False
        lock = cls._ensure_lock()

        while True:
            if cancel_checker:
                cancel_checker()

            config = RateLimitStore.resolve(pid)
            max_requests = config.max_requests
            window_seconds = float(config.window_seconds)

            async with lock:
                now = cls._time_fn()
                bucket = cls._prune(pid, window_seconds, now)
                if len(bucket) < max_requests:
                    bucket.append(now)
                    return
                oldest = bucket[0]
                wait_for = max(0.0, (oldest + window_seconds) - now)

            if not notified and on_waiting:
                on_waiting()
                notified = True

            sleep_for = min(poll_interval_sec, wait_for) if wait_for > 0 else poll_interval_sec
            try:
                await asyncio.sleep(sleep_for)
            except asyncio.CancelledError:
                raise
