"""Persist last selection state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from core.app_paths import AppPaths


class SelectionStore:
    """Save and load last used selection values."""

    FILE_PATH: Path | None = None

    @classmethod
    def _file_path(cls) -> Path:
        return cls.FILE_PATH or AppPaths.selection_file()

    @classmethod
    def _legacy_file_path(cls) -> Path:
        return AppPaths.repo_path("models", "last_selection.json")

    @classmethod
    def load(cls) -> Dict[str, Any]:
        for path in (cls._file_path(), cls._legacy_file_path()):
            if not path.exists():
                continue
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
        return {}

    @classmethod
    def save(cls, selection: Dict[str, Any]) -> None:
        data = dict(selection)
        data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        file_path = cls._file_path()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
