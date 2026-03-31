"""launcher の portable 向け挙動テスト"""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import launcher


class _FakeThread:
    def __init__(self, target=None, daemon=None):
        self.target = target
        self.daemon = daemon
        self.started = False
        self.join_calls = 0

    def start(self):
        self.started = True

    def join(self, timeout=None):
        self.join_calls += 1

    def is_alive(self):
        return self.join_calls == 0


class _FakeUvicornServer:
    def __init__(self, config):
        self.config = config
        self.should_exit = False

    def run(self):
        return None


class TestLauncher(unittest.TestCase):
    def test_preflight_issue_aborts_startup(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch.object(
                launcher.server,
                "get_runtime_diagnostics",
                return_value={"issues": ["frontend missing"]},
            ),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            exit_code = launcher.main(["--no-browser"])

        self.assertEqual(exit_code, 1)
        self.assertIn("起動前チェックで問題が見つかりました", stderr.getvalue())
        self.assertIn("frontend missing", stderr.getvalue())

    def test_port_fallback_and_browser_failure_are_reported(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch.object(
                launcher.server,
                "get_runtime_diagnostics",
                return_value={"issues": []},
            ),
            patch.object(launcher, "_pick_port", return_value=(8765, True)),
            patch.object(launcher, "_wait_until_ready", return_value=True),
            patch.object(launcher.uvicorn, "Config", return_value=object()),
            patch.object(launcher.uvicorn, "Server", side_effect=_FakeUvicornServer),
            patch.object(launcher.threading, "Thread", side_effect=_FakeThread),
            patch.object(launcher.webbrowser, "open", return_value=False),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            exit_code = launcher.main(["--port", "8000"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Prism LLM Eval is running at http://127.0.0.1:8765/", stdout.getvalue())
        self.assertIn("ポート 8000 は使用中だったため", stderr.getvalue())
        self.assertIn("ブラウザを自動で開けませんでした", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
