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
                return True
            return False
        except Exception:
            return False

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
