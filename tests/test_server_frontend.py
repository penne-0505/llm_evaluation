"""配布向け frontend 配信のテスト"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import server
from core.app_paths import AppPaths


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

        for path in [
            self.bundled_prompts,
            self.bundled_rubrics,
            self.user_prompts,
            self.user_rubrics,
            self.env_prompts,
            self.env_rubrics,
        ]:
            path.mkdir(parents=True, exist_ok=True)

        (self.bundled_prompts / "01.md").write_text("bundled prompt 01", encoding="utf-8")
        (self.bundled_rubrics / "01.md").write_text("task_type: fact", encoding="utf-8")
        (self.bundled_prompts / "03.md").write_text("bundled prompt 03", encoding="utf-8")
        (self.bundled_rubrics / "03.md").write_text("task_type: creative", encoding="utf-8")

        (self.user_prompts / "01.md").write_text("user prompt 01", encoding="utf-8")
        (self.user_rubrics / "02.md").write_text("task_type: speculative", encoding="utf-8")
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
            patch.object(AppPaths, "bundled_prompts_dir", return_value=self.bundled_prompts),
            patch.object(AppPaths, "bundled_rubrics_dir", return_value=self.bundled_rubrics),
            patch.object(
                AppPaths,
                "bundled_judge_system_prompt_file",
                return_value=self.bundled_judge,
            ),
            patch.object(AppPaths, "prompts_override_dir", return_value=self.user_prompts),
            patch.object(AppPaths, "rubrics_override_dir", return_value=self.user_rubrics),
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

        self.assertEqual(tasks["01"]["prompt"], "env prompt 01")
        self.assertEqual(tasks["01"]["prompt_source"], "env_override")
        self.assertEqual(tasks["01"]["rubric_source"], "env_override")

        self.assertEqual(tasks["02"]["prompt"], "user prompt 02")
        self.assertEqual(tasks["02"]["prompt_source"], "user_override")
        self.assertEqual(tasks["02"]["rubric_source"], "user_override")

        self.assertEqual(tasks["03"]["prompt"], "bundled prompt 03")
        self.assertEqual(tasks["03"]["prompt_source"], "bundled")
        self.assertEqual(tasks["03"]["rubric_source"], "bundled")

        self.assertEqual(resources.status_code, 200)
        resources_body = resources.json()
        self.assertEqual(
            resources_body["judge_system_prompt"]["resolved_source"], "env_override"
        )
        self.assertTrue(resources_body["judge_system_prompt"]["exists"])


if __name__ == "__main__":
    unittest.main()
