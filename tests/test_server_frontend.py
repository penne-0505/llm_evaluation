"""配布向け frontend 配信のテスト"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import server
from core.app_paths import AppPaths
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
            '{"subject_tools": {"enabled_tools": ["web-search"], "fixture_path": "task_fixtures/03.json"}}',
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
        self.assertEqual(body["id"], "official-v1")
        self.assertEqual(body["judge_runs"], 3)
        self.assertEqual(body["subject_temperature"], 0.6)
        self.assertEqual(body["task_ids"], [f"{i:02d}" for i in range(1, 12)])
        self.assertEqual(
            [judge["id"] for judge in body["judge_models"]],
            [
                "openrouter/anthropic/claude-sonnet-4.6",
                "openrouter/openai/gpt-5.4",
                "openrouter/google/gemini-3.1-pro-preview",
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


if __name__ == "__main__":
    unittest.main()
