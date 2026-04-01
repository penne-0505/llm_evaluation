"""アプリ共通のログ保存設定"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.app_paths import AppPaths

_FILE_HANDLER_NAME = "prism_app_file_handler"


def _candidate_log_files() -> list[Path]:
    return [
        AppPaths.log_file(),
        AppPaths.repo_path(".logs", "app.log"),
    ]


def configure_logging(level: int = logging.INFO) -> Path | None:
    """回転付きファイルログを root logger に設定する。"""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers:
        if getattr(handler, "name", "") == _FILE_HANDLER_NAME:
            filename = getattr(handler, "baseFilename", None)
            return Path(filename) if filename else None

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    for log_file in _candidate_log_files():
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                log_file,
                maxBytes=1_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            handler.setLevel(level)
            handler.setFormatter(formatter)
            handler.set_name(_FILE_HANDLER_NAME)
            root_logger.addHandler(handler)
            return log_file
        except OSError:
            continue

    return None
