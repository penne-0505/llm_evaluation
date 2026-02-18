import os
import sys
from pathlib import Path


def _set_resource_env() -> None:
    frozen_path = getattr(sys, "_MEIPASS", None)
    if frozen_path:
        base_dir = Path(frozen_path)
        os.environ.setdefault("LLM_BENCHMARK_RUBRICS_DIR", str(base_dir / "rubrics"))
        os.environ.setdefault("LLM_BENCHMARK_PROMPTS_DIR", str(base_dir / "prompts"))
        os.environ.setdefault(
            "LLM_BENCHMARK_JUDGE_SYSTEM_PROMPT_PATH",
            str(base_dir / "judge_system_prompt.md"),
        )


def _resolve_app_path() -> Path:
    frozen_path = getattr(sys, "_MEIPASS", None)
    if frozen_path:
        return Path(frozen_path) / "app.py"
    return Path(__file__).resolve().parents[1] / "app.py"


def main() -> None:
    _set_resource_env()
    app_path = _resolve_app_path()
    from streamlit.web import cli as stcli

    extra_args = sys.argv[1:]
    if not any(arg.startswith("--server.port") for arg in extra_args):
        extra_args.append("--server.port=8501")
    if not any(arg.startswith("--server.address") for arg in extra_args):
        extra_args.append("--server.address=127.0.0.1")
    if not any(arg.startswith("--browser.serverPort") for arg in extra_args):
        extra_args.append("--browser.serverPort=8501")
    if not any(arg.startswith("--browser.serverAddress") for arg in extra_args):
        extra_args.append("--browser.serverAddress=127.0.0.1")

    sys.argv = ["streamlit", "run", str(app_path), *extra_args]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
