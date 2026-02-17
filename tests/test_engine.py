"""コア機能のテスト"""

import json
import os
import sys
from unittest.mock import Mock, patch, AsyncMock

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.json_parser import JudgeResponseParser, ParseError
from core.result_aggregator import ResultAggregator


def test_json_parser_valid():
    """有効なJSONレスポンスのパーステスト"""
    print("\n=== JSONパーサー有効ケーステスト ===")

    valid_response = json.dumps(
        {
            "task_name": "テストタスク",
            "task_type": "fact",
            "weights": {
                "logic_and_fact": 60,
                "constraint_adherence": 30,
                "helpfulness_and_creativity": 10,
            },
            "score": {
                "logic_and_fact": 55,
                "constraint_adherence": 28,
                "helpfulness_and_creativity": 8,
            },
            "total_score": 91,
            "reasoning": {
                "logic_and_fact": "正確な回答",
                "constraint_adherence": "制約を遵守",
                "helpfulness_and_creativity": "実用的",
            },
            "critical_fail": False,
            "critical_fail_reason": None,
            "confidence": "high",
        }
    )

    result = JudgeResponseParser.parse(valid_response)

    assert result["task_name"] == "テストタスク"
    assert result["task_type"] == "fact"
    assert result["total_score"] == 91
    assert result["critical_fail"] == False
    assert result["confidence"] == "high"

    print("✓ 有効なJSONを正しくパース")
    print("JSONパーサー有効ケーステスト完了")


def test_json_parser_with_markdown():
    """Markdownコードブロック付きJSONのテスト"""
    print("\n=== Markdownコードブロック付きJSONテスト ===")

    markdown_response = """```json
{
    "task_name": "テスト",
    "task_type": "creative",
    "score": {
        "logic_and_fact": 30,
        "constraint_adherence": 30,
        "helpfulness_and_creativity": 35
    },
    "total_score": 95,
    "critical_fail": false,
    "confidence": "medium"
}
```"""

    result = JudgeResponseParser.parse(markdown_response)

    assert result["task_type"] == "creative"
    assert result["total_score"] == 95

    print("✓ Markdownコードブロックを除去してパース")
    print("Markdownコードブロック付きJSONテスト完了")


def test_json_parser_missing_fields():
    """必須フィールド欠如時のエラーテスト"""
    print("\n=== 必須フィールド欠如テスト ===")

    # task_name欠如
    invalid_response = json.dumps({"task_type": "fact", "score": {}, "total_score": 80})

    try:
        JudgeResponseParser.parse(invalid_response)
        assert False, "ParseErrorが発生すべき"
    except ParseError as e:
        print(f"✓ 必須フィールド欠如でエラー: {e}")

    print("必須フィールド欠如テスト完了")


def test_json_parser_invalid_task_type():
    """無効なtask_typeのテスト"""
    print("\n=== 無効なtask_typeテスト ===")

    invalid_response = json.dumps(
        {
            "task_name": "テスト",
            "task_type": "invalid_type",
            "score": {},
            "total_score": 80,
        }
    )

    try:
        JudgeResponseParser.parse(invalid_response)
        assert False, "ParseErrorが発生すべき"
    except ParseError as e:
        print(f"✓ 無効なtask_typeでエラー: {e}")

    print("無効なtask_typeテスト完了")


def test_json_parser_with_retry():
    """リトライ付きパースのテスト"""
    print("\n=== リトライ付きパーステスト ===")

    # 最初は余分なテキスト付き、2回目はクリーニング後に成功
    dirty_response = 'ここからJSON開始 {"task_name": "test", "task_type": "speculative", "score": {}, "total_score": 70} JSON終了'

    result = JudgeResponseParser.parse_with_retry(dirty_response, max_retries=1)

    assert result["task_name"] == "test"
    assert result["total_score"] == 70

    print("✓ リトライでクリーニング後にパース成功")
    print("リトライ付きパーステスト完了")


