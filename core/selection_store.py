"""Persist last selection state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class SelectionStore:
    """Save and load last used selection values."""

    FILE_PATH = Path("models/last_selection.json")

    @classmethod
    def load(cls) -> Dict[str, Any]:
        if not cls.FILE_PATH.exists():
            return {}
        try:
            return json.loads(cls.FILE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @classmethod
    def save(cls, selection: Dict[str, Any]) -> None:
        data = dict(selection)
        data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cls.FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cls.FILE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
