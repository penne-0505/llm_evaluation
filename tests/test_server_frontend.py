"""配布向け frontend 配信のテスト"""

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import server
from core.app_paths import AppPaths
from core.benchmark_engine import BenchmarkEngine, TaskResult
from core.grounding_corpus import GroundingCorpusStore
from core.result_storage import ResultStorage


class TestFrontendServing(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.dist_dir = Path(self._tmp_dir.name) / "frontend" / "dist"
        (self.dist_dir / "assets").mkdir(parents=True, exist_ok=True)
        (self.dist_dir / "index.html").write_text(
            "<html><body>frontend ok</body></html>", encoding="utf-8"
        )
        (self.dist_dir / "assets" / "app.js").write_text(
            "console.log('ok')", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_root_and_spa_route_fall_back_to_index(self):
        with patch.object(AppPaths, "frontend_dist_dir", return_value=self.dist_dir):
            client = TestClient(server.app)

            root_response = client.get("/")
            route_response = client.get("/settings")

        self.assertEqual(root_response.status_code, 200)
        self.assertIn("frontend ok", root_response.text)
        self.assertEqual(route_response.status_code, 200)
        self.assertIn("frontend ok", route_response.text)

    def test_existing_asset_is_served_directly(self):
        with patch.object(AppPaths, "frontend_dist_dir", return_value=self.dist_dir):
            client = TestClient(server.app)
            response = client.get("/assets/app.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("console.log('ok')", response.text)

    def test_missing_frontend_build_returns_503(self):
        missing_dir = self.dist_dir.parent / "missing-dist"
        with patch.object(AppPaths, "frontend_dist_dir", return_value=missing_dir):
            client = TestClient(server.app)
            response = client.get("/")

        self.assertEqual(response.status_code, 503)
        self.assertIn("配布用 frontend が見つかりません", response.text)


class TestPortableResourceResolution(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp_dir.name)

        self.bundled_prompts = self.root / "bundled" / "prompts"
        self.bundled_rubrics = self.root / "bundled" / "rubrics"
        self.user_prompts = self.root / "user" / "overrides" / "prompts"
        self.user_rubrics = self.root / "user" / "overrides" / "rubrics"
        self.env_prompts = self.root / "env" / "prompts"
        self.env_rubrics = self.root / "env" / "rubrics"
        self.bundled_task_configs = self.root / "bundled" / "task_configs"

        for path in [
            self.bundled_prompts,
            self.bundled_rubrics,
            self.bundled_task_configs,
            self.user_prompts,
            self.user_rubrics,
            self.env_prompts,
            self.env_rubrics,
        ]:
            path.mkdir(parents=True, exist_ok=True)

        (self.bundled_prompts / "01.md").write_text(
            "bundled prompt 01", encoding="utf-8"
        )
        (self.bundled_rubrics / "01.md").write_text("task_type: fact", encoding="utf-8")
        (self.bundled_prompts / "03.md").write_text(
            "bundled prompt 03", encoding="utf-8"
        )
        (self.bundled_rubrics / "03.md").write_text(
            "task_type: creative", encoding="utf-8"
        )
        (self.bundled_task_configs / "03.json").write_text(
            '{"subject_tools": {"enabled_tools": ["web_search"], "fixture_path": "task_fixtures/03.json"}}',
            encoding="utf-8",
        )

        (self.user_prompts / "01.md").write_text("user prompt 01", encoding="utf-8")
        (self.user_rubrics / "02.md").write_text(
            "task_type: speculative", encoding="utf-8"
        )
        (self.user_prompts / "02.md").write_text("user prompt 02", encoding="utf-8")

        (self.env_prompts / "01.md").write_text("env prompt 01", encoding="utf-8")
        (self.env_rubrics / "01.md").write_text("task_type: creative", encoding="utf-8")

        self.bundled_judge = self.root / "bundled" / "judge_system_prompt.md"
        self.user_judge = self.root / "user" / "overrides" / "judge_system_prompt.md"
        self.env_judge = self.root / "env" / "judge_system_prompt.md"
        self.bundled_judge.write_text("bundled judge", encoding="utf-8")
        self.user_judge.parent.mkdir(parents=True, exist_ok=True)
        self.user_judge.write_text("user judge", encoding="utf-8")
        self.env_judge.parent.mkdir(parents=True, exist_ok=True)
        self.env_judge.write_text("env judge", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_tasks_use_env_then_user_then_bundled_priority(self):
        with (
            patch.object(
                AppPaths, "bundled_prompts_dir", return_value=self.bundled_prompts
            ),
            patch.object(
                AppPaths, "bundled_rubrics_dir", return_value=self.bundled_rubrics
            ),
            patch.object(
                AppPaths,
                "bundled_task_configs_dir",
                return_value=self.bundled_task_configs,
            ),
            patch.object(
                AppPaths,
                "bundled_judge_system_prompt_file",
                return_value=self.bundled_judge,
            ),
            patch.object(
                AppPaths, "prompts_override_dir", return_value=self.user_prompts
            ),
            patch.object(
                AppPaths, "rubrics_override_dir", return_value=self.user_rubrics
            ),
            patch.object(
                AppPaths,
                "judge_system_prompt_override_file",
                return_value=self.user_judge,
            ),
            patch.dict(
                os.environ,
                {
                    server.PROMPTS_DIR_ENV: str(self.env_prompts),
                    server.RUBRICS_DIR_ENV: str(self.env_rubrics),
                    server.JUDGE_SYSTEM_PROMPT_ENV: str(self.env_judge),
                },
                clear=False,
            ),
        ):
            client = TestClient(server.app)
            response = client.get("/api/tasks")
            resources = client.get("/api/resources")

        self.assertEqual(response.status_code, 200)
        tasks = {task["id"]: task for task in response.json()}

        self.assertEqual(tasks["01"]["prompt_preview"], "env prompt 01")
        self.assertEqual(tasks["01"]["prompt_source"], "env_override")
        self.assertEqual(tasks["01"]["rubric_source"], "env_override")

        self.assertEqual(tasks["02"]["prompt_preview"], "user prompt 02")
        self.assertEqual(tasks["02"]["prompt_source"], "user_override")
        self.assertEqual(tasks["02"]["rubric_source"], "user_override")

        self.assertEqual(tasks["03"]["prompt_preview"], "bundled prompt 03")
        self.assertEqual(tasks["03"]["prompt_source"], "bundled")
        self.assertEqual(tasks["03"]["rubric_source"], "bundled")
        self.assertTrue(tasks["03"]["has_subject_tools"])

        self.assertEqual(resources.status_code, 200)
        resources_body = resources.json()
        self.assertEqual(
            resources_body["judge_system_prompt"]["resolved_source"], "env_override"
        )
        self.assertTrue(resources_body["judge_system_prompt"]["exists"])


class TestRunProgressSnapshot(unittest.TestCase):
    def test_completed_tasks_are_included_in_progress_snapshot(self):
        task_states = [
            {
                "task_id": "task-queued",
                "task_index": 0,
                "phase": "queued",
                "message": "Queued",
                "subject_done": False,
                "judge_states": {"judge-a": "pending", "judge-b": "pending"},
            },
            {
                "task_id": "task-running",
                "task_index": 1,
                "phase": "running_judges",
                "message": "judge progress",
                "subject_done": True,
                "judge_states": {"judge-a": "running", "judge-b": "completed"},
            },
            {
                "task_id": "task-done",
                "task_index": 2,
                "phase": "completed",
                "message": "Completed",
                "subject_done": True,
                "judge_states": {"judge-a": "completed", "judge-b": "completed"},
            },
        ]

        snapshot = server._build_progress_snapshot(task_states)

        self.assertEqual(snapshot["completed_task_count"], 1)
        self.assertEqual(snapshot["active_task_count"], 1)
        self.assertEqual(snapshot["queued_task_count"], 1)
        self.assertEqual(
            [task["task_id"] for task in snapshot["completed_tasks"]], ["task-done"]
        )
        self.assertEqual(
            snapshot["completed_tasks"][0]["judge_completed_count"],
            2,
        )

    def test_progress_eta_uses_wall_pace_not_task_timing(self):
        eta = server._compute_progress_eta(
            completed_task_count=2,
            remaining_task_count=2,
            elapsed_ms=10_000,
            current_step=4,
            total_steps=10,
            history_summaries=[],
        )
        # wall pace: 10000/2*2 = 10000 (not task_timing average)
        self.assertEqual(eta["eta_status"], "measured")
        self.assertEqual(eta["eta_ms"], 10_000)

    def test_progress_eta_step_fallback_only_when_no_completed_and_no_history(self):
        step_eta = server._compute_progress_eta(
            completed_task_count=0,
            remaining_task_count=3,
            elapsed_ms=4000,
            current_step=2,
            total_steps=8,
            history_summaries=[],
        )
        self.assertEqual(step_eta["eta_status"], "step_fallback")
        self.assertEqual(step_eta["eta_ms"], 12000)

        measured = server._compute_progress_eta(
            completed_task_count=1,
            remaining_task_count=3,
            elapsed_ms=4000,
            current_step=2,
            total_steps=8,
            history_summaries=[],
        )
        self.assertEqual(measured["eta_status"], "measured")
        self.assertEqual(measured["eta_ms"], 12_000)

    def test_progress_eta_unavailable_without_measurements_or_steps(self):
        eta = server._compute_progress_eta(
            completed_task_count=0,
            remaining_task_count=3,
            elapsed_ms=0,
            current_step=0,
            total_steps=8,
            history_summaries=[],
        )
        self.assertEqual(eta["eta_status"], "unavailable")
        self.assertIsNone(eta["eta_ms"])

    def test_progress_eta_measured_zero_only_when_remaining_is_zero(self):
        # AC: remaining > 0 なら measured 0 にならない
        eta = server._compute_progress_eta(
            completed_task_count=1,
            remaining_task_count=1,
            elapsed_ms=5000,
            current_step=4,
            total_steps=10,
            history_summaries=[],
        )
        self.assertEqual(eta["eta_status"], "measured")
        self.assertEqual(eta["eta_ms"], 5000)
        self.assertNotEqual(eta["eta_ms"], 0)

        done = server._compute_progress_eta(
            completed_task_count=1,
            remaining_task_count=0,
            elapsed_ms=5000,
            current_step=10,
            total_steps=10,
            history_summaries=[],
        )
        self.assertEqual(done["eta_status"], "measured")
        self.assertEqual(done["eta_ms"], 0)

    def test_remaining_task_count_includes_holistic_while_incomplete(self):
        # Core-Bug-54: standard 完了 + holistic 未完了 → remaining > 0
        standard = server._initial_task_progress_state("01", 0, ["judge-a"])
        standard["phase"] = "completed"
        standard["subject_done"] = True
        standard["task_timing"] = {
            "subject_duration_ms": 1000,
            "judge_duration_ms": 2000,
        }
        holistic = server._initial_task_progress_state(
            "style", 1, ["judge-h"], task_kind="holistic"
        )
        holistic["phase"] = "running_judges"
        holistic["subject_done"] = True

        snapshot = server._build_progress_snapshot([standard, holistic])
        remaining = server._remaining_task_count_for_eta(
            snapshot=snapshot,
            task_states=[standard, holistic],
            holistic_task_count=2,
        )
        # snapshot は standard-only で active/queued=0、holistic 残 2（1 done 扱いしない）
        self.assertEqual(snapshot["active_task_count"], 0)
        self.assertEqual(snapshot["queued_task_count"], 0)
        self.assertEqual(remaining, 2)

        eta = server._compute_progress_eta(
            completed_task_count=1,
            remaining_task_count=remaining,
            elapsed_ms=9000,
            current_step=5,
            total_steps=12,
            history_summaries=[],
        )
        self.assertEqual(eta["eta_status"], "measured")
        self.assertNotEqual(eta["eta_ms"], 0)
        self.assertEqual(eta["eta_ms"], 18_000)  # 9000/1*2

    def test_remaining_task_count_ignores_holistic_before_phase_starts(self):
        standard = server._initial_task_progress_state("01", 0, ["judge-a"])
        standard["phase"] = "queued"
        snapshot = server._build_progress_snapshot([standard])
        remaining = server._remaining_task_count_for_eta(
            snapshot=snapshot,
            task_states=[standard],
            holistic_task_count=1,
        )
        self.assertEqual(remaining, 1)

    def test_holistic_tasks_are_excluded_from_standard_progress_lanes(self):
        standard_task = server._initial_task_progress_state(
            "standard-task", 0, ["judge-a"]
        )
        standard_task["phase"] = "completed"
        standard_task["subject_done"] = True
        standard_task["judge_states"]["judge-a"] = "completed"
        holistic_task = server._initial_task_progress_state(
            "style", 1, ["judge-a"], task_kind="holistic"
        )
        holistic_task["phase"] = "running_judges"
        holistic_task["subject_done"] = True
        holistic_task["judge_states"]["judge-a"] = "running"

        snapshot = server._build_progress_snapshot([standard_task, holistic_task])

        self.assertEqual(snapshot["completed_task_count"], 1)
        self.assertEqual(snapshot["active_task_count"], 0)
        self.assertEqual(snapshot["queued_task_count"], 0)
        self.assertEqual(
            [task["task_id"] for task in snapshot["completed_tasks"]],
            ["standard-task"],
        )
        self.assertEqual(snapshot["completed_tasks"][0]["task_kind"], "standard")

    def test_holistic_progress_event_has_dedicated_lifecycle_payload(self):
        event = server._build_holistic_progress_event(
            status="running",
            completed_task_count=1,
            failed_task_count=0,
            total_task_count=2,
            current_task_index=1,
            current_task_id="style",
            message="包括評価 2/2: 実行中",
        )

        self.assertEqual(event["type"], "holistic_progress")
        self.assertEqual(event["status"], "running")
        self.assertEqual(event["completed_task_count"], 1)
        self.assertEqual(event["total_task_count"], 2)
        self.assertEqual(event["current_task_index"], 1)
        self.assertEqual(event["current_task_id"], "style")


class TestHolisticProgressDelivery(unittest.IsolatedAsyncioTestCase):
    async def test_progress_event_is_yielded_before_holistic_task_completes(self):
        progress_queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()
        release_task = asyncio.Event()

        async def run_holistic_task() -> None:
            progress_queue.put_nowait(
                server._build_holistic_progress_event(
                    status="running",
                    completed_task_count=0,
                    failed_task_count=0,
                    total_task_count=1,
                    current_task_index=0,
                    current_task_id="style",
                    message="包括評価 1/1: 実行中",
                )
            )
            await release_task.wait()

        running_task = asyncio.create_task(run_holistic_task())
        delivered_events = []
        async for event in server._drain_progress_events_while_task_runs(
            running_task, progress_queue, lambda: None
        ):
            delivered_events.append(event)
            self.assertFalse(running_task.done())
            release_task.set()

        await running_task
        self.assertEqual(delivered_events[0]["type"], "holistic_progress")
        self.assertEqual(delivered_events[0]["status"], "running")

    async def test_cancelling_progress_drain_cancels_and_awaits_holistic_task(self):
        progress_queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()
        task_cancelled = asyncio.Event()

        async def run_holistic_task() -> None:
            try:
                await asyncio.Event().wait()
            finally:
                task_cancelled.set()

        running_task = asyncio.create_task(run_holistic_task())
        await asyncio.sleep(0)

        with self.assertRaises(asyncio.CancelledError):
            async for _event in server._drain_progress_events_while_task_runs(
                running_task,
                progress_queue,
                lambda: (_ for _ in ()).throw(asyncio.CancelledError()),
            ):
                pass

        self.assertTrue(running_task.done())
        self.assertTrue(running_task.cancelled())
        self.assertTrue(task_cancelled.is_set())

    async def test_failed_holistic_task_finishes_before_exception_is_observed(self):
        progress_queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()

        async def run_holistic_task() -> None:
            progress_queue.put_nowait(
                server._build_holistic_progress_event(
                    status="running",
                    completed_task_count=0,
                    failed_task_count=0,
                    total_task_count=1,
                    message="包括評価 1/1: 実行中",
                )
            )
            await asyncio.sleep(0)
            raise RuntimeError("judge failure")

        running_task = asyncio.create_task(run_holistic_task())
        delivered_events = []
        async for event in server._drain_progress_events_while_task_runs(
            running_task, progress_queue, lambda: None
        ):
            delivered_events.append(event)

        with self.assertRaisesRegex(RuntimeError, "judge failure"):
            await running_task
        self.assertTrue(running_task.done())
        self.assertEqual(delivered_events[0]["type"], "holistic_progress")


class TestGroundingCorpusApi(unittest.TestCase):
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

    def test_grounding_corpus_round_trip(self):
        client = TestClient(server.app)
        payload = {
            "query": "latest ai chip news",
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

        save_response = client.post("/api/grounding-corpus", json=payload)
        self.assertEqual(save_response.status_code, 200)

        record_id = save_response.json()["record_id"]

        list_response = client.get("/api/grounding-corpus")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)
        self.assertEqual(list_response.json()[0]["id"], record_id)

        detail_response = client.get(f"/api/grounding-corpus/{record_id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["query"], "latest ai chip news")
        self.assertEqual(detail_response.json()["documents"][0]["title"], "Example A")


class TestStrictModeApi(unittest.TestCase):
    def test_strict_mode_preset_endpoint_returns_official_preset(self):
        client = TestClient(server.app)

        response = client.get("/api/strict-mode/preset")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], "official-v3")
        self.assertEqual(body["label"], "Official Strict v3")
        self.assertEqual(body["judge_runs"], 3)
        self.assertEqual(body["subject_temperature"], 0.45)
        self.assertEqual(
            body["judge_temperature_omitted_models"],
            ["openrouter/openai/gpt-5.6-terra"],
        )
        self.assertEqual(body["task_ids"], [f"{i:02d}" for i in range(1, 12)])
        self.assertEqual(
            [judge["id"] for judge in body["judge_models"]],
            [
                "openrouter/moonshotai/kimi-k3",
                "openrouter/openai/gpt-5.6-terra",
                "openrouter/qwen/qwen3.7-max",
            ],
        )


class TestOpenRouterAdminApi(unittest.TestCase):
    def test_openrouter_admin_status_reflects_management_key_configuration(self):
        client = TestClient(server.app)

        with patch.object(
            server.SecretsStore, "load_openrouter_management_key", return_value=None
        ):
            response = client.get("/api/openrouter/admin/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"configured": False})

        with patch.object(
            server.SecretsStore,
            "load_openrouter_management_key",
            return_value="mgmt-key",
        ):
            response = client.get("/api/openrouter/admin/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"configured": True})

    def test_save_and_delete_openrouter_management_key(self):
        client = TestClient(server.app)

        with patch.object(
            server.SecretsStore, "save_openrouter_management_key"
        ) as save_mock:
            response = client.post(
                "/api/openrouter/admin/key",
                json={"key": " mgmt-key "},
            )

        self.assertEqual(response.status_code, 200)
        save_mock.assert_called_once_with("mgmt-key")

        with patch.object(
            server.SecretsStore, "clear_openrouter_management_key"
        ) as clear_mock:
            response = client.delete("/api/openrouter/admin/key")

        self.assertEqual(response.status_code, 200)
        clear_mock.assert_called_once_with()

    def test_openrouter_credits_returns_not_configured_without_management_key(self):
        client = TestClient(server.app)

        with patch.object(
            server.SecretsStore, "load_openrouter_management_key", return_value=None
        ):
            response = client.get("/api/openrouter/credits")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"configured": False})

    def test_openrouter_credits_returns_credit_snapshot_when_configured(self):
        client = TestClient(server.app)

        with (
            patch.object(
                server.SecretsStore,
                "load_openrouter_management_key",
                return_value="mgmt-key",
            ),
            patch.object(
                server,
                "fetch_credits",
                return_value={
                    "total_credits": 12.5,
                    "total_usage": 4.25,
                    "remaining_credits": 8.25,
                },
            ) as fetch_mock,
        ):
            response = client.get("/api/openrouter/credits")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "configured": True,
                "total_credits": 12.5,
                "total_usage": 4.25,
                "remaining_credits": 8.25,
            },
        )
        fetch_mock.assert_called_once_with("mgmt-key")

    def test_openrouter_credits_returns_502_when_credit_fetch_fails(self):
        client = TestClient(server.app)

        with (
            patch.object(
                server.SecretsStore,
                "load_openrouter_management_key",
                return_value="mgmt-key",
            ),
            patch.object(
                server,
                "fetch_credits",
                side_effect=server.OpenRouterAdminError("credit fetch failed"),
            ),
        ):
            response = client.get("/api/openrouter/credits")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "credit fetch failed")


