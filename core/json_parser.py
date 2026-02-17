"""JudgeレスポンスのJSONパーサー"""

import json
import re
from typing import Any, Dict


class ParseError(Exception):
    """JSONパースエラー"""

    pass


class JudgeResponseParser:
    """
    judgeからのJSONレスポンスをパースする

    期待されるスキーマ:
    {
        "task_name": str,
        "task_type": "fact" | "creative" | "speculative",
        "inferred_task_type": str | null,
        "weights": {...},
        "score": {...},
        "total_score": int,
        "reasoning": {...},
        "critical_fail": bool,
        "critical_fail_reason": str | null,
        "confidence": "high" | "medium" | "low"
    }
    """

    @staticmethod
    def parse(response: str) -> Dict[str, Any]:
        """
        JSONレスポンスをパース

        - Markdownコードブロックを除去
        - 必須フィールドの検証
        - 型変換

        Args:
            response: judgeからの生レスポンス文字列

        Returns:
            パース済みの辞書

        Raises:
            ParseError: パース失敗時
        """
        # Markdownコードブロックの除去
        cleaned = re.sub(r"```json\n?", "", response)
        cleaned = re.sub(r"\n?```", "", cleaned)
        cleaned = cleaned.strip()

        # JSONパース
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ParseError(f"JSONパース失敗: {str(e)}") from e

        # 必須フィールド検証
        required = ["task_name", "task_type", "score", "total_score"]
        for field in required:
            if field not in data:
                raise ParseError(f"必須フィールド '{field}' が存在しません")

        # task_typeの検証
        valid_task_types = ["fact", "creative", "speculative"]
        if data["task_type"] not in valid_task_types:
            raise ParseError(f"無効なtask_type: {data['task_type']}")

        # total_scoreの検証
        if not isinstance(data["total_score"], (int, float)):
            raise ParseError(f"total_scoreが数値ではありません: {data['total_score']}")

        # scoreの検証
        if not isinstance(data["score"], dict):
            raise ParseError("scoreが辞書ではありません")

        # confidenceの検証（存在する場合）
        if "confidence" in data:
            valid_confidences = ["high", "medium", "low"]
            if data["confidence"] not in valid_confidences:
                data["confidence"] = "low"  # 無効な値はlowにフォールバック

        return data

    @staticmethod
    def parse_with_retry(response: str, max_retries: int = 1) -> Dict[str, Any]:
        """
        リトライ付きでJSONをパース

        Args:
            response: judgeからの生レスポンス文字列
            max_retries: 最大リトライ回数

        Returns:
            パース済みの辞書

        Raises:
            ParseError: 全てのリトライで失敗した場合
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return JudgeResponseParser.parse(response)
            except ParseError as e:
                last_error = e
                if attempt < max_retries:
                    # リトライ前に追加のクリーニングを試みる
                    response = JudgeResponseParser._additional_cleaning(response)

        raise last_error or ParseError("パースに失敗しました")

    @staticmethod
    def _additional_cleaning(response: str) -> str:
        """追加のクリーニング処理"""
        # 余分な空白や改行の除去
        cleaned = response.strip()

        # JSON以外のテキストを除去（最初の{から最後の}までを抽出）
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start != -1 and end != -1 and start < end:
            cleaned = cleaned[start : end + 1]

        return cleaned
