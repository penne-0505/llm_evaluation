"""配布向けの実行/保存パス解決ヘルパー"""

from __future__ import annotations

import sys
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir


class AppPaths:
    """開発環境と packaged 実行で共通利用するパス定義。"""

    APP_NAME = "prism-llm-eval"
    APP_AUTHOR = "Prism"

    @classmethod
    def repo_root(cls) -> Path:
        return Path(__file__).resolve().parent.parent

    @classmethod
    def runtime_root(cls) -> Path:
        bundled_root = getattr(sys, "_MEIPASS", None)
        if bundled_root:
            return Path(bundled_root)
        return cls.repo_root()

    @classmethod
    def bundled_path(cls, *parts: str) -> Path:
        return cls.runtime_root().joinpath(*parts)

    @classmethod
    def repo_path(cls, *parts: str) -> Path:
        return cls.repo_root().joinpath(*parts)

    @classmethod
    def data_dir(cls) -> Path:
        path = Path(user_data_dir(cls.APP_NAME, cls.APP_AUTHOR))
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def config_dir(cls) -> Path:
        path = Path(user_config_dir(cls.APP_NAME, cls.APP_AUTHOR))
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def results_dir(cls) -> Path:
        return cls.data_dir() / "results"

    @classmethod
    def logs_dir(cls) -> Path:
        return cls.data_dir() / "logs"

    @classmethod
    def log_file(cls) -> Path:
        return cls.logs_dir() / "app.log"

    @classmethod
    def models_dir(cls) -> Path:
        return cls.data_dir() / "models"

    @classmethod
    def grounding_corpus_dir(cls) -> Path:
        return cls.data_dir() / "grounding_corpus"

    @classmethod
    def selection_file(cls) -> Path:
        return cls.models_dir() / "last_selection.json"

    @classmethod
    def model_cache_file(cls) -> Path:
        return cls.models_dir() / "models.json"

    @classmethod
    def secrets_file(cls) -> Path:
        return cls.config_dir() / "secrets.toml"

    @classmethod
    def overrides_dir(cls) -> Path:
        return cls.data_dir() / "overrides"

    @classmethod
    def prompts_override_dir(cls) -> Path:
        return cls.overrides_dir() / "prompts"

    @classmethod
    def rubrics_override_dir(cls) -> Path:
        return cls.overrides_dir() / "rubrics"

    @classmethod
    def judge_system_prompt_override_file(cls) -> Path:
        return cls.overrides_dir() / "judge_system_prompt.md"

    @classmethod
    def bundled_prompts_dir(cls) -> Path:
        return cls.bundled_path("prompts")

    @classmethod
    def bundled_rubrics_dir(cls) -> Path:
        return cls.bundled_path("rubrics")

    @classmethod
    def bundled_judge_system_prompt_file(cls) -> Path:
        return cls.bundled_path("judge_system_prompt.md")

    @classmethod
    def bundled_task_configs_dir(cls) -> Path:
        return cls.bundled_path("task_configs")

    @classmethod
    def bundled_task_fixtures_dir(cls) -> Path:
        return cls.bundled_path("task_fixtures")

    @classmethod
    def frontend_dist_dir(cls) -> Path:
        return cls.bundled_path("frontend", "dist")