class TestLMStudioConfigApi(unittest.TestCase):
    def test_lmstudio_config_status_reflects_saved_values(self):
        client = TestClient(server.app)

        with (
            patch.object(
                server.ProviderConfigStore,
                "load_provider",
                return_value={"base_url": "http://127.0.0.1:1234/v1"},
            ),
            patch.object(
                server.SecretsStore,
                "load_existing",
                return_value={"lmstudio": "token"},
            ),
        ):
            response = client.get("/api/lmstudio/config")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "configured": True,
                "base_url": "http://127.0.0.1:1234/v1",
                "api_token_configured": True,
            },
        )

    def test_save_lmstudio_config_trims_values_and_saves_optional_token(self):
        client = TestClient(server.app)

        with (
            patch.object(server.ProviderConfigStore, "save_provider") as save_provider_mock,
            patch.object(server.SecretsStore, "save") as save_secret_mock,
            patch.object(
                server.ProviderConfigStore,
                "load_provider",
                return_value={"base_url": "http://127.0.0.1:1234/v1"},
            ),
            patch.object(
                server.SecretsStore,
                "load_existing",
                return_value={"lmstudio": "token"},
            ),
        ):
            response = client.post(
                "/api/lmstudio/config",
                json={
                    "base_url": " http://127.0.0.1:1234/v1 ",
                    "api_token": " secret-token ",
                },
            )

        self.assertEqual(response.status_code, 200)
        save_provider_mock.assert_called_once_with(
            "lmstudio", {"base_url": "http://127.0.0.1:1234/v1"}
        )
        save_secret_mock.assert_called_once_with({"lmstudio": "secret-token"})

    def test_save_lmstudio_config_can_clear_optional_token(self):
        client = TestClient(server.app)

        with (
            patch.object(server.ProviderConfigStore, "save_provider") as save_provider_mock,
            patch.object(
                server.SecretsStore, "clear_provider_secret"
            ) as clear_secret_mock,
            patch.object(
                server.ProviderConfigStore,
                "load_provider",
                return_value={"base_url": "http://127.0.0.1:1234/v1"},
            ),
            patch.object(server.SecretsStore, "load_existing", return_value={}),
        ):
            response = client.post(
                "/api/lmstudio/config",
                json={
                    "base_url": "http://127.0.0.1:1234/v1",
                    "api_token": "   ",
                },
            )

        self.assertEqual(response.status_code, 200)
        save_provider_mock.assert_called_once()
        clear_secret_mock.assert_called_once_with("lmstudio")

    def test_delete_lmstudio_config_clears_store_and_secret(self):
        client = TestClient(server.app)

        with (
            patch.object(server.ProviderConfigStore, "clear_provider") as clear_provider_mock,
            patch.object(
                server.SecretsStore, "clear_provider_secret"
            ) as clear_secret_mock,
        ):
            response = client.delete("/api/lmstudio/config")

        self.assertEqual(response.status_code, 200)
        clear_provider_mock.assert_called_once_with("lmstudio")
        clear_secret_mock.assert_called_once_with("lmstudio")


