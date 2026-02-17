import os
import sys
from pathlib import Path


def _set_resource_env() -> None:
    if hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS)
        os.environ.setdefault("LLM_BENCHMARK_RUBRICS_DIR", str(base_dir / "rubrics"))
        os.environ.setdefault("LLM_BENCHMARK_PROMPTS_DIR", str(base_dir / "prompts"))
        os.environ.setdefault(
            "LLM_BENCHMARK_JUDGE_SYSTEM_PROMPT_PATH",
            str(base_dir / "judge_system_prompt.md"),
        )


def _resolve_app_path() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "app.py"
    return Path(__file__).resolve().parents[1] / "app.py"


def main() -> None:
    _set_resource_env()
    app_path = _resolve_app_path()
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(app_path)]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
