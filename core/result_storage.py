"""実行結果の保存・読み込み管理"""

import json
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.app_paths import AppPaths
from core.cost_estimator import summarize_task_timing, summarize_usage_records
from core.judge_reliability import collect_total_scores, collect_unreliable_judges


class ResultStorage:
    """
    実行結果の保存・読み込みを管理
    """

    RESULTS_DIR: Path | None = None
    INDEX_FILE: Path | None = None

    # intent: DEC-001 (Core/result-index-integrity) — index の read-modify-write を直列化する。
    # 更新経路は event loop thread（async な POST /api/run が save を直接呼ぶ）と
    # threadpool thread（同期 def の GET / DELETE /api/results）に跨るため、
    # asyncio.Lock ではなく threading 側で排他する。
    # RLock なのは、ロック保持中に別の index 操作を呼ぶ経路を許すため。
    _index_lock = threading.RLock()

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

    # 古い index cache に欠けうるフィールド群。
    # intent: DEC-003 (Core/result-index-integrity) — 補完は storage の責務。
    # API 層で個別に埋めると、フィールド追加のたびに複数箇所を触ることになる。
    _BACKFILL_FIELDS: tuple[str, ...] = (
        "run_id",
        "max_score",
        "min_score",
        "estimated_cost_usd",
        "cost_estimate_status",
        "subject_total_tokens",
        "subject_estimated_cost_usd",
        "subject_cost_per_1m_tokens_usd",
        "strict_mode_requested",
        "strict_mode_enforced",
        "strict_mode_eligible",
        "strict_mode_preset_id",
        "strict_mode_preset_label",
        "strict_mode_profile_id",
        "strict_mode_profile_label",
    )

    @classmethod
    def _needs_backfill(cls, summary: Dict[str, Any]) -> bool:
        return any(field not in summary for field in cls._BACKFILL_FIELDS)

    @classmethod
    def _backfill_summary(cls, summary: Dict[str, Any]) -> bool:
        """欠落フィールドを結果ファイルから補完する。補完したら True を返す。

        結果ファイルを読めない場合も、欠落キーは既定値で必ず埋める。
        呼び出し側がキーの存在を前提にできるようにするため、部分的な補完で終えない。
        """
        if not cls._needs_backfill(summary):
            return False

        filename = summary.get("filename", "")
        rebuilt: Optional[Dict[str, Any]] = None
        fallback_run_id = Path(filename).stem if filename else ""
        if filename:
            try:
                filepath = cls.resolve_result_path(filename)
                if filepath.exists():
                    rebuilt = cls._build_summary(cls.load(filepath), filepath)
                    fallback_run_id = filepath.stem
            except Exception:
                rebuilt = None

        for field in cls._BACKFILL_FIELDS:
            if field in summary:
                continue
            if rebuilt is not None and field in rebuilt:
                summary[field] = rebuilt[field]
            elif field == "run_id":
                summary[field] = fallback_run_id
            elif field in ("max_score", "min_score"):
                summary[field] = 0
            elif field == "cost_estimate_status":
                summary[field] = "unavailable"
            elif field == "subject_total_tokens":
                summary[field] = 0
            elif field.startswith("strict_mode_") and field in (
                "strict_mode_requested",
                "strict_mode_enforced",
                "strict_mode_eligible",
            ):
                summary[field] = False
            else:
                summary[field] = None
        return True

    @classmethod
    def list_summaries(cls) -> List[Dict[str, Any]]:
        """
        保存済み結果のサマリー一覧を取得

        欠落フィールドは補完済みで返す。補完が発生した場合は index を再保存する。

        Returns:
            サマリーのリスト（新しい順）
        """
        use_index_cache = not cls._has_legacy_result_files()
        # intent: DEC-001 (Core/result-index-integrity) — 再構築・再保存も index を書く経路なので、
        # 読み出しから書き戻しまでを他の更新と交錯させない。
        with cls._index_lock:
            index = cls._load_index() if use_index_cache else []
            if index:
                backfilled = False
                for summary in index:
                    if cls._backfill_summary(summary):
                        backfilled = True
                if backfilled and use_index_cache:
                    try:
                        cls._save_index(index)
                    except Exception:
                        # 再保存は次回への最適化にすぎない。失敗しても補完済みの値は返す。
                        pass
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
    def _summary_min_score(
        cls,
        tasks: List[Dict[str, Any]],
        *,
        total_scores: List[float],
        exclude_unreliable: bool,
        score_aggregation: Any,
    ) -> Optional[float]:
        """Derive list-summary min from the same score set as hero avg/max.

        When exclude-ON, prefer ``score_aggregation.excluded_judges`` (or
        recompute unreliable set) and return null if no included scores remain.
        """
        if not exclude_unreliable:
            return min(total_scores) if total_scores else 0

        excluded_ids: List[str] = []
        if isinstance(score_aggregation, dict):
            for entry in score_aggregation.get("excluded_judges") or []:
                if isinstance(entry, dict) and entry.get("judge_id"):
                    excluded_ids.append(str(entry["judge_id"]))
            if score_aggregation.get("all_excluded"):
                return None
        else:
            excluded_ids = list(collect_unreliable_judges(tasks).keys())

        hero_scores = collect_total_scores(tasks, excluded_judges=excluded_ids)
        if not hero_scores:
            return None
        return min(hero_scores)

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

        # Prefer saved hero scores (may be null when exclude-ON + all excluded).
        # Legacy JSON without average_score falls back to all-judge recompute.
        total_scores: List[float] = []
        for task in tasks:
            judge_results = task.get("judge_results", {})
            for result in judge_results.values():
                agg = result.get("aggregated")
                if agg and agg.get("total_score_mean") is not None:
                    total_scores.append(float(agg.get("total_score_mean", 0)))

        if "average_score" in benchmark_result:
            avg_score = benchmark_result.get("average_score")
        else:
            avg_score = (
                sum(total_scores) / len(total_scores) if total_scores else 0
            )

        if "best_score" in benchmark_result:
            max_score = benchmark_result.get("best_score")
        else:
            max_score = max(total_scores) if total_scores else 0

        # intent: DEC-004 (Core/exclude-unreliable-judges) — min uses the same
        # exclude-aware score set as hero avg/max; all-excluded → null not 0.
        min_score = cls._summary_min_score(
            tasks,
            total_scores=total_scores,
            exclude_unreliable=bool(
                benchmark_result.get("exclude_unreliable_judges", False)
            ),
            score_aggregation=benchmark_result.get("score_aggregation"),
        )

        executed_at = benchmark_result.get("executed_at")
        if not executed_at:
            executed_at = datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()

        # intent: DEC-002 (Core/time-roi-task-timing) — summary index にも同一合算を載せる
        timing_summary = benchmark_result.get("timing_summary")
        if not isinstance(timing_summary, dict):
            timing_summary = summarize_task_timing(tasks)

        return {
            "filename": filepath.name,
            "filepath": str(filepath),
            "run_id": benchmark_result.get("run_id", filepath.stem),
            "target_model": benchmark_result.get("target_model", "unknown"),
            "executed_at": executed_at,
            "execution_duration_ms": benchmark_result.get("execution_duration_ms"),
            "timing_summary": timing_summary,
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
            # intent: DEC-003 — list/history でも run 時 toggle を再現
            "exclude_unreliable_judges": bool(
                benchmark_result.get("exclude_unreliable_judges", False)
            ),
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
        # intent: DEC-002 (Core/result-index-integrity) — 一時ファイルへ書いてから
        # os.replace で差し替える。open(path, "w") は truncate してから書くため、
        # 書き込み途中の状態が他スレッドやプロセス異常終了へ晒される。
        # intent-invariant: INV-001 — index.json は常に完全な JSON 配列として読める。
        results_dir = cls.results_dir()
        results_dir.mkdir(parents=True, exist_ok=True)
        index_file = cls.index_file()
        # os.replace が原子的であるためには同一ファイルシステム上である必要があるので、
        # 一時ファイルは索引と同じディレクトリへ作る。
        fd, tmp_name = tempfile.mkstemp(
            dir=str(index_file.parent), prefix=".index-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            os.replace(tmp_name, index_file)
        except BaseException:
            # 置き換え前に失敗した場合だけ一時ファイルが残るため、ここで取り除く。
            # 成功時は os.replace により tmp_name は既に存在しない。
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    @classmethod
    def _upsert_index(cls, benchmark_result: Dict[str, Any], filepath: Path) -> None:
        summary = cls._build_summary(benchmark_result, filepath)
        # intent: DEC-001 — load から save までを 1 区間として保持しないと lost update が残る。
        with cls._index_lock:
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
        # intent: DEC-001 — 削除も load から save までを保持区間に含める。
        with cls._index_lock:
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