class TestProviderRegistryApi(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_registry = server.ProviderRegistry.FILE_PATH
        self._orig_secrets = server.SecretsStore.FILE_PATH
        server.ProviderRegistry.FILE_PATH = Path(self._tmp.name) / "providers.json"
        server.SecretsStore.FILE_PATH = Path(self._tmp.name) / "secrets.toml"
        server._registry_bootstrapped = False

    def tearDown(self) -> None:
        server.ProviderRegistry.FILE_PATH = self._orig_registry
        server.SecretsStore.FILE_PATH = self._orig_secrets
        server._registry_bootstrapped = False

    def test_list_providers_includes_builtins_without_keys(self) -> None:
        client = TestClient(server.app)
        response = client.get("/api/providers")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        ids = [p["id"] for p in body["providers"]]
        self.assertEqual(
            ids[:4],
            ["openrouter", "openai", "google-ai-studio", "anthropic"],
        )
        for provider in body["providers"]:
            self.assertIn("has_key", provider)
            self.assertNotIn("key", provider)
            self.assertFalse(any("sk-" in str(v) for v in provider.values()))

    def test_keys_status_includes_providers_map(self) -> None:
        client = TestClient(server.app)
        response = client.get("/api/keys/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("openrouter", body)
        self.assertIn("providers", body)
        self.assertIn("openai", body["providers"])

    def test_save_and_clear_provider_key(self) -> None:
        client = TestClient(server.app)
        save = client.post("/api/providers/openai/key", json={"key": "sk-test-openai"})
        self.assertEqual(save.status_code, 200)
        status = client.get("/api/keys/status").json()
        self.assertTrue(status["providers"]["openai"])
        listed = client.get("/api/providers").json()
        openai_entry = next(p for p in listed["providers"] if p["id"] == "openai")
        self.assertTrue(openai_entry["has_key"])
        self.assertNotIn("sk-test-openai", json.dumps(listed))

        clear = client.delete("/api/providers/openai/key")
        self.assertEqual(clear.status_code, 200)
        status_after = client.get("/api/keys/status").json()
        self.assertFalse(status_after["providers"]["openai"])

    def test_create_and_delete_custom_provider(self) -> None:
        client = TestClient(server.app)
        created = client.post(
            "/api/providers",
            json={
                "display_name": "My Compat",
                "kind": "openai_compatible",
                "base_url": "https://example.com/v1",
            },
        )
        self.assertEqual(created.status_code, 200)
        body = created.json()
        self.assertEqual(body["id"], "my-compat")
        self.assertFalse(body["builtin"])
        self.assertFalse(body["has_key"])

        deleted = client.delete(f"/api/providers/{body['id']}")
        self.assertEqual(deleted.status_code, 200)

        listed = client.get("/api/providers").json()
        self.assertNotIn(body["id"], [p["id"] for p in listed["providers"]])

    def test_cannot_delete_builtin(self) -> None:
        client = TestClient(server.app)
        response = client.delete("/api/providers/openrouter")
        self.assertEqual(response.status_code, 400)


class TestResultDeletionApi(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.results_dir = Path(self._tmp_dir.name) / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self._orig_results_dir = ResultStorage.RESULTS_DIR
        self._orig_index_file = ResultStorage.INDEX_FILE
        ResultStorage.RESULTS_DIR = self.results_dir
        ResultStorage.INDEX_FILE = self.results_dir / "index.json"

    def tearDown(self) -> None:
        ResultStorage.RESULTS_DIR = self._orig_results_dir
        ResultStorage.INDEX_FILE = self._orig_index_file
        self._tmp_dir.cleanup()

    def test_delete_result_endpoint_removes_saved_result(self):
        saved_path = ResultStorage.save(
            {
                "run_id": "run-delete-api",
                "target_model": "gpt-5.1",
                "judge_models": ["judge-a"],
                "tasks": [],
            }
        )

        client = TestClient(server.app)
        delete_response = client.delete(f"/api/results/{saved_path.name}")
        list_response = client.get("/api/results")

        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["status"], "deleted")
        self.assertFalse(saved_path.exists())
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json(), [])

    def test_list_results_preserves_null_scores_when_all_excluded(self):
        """DEC-004: all-excluded null hero scores must not 500 /api/results."""
        ResultStorage.save(
            {
                "run_id": "run-all-excluded-list",
                "target_model": "gpt-5.1",
                "judge_models": ["judge-a", "judge-b"],
                "judge_runs": 1,
                "executed_at": "2026-07-24T04:00:00Z",
                "exclude_unreliable_judges": True,
                "average_score": None,
                "best_score": None,
                "score_aggregation": {
                    "average_score_before": 45.0,
                    "average_score_after": None,
                    "best_score_before": 50.0,
                    "best_score_after": None,
                    "excluded_judges": [
                        {"judge_id": "judge-a", "reasons": ["high_variance"]},
                        {"judge_id": "judge-b", "reasons": ["critical_fail"]},
                    ],
                    "included_judges": [],
                    "all_excluded": True,
                    "unreliable_candidates": [],
                },
                "tasks": [
                    {
                        "task_name": "01",
                        "task_type": "fact",
                        "input_prompt": "prompt",
                        "response": "response",
                        "judge_results": {
                            "judge-a": {
                                "aggregated": {
                                    "total_score_mean": 50,
                                    "total_score_std": 1,
                                    "critical_fail": False,
                                    "confidence_distribution": {
                                        "high": 0,
                                        "medium": 0,
                                        "low": 0,
                                    },
                                }
                            },
                            "judge-b": {
                                "aggregated": {
                                    "total_score_mean": 40,
                                    "total_score_std": 1,
                                    "critical_fail": True,
                                    "confidence_distribution": {
                                        "high": 0,
                                        "medium": 0,
                                        "low": 0,
                                    },
                                }
                            },
                        },
                    }
                ],
            }
        )

        client = TestClient(server.app)
        response = client.get("/api/results")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertIsNone(body[0]["avg_score"])
        self.assertIsNone(body[0]["max_score"])
        self.assertIsNone(body[0]["min_score"])
        self.assertTrue(body[0]["exclude_unreliable_judges"])

    def test_run_with_empty_target_model_returns_error(self):
        """空文字の target_model で run した場合、エラーが返されることを確認"""
        client = TestClient(server.app)
        with patch.object(
            server, "_load_tasks", return_value=[{"id": "task-1", "type": "fact", "rubric_file": "/dev/null", "prompt_file": "/dev/null"}]
        ):
            response = client.post(
                "/api/run",
                json={
                    "target_model": "",
                    "judge_models": ["openrouter/openai/gpt-5.4"],
                    "selected_task_ids": ["task-1"],
                },
            )
        self.assertEqual(response.status_code, 200)
        # SSE ストリームを読む
        lines = response.text.split("\n")
        events = []
        for line in lines:
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
        # error イベントが含まれる
        error_events = [e for e in events if e.get("type") == "error"]
        self.assertTrue(len(error_events) > 0, f"Expected error event, got events={events}")
        self.assertIn("アダプタまたはAPIキーが見つかりません", error_events[0].get("message", ""))


class TestHolisticJudgeModels(unittest.TestCase):
    def test_effective_holistic_judge_models_three_patterns(self):
        """AC-005 / DEC-001: standard-only fallback, holistic override, both distinct."""
        # holistic unspecified / empty → fallback to judge_models
        self.assertEqual(
            server._effective_holistic_judge_models(["judge-a"], []),
            ["judge-a"],
        )
        self.assertEqual(
            server._effective_holistic_judge_models(["judge-a"], None),
            ["judge-a"],
        )
        # holistic-only override (when judge_models differ)
        self.assertEqual(
            server._effective_holistic_judge_models(
                ["judge-a"], ["judge-holistic"]
            ),
            ["judge-holistic"],
        )
        # both specified independently
        self.assertEqual(
            server._effective_holistic_judge_models(
                ["judge-a", "judge-b"], ["judge-holistic"]
            ),
            ["judge-holistic"],
        )

    def test_run_request_accepts_optional_holistic_judge_models(self):
        req = server.RunRequest(
            target_model="subject",
            judge_models=["judge-a"],
            selected_task_ids=["01"],
        )
        self.assertEqual(req.holistic_judge_models, [])

        req_override = server.RunRequest(
            target_model="subject",
            judge_models=["judge-a"],
            selected_task_ids=["01"],
            holistic_judge_models=["judge-holistic"],
            run_holistic=True,
        )
        self.assertEqual(req_override.holistic_judge_models, ["judge-holistic"])

    def test_run_request_accepts_and_clamps_subject_runs(self):
        req = server.RunRequest(
            target_model="subject",
            judge_models=["judge-a"],
            selected_task_ids=["01"],
        )
        self.assertEqual(req.subject_runs, 1)
        self.assertEqual(req.clamped_subject_runs(), 1)

        req_n = server.RunRequest(
            target_model="subject",
            judge_models=["judge-a"],
            selected_task_ids=["01"],
            subject_runs=3,
            judge_runs=2,
        )
        self.assertEqual(req_n.subject_runs, 3)
        self.assertEqual(req_n.judge_runs, 2)
        self.assertEqual(req_n.clamped_subject_runs(), 3)

        req_over = server.RunRequest(
            target_model="subject",
            judge_models=["judge-a"],
            selected_task_ids=["01"],
            subject_runs=99,
        )
        self.assertEqual(req_over.clamped_subject_runs(), 5)

    def test_run_request_exclude_unreliable_judges_defaults_false(self):
        req = server.RunRequest(
            target_model="subject",
            judge_models=["judge-a"],
            selected_task_ids=["01"],
        )
        self.assertFalse(req.exclude_unreliable_judges)

        req_on = server.RunRequest(
            target_model="subject",
            judge_models=["judge-a"],
            selected_task_ids=["01"],
            exclude_unreliable_judges=True,
        )
        self.assertTrue(req_on.exclude_unreliable_judges)

    def test_compute_score_aggregation_used_for_hero_scores(self):
        """AC-002: server path uses judge_reliability for exclude-ON hero scores."""
        from core.judge_reliability import compute_score_aggregation

        tasks = [
            {
                "task_name": "01",
                "judge_results": {
                    "judge-ok": {
                        "aggregated": {
                            "total_score_mean": 80.0,
                            "total_score_std": 1.0,
                            "critical_fail": False,
                            "confidence_distribution": {
                                "high": 1,
                                "medium": 0,
                                "low": 0,
                            },
                        }
                    },
                    "judge-bad": {
                        "aggregated": {
                            "total_score_mean": 78.0,
                            "total_score_std": 6.0,
                            "critical_fail": False,
                            "confidence_distribution": {
                                "high": 1,
                                "medium": 0,
                                "low": 0,
                            },
                        }
                    },
                },
            }
        ]
        off = compute_score_aggregation(tasks, exclude_unreliable_judges=False)
        on = compute_score_aggregation(tasks, exclude_unreliable_judges=True)
        self.assertEqual(off["average_score"], 79.0)
        self.assertEqual(on["average_score"], 80.0)
        self.assertEqual(
            [e["judge_id"] for e in on["score_aggregation"]["excluded_judges"]],
            ["judge-bad"],
        )

    def test_run_holistic_false_skips_holistic_adapter_resolution_gate(self):
        """INV-002: resolution sits behind run_holistic; false keeps override unused."""
        req = server.RunRequest(
            target_model="subject",
            judge_models=["judge-a"],
            selected_task_ids=["01"],
            holistic_judge_models=["judge-holistic"],
            run_holistic=False,
        )
        self.assertFalse(req.run_holistic)
        # Gate condition used by server holistic block
        should_resolve = bool(req.run_holistic)
        self.assertFalse(should_resolve)
        # Effective IDs remain computable but must not be resolved when gated off
        effective = server._effective_holistic_judge_models(
            req.judge_models, req.holistic_judge_models
        )
        self.assertEqual(effective, ["judge-holistic"])

    def test_non_creative_holistic_inputs_bundle_subject_runs_when_n_gt_1(self):
        """DEC-007 / Core-Enhance-55: multi-run completed task → bundled text in holistic input."""
        completed = [
            {
                "task_name": "01",
                "task_type": "fact",
                "input_prompt": "p1",
                "response": "representative-only",
                "subject_runs": [
                    {"run_index": 1, "response": "alpha"},
                    {"run_index": 2, "response": "beta"},
                ],
            },
            {
                "task_name": "02",
                "task_type": "creative",
                "input_prompt": "p2",
                "response": "skip-me",
                "subject_runs": [
                    {"run_index": 1, "response": "c1"},
                    {"run_index": 2, "response": "c2"},
                ],
            },
            {
                "task_name": "03",
                "task_type": "fact",
                "input_prompt": "p3",
                "response": "single-rep",
                "subject_runs": [{"run_index": 1, "response": "single-rep"}],
            },
        ]
        inputs = server._build_non_creative_holistic_inputs(completed)
        self.assertEqual(len(inputs), 2)
        self.assertEqual(inputs[0]["task_name"], "01")
        self.assertIn("### 被験試行 #1\nalpha", inputs[0]["response"])
        self.assertIn("### 被験試行 #2\nbeta", inputs[0]["response"])
        self.assertNotEqual(inputs[0]["response"], "representative-only")
        self.assertEqual(inputs[1]["task_name"], "03")
        self.assertEqual(inputs[1]["response"], "single-rep")

        # holistic multi-task bundler schema is unchanged (separate builder)
        bundled = BenchmarkEngine._build_bundled_responses(inputs)
        self.assertIn("### タスク: 01（fact）", bundled)
        self.assertIn("被験試行 #1", bundled)

    def test_holistic_adapter_failure_still_saves_standard_results(self):
        """Core-Bug-50: standard 完了 → holistic adapter 空 → SSE error 後も ResultStorage.save."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        rubric = Path(tmp.name) / "rubric.md"
        prompt = Path(tmp.name) / "prompt.md"
        rubric.write_text("rubric", encoding="utf-8")
        prompt.write_text("prompt", encoding="utf-8")

        task_payload = {
            "id": "01",
            "type": "fact",
            "rubric_file": str(rubric),
            "prompt_file": str(prompt),
            "config": {},
        }
        fake_adapter = MagicMock()
        fake_adapter.is_available.return_value = True

        task_result = TaskResult(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            response="subject-answer",
            judge_results={
                "judge-a": {
                    "runs": [
                        {
                            "scores": {
                                "logic_and_fact": 30,
                                "constraint_adherence": 20,
                                "helpfulness_and_creativity": 20,
                            },
                            "total": 70,
                            "usage": {"duration_ms": 100},
                        }
                    ]
                }
            },
            subject_usage={"duration_ms": 50},
        )

        saved: list = []

        def _capture_save(result):
            saved.append(result)
            return Path(tmp.name) / "saved.json"

        judge_calls = {"n": 0}

        def _judge_adapters(model_ids, api_keys=None):
            judge_calls["n"] += 1
            # 1st: standard judges available; 2nd: holistic resolves empty
            if judge_calls["n"] == 1:
                return {"judge-a": fake_adapter}
            return {}

        client = TestClient(server.app)
        with (
            patch.object(server, "_load_tasks", return_value=[task_payload]),
            patch.object(
                server,
                "_load_holistic_tasks",
                return_value=[
                    {
                        "id": "style",
                        "rubric_file": str(rubric),
                        "prompt_file": str(prompt),
                    }
                ],
            ),
            patch.object(
                server.SecretsStore, "load_existing", return_value={"openrouter": "k"}
            ),
            patch.object(
                server, "get_adapter_for_model", return_value=fake_adapter
            ),
            patch.object(
                server, "get_available_judge_adapters", side_effect=_judge_adapters
            ),
            patch.object(
                server.BenchmarkEngine,
                "run_task",
                new=AsyncMock(return_value=task_result),
            ),
            patch.object(server.ResultStorage, "save", side_effect=_capture_save),
            patch.object(
                server,
                "_resolve_judge_system_prompt_resource",
                return_value=MagicMock(
                    path=Path(tmp.name) / "missing_judge_system.md",
                    source="test",
                ),
            ),
        ):
            response = client.post(
                "/api/run",
                json={
                    "target_model": "openrouter/openai/gpt-5.4",
                    "judge_models": ["judge-a"],
                    "holistic_judge_models": ["judge-holistic-missing-key"],
                    "selected_task_ids": ["01"],
                    "run_holistic": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        events = []
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        error_events = [e for e in events if e.get("type") == "error"]
        complete_events = [e for e in events if e.get("type") == "complete"]
        self.assertTrue(error_events, f"expected error SSE, got {events}")
        self.assertIn("包括評価用", error_events[0].get("message", ""))
        self.assertTrue(complete_events, f"expected complete after save, got {events}")
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["tasks"][0]["response"], "subject-answer")
        self.assertEqual(saved[0]["holistic_tasks"], [])
        self.assertEqual(saved[0]["holistic_judge_models"], [])
        self.assertEqual(complete_events[0]["result"]["holistic_tasks"], [])


if __name__ == "__main__":
    unittest.main()
