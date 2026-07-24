"""Tests for concurrent jobs registry and provider rate limits."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import server
from core.active_run_registry import ActiveRunRegistry
from core.app_paths import AppPaths
from core.provider_rate_limiter import ProviderRateLimiter
from core.rate_limit_store import (
    UNKNOWN_PROVIDER_DEFAULT,
    RateLimitStore,
    recommended_for,
)


class TestActiveRunRegistry(unittest.TestCase):
    def setUp(self) -> None:
        ActiveRunRegistry.reset_for_tests()

    def tearDown(self) -> None:
        ActiveRunRegistry.reset_for_tests()

    def test_allows_up_to_max_and_rejects_fourth(self) -> None:
        self.assertTrue(ActiveRunRegistry.try_start("r1"))
        self.assertTrue(ActiveRunRegistry.try_start("r2"))
        self.assertTrue(ActiveRunRegistry.try_start("r3"))
        self.assertFalse(ActiveRunRegistry.try_start("r4"))
        self.assertEqual(ActiveRunRegistry.active_count(), 3)
        ActiveRunRegistry.finish("r2")
        self.assertTrue(ActiveRunRegistry.try_start("r4"))
        self.assertEqual(ActiveRunRegistry.active_count(), 3)


class TestRateLimitStore(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "rate_limits.json"
        RateLimitStore.FILE_PATH = self.path

    def tearDown(self) -> None:
        RateLimitStore.FILE_PATH = None
        self._tmp.cleanup()

    def test_unknown_uses_conservative_default(self) -> None:
        cfg = recommended_for("some-custom-provider")
        self.assertEqual(cfg.max_requests, UNKNOWN_PROVIDER_DEFAULT["max_requests"])
        self.assertTrue(cfg.is_default)

    def test_override_persists_and_resolve(self) -> None:
        RateLimitStore.save_overrides(
            {"openrouter": {"max_requests": 5, "window_seconds": 30}}
        )
        cfg = RateLimitStore.resolve("openrouter")
        self.assertEqual(cfg.max_requests, 5)
        self.assertEqual(cfg.window_seconds, 30)
        self.assertFalse(cfg.is_default)
        RateLimitStore.clear_overrides()
        cfg2 = RateLimitStore.resolve("openrouter")
        self.assertTrue(cfg2.is_default)


class TestProviderRateLimiter(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "rate_limits.json"
        RateLimitStore.FILE_PATH = self.path
        RateLimitStore.save_overrides(
            {"openrouter": {"max_requests": 2, "window_seconds": 10}}
        )
        ProviderRateLimiter.reset_for_tests()
        self._clock = [1000.0]

        def _now() -> float:
            return self._clock[0]

        ProviderRateLimiter.set_time_fn(_now)

    def tearDown(self) -> None:
        ProviderRateLimiter.reset_for_tests()
        RateLimitStore.FILE_PATH = None
        self._tmp.cleanup()

    async def test_sliding_window_blocks_until_slot(self) -> None:
        await ProviderRateLimiter.acquire("openrouter", poll_interval_sec=0.01)
        await ProviderRateLimiter.acquire("openrouter", poll_interval_sec=0.01)

        waiting = {"hit": False}

        async def _third() -> None:
            def on_wait() -> None:
                waiting["hit"] = True

            task = asyncio.create_task(
                ProviderRateLimiter.acquire(
                    "openrouter",
                    on_waiting=on_wait,
                    poll_interval_sec=0.01,
                )
            )
            await asyncio.sleep(0.03)
            self.assertTrue(waiting["hit"])
            self.assertFalse(task.done())
            self._clock[0] = 1011.0
            await asyncio.wait_for(task, timeout=1.0)

        await _third()

    async def test_cancel_during_wait(self) -> None:
        await ProviderRateLimiter.acquire("openrouter", poll_interval_sec=0.01)
        await ProviderRateLimiter.acquire("openrouter", poll_interval_sec=0.01)

        def cancel() -> None:
            raise asyncio.CancelledError("ユーザーによってキャンセルされました")

        with self.assertRaises(asyncio.CancelledError):
            await ProviderRateLimiter.acquire(
                "openrouter",
                cancel_checker=cancel,
                poll_interval_sec=0.01,
            )


class TestRateLimitAndActiveApis(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "rate_limits.json"
        RateLimitStore.FILE_PATH = self.path
        ActiveRunRegistry.reset_for_tests()
        self.client = TestClient(server.app)

    def tearDown(self) -> None:
        ActiveRunRegistry.reset_for_tests()
        RateLimitStore.FILE_PATH = None
        self._tmp.cleanup()

    def test_get_and_put_rate_limits(self) -> None:
        get_res = self.client.get("/api/rate-limits")
        self.assertEqual(get_res.status_code, 200)
        body = get_res.json()
        self.assertIn("providers", body)
        self.assertIn("openrouter", body["providers"])
        self.assertEqual(body["max_concurrent_jobs"], 3)

        put_res = self.client.put(
            "/api/rate-limits",
            json={
                "providers": {
                    "openrouter": {"max_requests": 7, "window_seconds": 45},
                }
            },
        )
        self.assertEqual(put_res.status_code, 200)
        openrouter = put_res.json()["providers"]["openrouter"]
        self.assertEqual(openrouter["max_requests"], 7)
        self.assertFalse(openrouter["is_default"])

        reset = self.client.post("/api/rate-limits/reset")
        self.assertEqual(reset.status_code, 200)
        self.assertTrue(reset.json()["providers"]["openrouter"]["is_default"])

    def test_active_endpoint_and_fourth_run_rejected(self) -> None:
        self.assertTrue(ActiveRunRegistry.try_start("a"))
        self.assertTrue(ActiveRunRegistry.try_start("b"))
        self.assertTrue(ActiveRunRegistry.try_start("c"))
        active = self.client.get("/api/run/active")
        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.json()["active_count"], 3)

        # POST /api/run will try to register a 4th; with empty/invalid body it may
        # fail validation first. Register via try_start already full — call run
        # with minimal valid-looking body; registry rejects before stream.
        with patch.object(ActiveRunRegistry, "try_start", return_value=False):
            res = self.client.post(
                "/api/run",
                json={
                    "target_model": "openrouter/x",
                    "judge_models": ["openrouter/y"],
                    "selected_task_ids": ["t1"],
                },
            )
        self.assertEqual(res.status_code, 409)


if __name__ == "__main__":
    unittest.main()