def test_result_aggregator_basic():
    """結果集計の基本テスト"""
    print("\n=== 結果集計基本テスト ===")

    runs = [
        {
            "task_name": "test",
            "task_type": "fact",
            "score": {
                "logic_and_fact": 50,
                "constraint_adherence": 25,
                "helpfulness_and_creativity": 8,
            },
            "total_score": 83,
            "confidence": "high",
            "critical_fail": False,
        },
        {
            "task_name": "test",
            "task_type": "fact",
            "score": {
                "logic_and_fact": 55,
                "constraint_adherence": 28,
                "helpfulness_and_creativity": 9,
            },
            "total_score": 92,
            "confidence": "high",
            "critical_fail": False,
        },
        {
            "task_name": "test",
            "task_type": "fact",
            "score": {
                "logic_and_fact": 52,
                "constraint_adherence": 26,
                "helpfulness_and_creativity": 7,
            },
            "total_score": 85,
            "confidence": "medium",
            "critical_fail": False,
        },
    ]

    result = ResultAggregator.aggregate(runs)

    assert result["aggregated"] is not None
    assert result["aggregated"]["logic_and_fact_mean"] == 52.3  # (50+55+52)/3
    assert result["aggregated"]["total_score_mean"] == 86.7  # (83+92+85)/3
    assert result["aggregated"]["confidence_distribution"]["high"] == 2
    assert result["aggregated"]["confidence_distribution"]["medium"] == 1
    assert result["aggregated"]["critical_fail"] == False

    print(f"✓ 平均スコア: {result['aggregated']['total_score_mean']}")
    print(f"✓ 標準偏差: {result['aggregated']['total_score_std']}")
    print("結果集計基本テスト完了")


def test_result_aggregator_with_skipped():
    """スキップされたランを含む集計テスト"""
    print("\n=== スキップ含む集計テスト ===")

    runs = [
        {
            "score": {
                "logic_and_fact": 50,
                "constraint_adherence": 25,
                "helpfulness_and_creativity": 8,
            },
            "total_score": 83,
            "confidence": "high",
            "critical_fail": False,
        },
        {"error": "パース失敗", "skipped": True},
        {
            "score": {
                "logic_and_fact": 55,
                "constraint_adherence": 28,
                "helpfulness_and_creativity": 9,
            },
            "total_score": 92,
            "confidence": "high",
            "critical_fail": False,
        },
    ]

    result = ResultAggregator.aggregate(runs)

    # スキップを除いて2回分で計算
    assert result["aggregated"]["logic_and_fact_mean"] == 52.5  # (50+55)/2

    print("✓ スキップされたランを正しく除外")
    print("スキップ含む集計テスト完了")


def test_result_aggregator_empty():
    """空の結果集計テスト"""
    print("\n=== 空の結果集計テスト ===")

    runs = [
        {"error": "エラー1", "skipped": True},
        {"error": "エラー2", "skipped": True},
    ]

    result = ResultAggregator.aggregate(runs)

    assert result["aggregated"] is None

    print("✓ 全てスキップ時はaggregatedがNone")
    print("空の結果集計テスト完了")


def test_result_aggregator_cross_judge():
    """横断サマリーテスト"""
    print("\n=== 横断サマリーテスト ===")

    judge_results = {
        "openai": {
            "aggregated": {
                "total_score_mean": 85.0,
                "total_score_std": 2.5,
                "critical_fail": False,
                "confidence_distribution": {"high": 3, "medium": 0, "low": 0},
            }
        },
        "anthropic": {
            "aggregated": {
                "total_score_mean": 78.0,
                "total_score_std": 6.0,  # > 5 なので警告
                "critical_fail": False,
                "confidence_distribution": {"high": 2, "medium": 1, "low": 0},
            }
        },
        "gemini": {
            "aggregated": {
                "total_score_mean": 70.0,
                "total_score_std": 3.0,
                "critical_fail": True,  # critical_fail
                "confidence_distribution": {
                    "high": 0,
                    "medium": 1,
                    "low": 2,
                },  # lowあり
            }
        },
    }

    summary = ResultAggregator.aggregate_all_judges(judge_results)

    assert "openai" in summary["by_judge"]
    assert "anthropic" in summary["cross_judge"]["score_variance_warnings"]
    assert "gemini" in summary["cross_judge"]["low_confidence_tasks"]
    assert "gemini" in summary["cross_judge"]["critical_fail_tasks"]

    print("✓ 標準偏差>5のjudgeを検出")
    print("✓ low confidenceのjudgeを検出")
    print("✓ critical_failのjudgeを検出")
    print("横断サマリーテスト完了")


def run_all_tests():
    """全テストを実行"""
    print("=" * 50)
    print("コア機能テスト開始")
    print("=" * 50)

    try:
        test_json_parser_valid()
        test_json_parser_with_markdown()
        test_json_parser_missing_fields()
        test_json_parser_invalid_task_type()
        test_json_parser_with_retry()
        test_result_aggregator_basic()
        test_result_aggregator_with_skipped()
        test_result_aggregator_empty()
        test_result_aggregator_cross_judge()

        print("\n" + "=" * 50)
        print("✅ 全テスト完了")
        print("=" * 50)
        return True

    except AssertionError as e:
        print(f"\n❌ テスト失敗: {e}")
        import traceback

        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ 予期しないエラー: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
