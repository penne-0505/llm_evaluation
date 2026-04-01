"""Grounding corpus のローカル保存管理"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from core.app_paths import AppPaths


class GroundingCorpusStore:
    RECORDS_DIR: Path | None = None
    INDEX_FILE: Path | None = None

    @classmethod
    def records_dir(cls) -> Path:
        return cls.RECORDS_DIR or AppPaths.grounding_corpus_dir()

    @classmethod
    def index_file(cls) -> Path:
        return cls.INDEX_FILE or (cls.records_dir() / "index.json")

    @classmethod
    def resolve_record_path(cls, record_id: str) -> Path:
        safe_name = Path(record_id).name
        if not safe_name.endswith(".json"):
            safe_name = f"{safe_name}.json"
        return cls.records_dir() / safe_name

    @classmethod
    def save(cls, record: Dict[str, Any]) -> Path:
        records_dir = cls.records_dir()
        records_dir.mkdir(parents=True, exist_ok=True)

        record_id = record.get("id") or cls._generate_record_id(record.get("query", "record"))
        filename = f"{record_id}.json"
        filepath = records_dir / filename

        payload = {
            "id": record_id,
            "query": record.get("query", ""),
            "captured_at": record.get("captured_at")
            or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "search_results": record.get("search_results"),
            "documents": record.get("documents", []),
            "notes": record.get("notes", ""),
        }

        with filepath.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        cls._upsert_index(payload, filepath)
        return filepath

    @classmethod
    def load(cls, filepath: Path) -> Dict[str, Any]:
        with filepath.open("r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def list_records(cls) -> List[Dict[str, Any]]:
        index = cls._load_index()
        if index:
            return index

        records: List[Dict[str, Any]] = []
        for filepath in sorted(cls.records_dir().glob("*.json"), reverse=True):
            if filepath.name == "index.json":
                continue
            try:
                records.append(cls._build_summary(cls.load(filepath), filepath))
            except Exception:
                continue
        if records:
            cls._save_index(records)
        return records

    @classmethod
    def _build_summary(cls, record: Dict[str, Any], filepath: Path) -> Dict[str, Any]:
        documents = record.get("documents", [])
        search_results = record.get("search_results")
        result_count = 0
        if isinstance(search_results, list):
            result_count = len(search_results)
        elif isinstance(search_results, dict):
            result_count = len(search_results.get("results", [])) if isinstance(search_results.get("results"), list) else 0

        return {
            "id": record.get("id", filepath.stem),
            "filename": filepath.name,
            "filepath": str(filepath),
            "query": record.get("query", ""),
            "captured_at": record.get("captured_at")
            or datetime.fromtimestamp(filepath.stat().st_mtime).isoformat(),
            "document_count": len(documents) if isinstance(documents, list) else 0,
            "search_result_count": result_count,
        }

    @classmethod
    def _load_index(cls) -> List[Dict[str, Any]]:
        path = cls.index_file()
        if not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            return []
        return []

    @classmethod
    def _save_index(cls, items: List[Dict[str, Any]]) -> None:
        records_dir = cls.records_dir()
        records_dir.mkdir(parents=True, exist_ok=True)
        with cls.index_file().open("w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

    @classmethod
    def _upsert_index(cls, record: Dict[str, Any], filepath: Path) -> None:
        summary = cls._build_summary(record, filepath)
        items = [
            item
            for item in cls._load_index()
            if item.get("id") != summary["id"] and item.get("filename") != filepath.name
        ]
        items.append(summary)
        items.sort(key=lambda item: item.get("captured_at", ""), reverse=True)
        cls._save_index(items)

    @staticmethod
    def _generate_record_id(query: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^\w\-]+", "_", query.strip().lower()).strip("_") or "record"
        return f"{timestamp}_{slug[:48]}"
