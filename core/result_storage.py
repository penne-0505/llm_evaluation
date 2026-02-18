"""実行結果の保存・読み込み管理"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class ResultStorage:
    """
    実行結果の保存・読み込みを管理
    """

    RESULTS_DIR = Path("results")
    INDEX_FILE = RESULTS_DIR / "index.json"

    @classmethod
    def save(cls, benchmark_result: Dict[str, Any]) -> Path:
        """
        実行結果をJSONとして保存

        Args:
            benchmark_result: ベンチマーク結果の辞書

        Returns:
            保存されたファイルパス

        ファイル名: YYYYMMDD_HHMMSS_<model_name>.json
        """
        cls.RESULTS_DIR.mkdir(exist_ok=True)

        # ファイル名生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_model = benchmark_result.get("target_model", "unknown")
        safe_model_name = re.sub(r"[^\w\-]", "_", target_model)
        filename = f"{timestamp}_{safe_model_name}.json"

        filepath = cls.RESULTS_DIR / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(benchmark_result, f, ensure_ascii=False, indent=2)

        cls._upsert_index(benchmark_result, filepath)

        return filepath

    @classmethod
    def load(cls, filepath: Path) -> Dict[str, Any]:
        """
        保存済み結果を読み込み

        Args:
            filepath: JSONファイルパス

        Returns:
            ベンチマーク結果の辞書
        """
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def list_results(cls) -> List[Path]:
        """
        保存済み結果ファイルの一覧を取得

        Returns:
            新しい順にソートされたファイルパスのリスト
        """
        if not cls.RESULTS_DIR.exists():
            return []
        return sorted(cls.RESULTS_DIR.glob("*.json"), reverse=True)

    @classmethod
    def list_summaries(cls) -> List[Dict[str, Any]]:
        """
        保存済み結果のサマリー一覧を取得

        Returns:
            サマリーのリスト（新しい順）
        """
        index = cls._load_index()
        if index:
            return index

        summaries: List[Dict[str, Any]] = []
        for filepath in cls.list_results():
            try:
                data = cls.load(filepath)
            except Exception:
                continue
            summaries.append(cls._build_summary(data, filepath))

        if summaries:
            summaries.sort(key=lambda x: x.get("executed_at", ""), reverse=True)
            cls._save_index(summaries)

        return summaries

    @classmethod
    def delete(cls, filepath: Path) -> bool:
        """
        結果ファイルを削除

        Args:
            filepath: 削除するファイルパス

        Returns:
            削除成功時True
        """
        try:
            if filepath.exists():
                filepath.unlink()
                cls._remove_from_index(filepath)
                return True
            return False
        except Exception:
            return False

    @classmethod
    def _build_summary(
        cls, benchmark_result: Dict[str, Any], filepath: Path
    ) -> Dict[str, Any]:
        tasks = benchmark_result.get("tasks", [])
        total_scores = []
        for task in tasks:
            judge_results = task.get("judge_results", {})
            for result in judge_results.values():
                agg = result.get("aggregated")
                if agg:
                    total_scores.append(agg.get("total_score_mean", 0))

        avg_score = sum(total_scores) / len(total_scores) if total_scores else 0
        max_score = max(total_scores) if total_scores else 0
        min_score = min(total_scores) if total_scores else 0

        executed_at = benchmark_result.get("executed_at")
        if not executed_at:
            executed_at = datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()

        return {
            "filename": filepath.name,
            "filepath": str(filepath),
            "target_model": benchmark_result.get("target_model", "unknown"),
            "executed_at": executed_at,
            "task_count": len(tasks),
            "judge_count": len(benchmark_result.get("judge_models", [])),
            "avg_score": avg_score,
            "max_score": max_score,
            "min_score": min_score,
        }

    @classmethod
    def _load_index(cls) -> List[Dict[str, Any]]:
        if not cls.INDEX_FILE.exists():
            return []
        try:
            with open(cls.INDEX_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            return []
        return []

    @classmethod
    def _save_index(cls, index: List[Dict[str, Any]]) -> None:
        cls.RESULTS_DIR.mkdir(exist_ok=True)
        with open(cls.INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    @classmethod
    def _upsert_index(cls, benchmark_result: Dict[str, Any], filepath: Path) -> None:
        summary = cls._build_summary(benchmark_result, filepath)
        index = cls._load_index()
        index = [
            item
            for item in index
            if item.get("filepath") != str(filepath)
            and item.get("filename") != filepath.name
        ]
        index.append(summary)
        index.sort(key=lambda x: x.get("executed_at", ""), reverse=True)
        cls._save_index(index)

    @classmethod
    def _remove_from_index(cls, filepath: Path) -> None:
        index = cls._load_index()
        if not index:
            return
        index = [
            item
            for item in index
            if item.get("filepath") != str(filepath)
            and item.get("filename") != filepath.name
        ]
        cls._save_index(index)

    @classmethod
    def get_result_info(cls, filepath: Path) -> Dict[str, Any]:
        """
        結果ファイルのメタ情報を取得（読み込み軽量化用）

        Args:
            filepath: JSONファイルパス

        Returns:
            メタ情報の辞書
        """
        try:
            data = cls.load(filepath)
            return {
                "filename": filepath.name,
                "filepath": str(filepath),
                "target_model": data.get("target_model", "unknown"),
                "executed_at": data.get("executed_at", "unknown"),
                "task_count": len(data.get("tasks", [])),
                "judge_models": data.get("judge_models", {}),
            }
        except Exception as e:
            return {
                "filename": filepath.name,
                "filepath": str(filepath),
                "error": str(e),
            }
