"""実行結果の保存・読み込み管理"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.app_paths import AppPaths
from core.cost_estimator import summarize_usage_records


class ResultStorage:
    """
    実行結果の保存・読み込みを管理
    """

    RESULTS_DIR: Path | None = None
    INDEX_FILE: Path | None = None

    @classmethod
    def results_dir(cls) -> Path:
        return cls.RESULTS_DIR or AppPaths.results_dir()

    @classmethod
    def index_file(cls) -> Path:
        return cls.INDEX_FILE or (cls.results_dir() / "index.json")

    @classmethod
    def legacy_results_dir(cls) -> Path:
        return AppPaths.repo_path("results")

    @classmethod
    def _result_dirs(cls) -> List[Path]:
        current = cls.results_dir()
        legacy = cls.legacy_results_dir()
        if legacy == current:
            return [current]
        return [current, legacy]

    @classmethod
    def _has_legacy_result_files(cls) -> bool:
        legacy = cls.legacy_results_dir()
        if legacy == cls.results_dir() or not legacy.exists():
            return False
        return any(path.name != "index.json" for path in legacy.glob("*.json"))

    @classmethod
    def resolve_result_path(cls, filename: str) -> Path:
        safe_name = Path(filename).name
        for directory in cls._result_dirs():
            candidate = directory / safe_name
            if candidate.exists():
                return candidate
        return cls.results_dir() / safe_name

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
        results_dir = cls.results_dir()
        results_dir.mkdir(parents=True, exist_ok=True)

        # ファイル名生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_model = benchmark_result.get("target_model", "unknown")
        safe_model_name = re.sub(r"[^\w\-]", "_", target_model)
        filename = f"{timestamp}_{safe_model_name}.json"

        filepath = results_dir / filename

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
        results: List[Path] = []
        seen: set[Path] = set()
        for directory in cls._result_dirs():
            if not directory.exists():
                continue
            for filepath in directory.glob("*.json"):
                if filepath.name == "index.json":
                    continue
                resolved = filepath.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                results.append(filepath)
        return sorted(results, reverse=True)

    @classmethod
    def list_summaries(cls) -> List[Dict[str, Any]]:
        """
        保存済み結果のサマリー一覧を取得

        Returns:
            サマリーのリスト（新しい順）
        """
        use_index_cache = not cls._has_legacy_result_files()
        index = cls._load_index() if use_index_cache else []
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
            if use_index_cache:
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
        subject_usage_records = [
            task.get("subject_usage")
            for task in tasks
            if isinstance(task.get("subject_usage"), dict)
        ]
        subject_usage_summary = summarize_usage_records(subject_usage_records)
        subject_total_tokens = subject_usage_summary["totals"].get("total_tokens", 0)
        subject_estimated_cost_usd = subject_usage_summary["totals"].get(
            "estimated_cost_usd"
        )
        subject_cost_per_1m_tokens_usd = None
        if subject_total_tokens and subject_estimated_cost_usd is not None:
            subject_cost_per_1m_tokens_usd = round(
                (float(subject_estimated_cost_usd) / subject_total_tokens) * 1_000_000,
                6,
            )

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
            "run_id": benchmark_result.get("run_id", filepath.stem),
            "target_model": benchmark_result.get("target_model", "unknown"),
            "executed_at": executed_at,
            "execution_duration_ms": benchmark_result.get("execution_duration_ms"),
            "estimated_cost_usd": benchmark_result.get("estimated_cost_usd"),
            "cost_estimate_status": benchmark_result.get("cost_estimate_status"),
            "subject_total_tokens": subject_total_tokens,
            "subject_estimated_cost_usd": subject_estimated_cost_usd,
            "subject_cost_per_1m_tokens_usd": subject_cost_per_1m_tokens_usd,
            "strict_mode_requested": benchmark_result.get("strict_mode", {}).get(
                "requested", False
            ),
            "strict_mode_enforced": benchmark_result.get("strict_mode", {}).get(
                "enforced", False
            ),
            "strict_mode_eligible": benchmark_result.get("strict_mode", {}).get(
                "eligible", False
            ),
            "strict_mode_preset_id": benchmark_result.get("strict_mode", {}).get(
                "preset_id"
            ),
            "strict_mode_preset_label": benchmark_result.get("strict_mode", {}).get(
                "preset_label"
            ),
            "strict_mode_profile_id": benchmark_result.get("strict_mode", {}).get(
                "profile_id"
            ),
            "strict_mode_profile_label": benchmark_result.get("strict_mode", {}).get(
                "profile_label"
            ),
            "task_count": len(tasks),
            "judge_count": len(benchmark_result.get("judge_models", [])),
            "avg_score": avg_score,
            "max_score": max_score,
            "min_score": min_score,
        }

    @classmethod
    def _load_index(cls) -> List[Dict[str, Any]]:
        index_file = cls.index_file()
        if not index_file.exists():
            return []
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            return []
        return []

    @classmethod
    def _save_index(cls, index: List[Dict[str, Any]]) -> None:
        results_dir = cls.results_dir()
        results_dir.mkdir(parents=True, exist_ok=True)
        with open(cls.index_file(), "w", encoding="utf-8") as f:
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
