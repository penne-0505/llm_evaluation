"""評価結果の集計ロジック"""

import statistics
from typing import Any, Dict, List


class ResultAggregator:
    """
    複数回のjudge評価結果を集計する
    """

    @staticmethod
    def aggregate(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        n回分の評価結果を集計

        Args:
            runs: 個別の評価結果リスト

        Returns:
            {
                "runs": [...],  # 個別結果
                "aggregated": {
                    "logic_and_fact_mean": float,
                    "logic_and_fact_std": float,
                    "constraint_adherence_mean": float,
                    "constraint_adherence_std": float,
                    "helpfulness_mean": float,
                    "helpfulness_std": float,
                    "total_score_mean": float,
                    "total_score_std": float,
                    "critical_fail": bool,
                    "confidence_distribution": {"high": n, "medium": n, "low": n}
                }
            }
        """
        valid_runs = [r for r in runs if not r.get("skipped") and "error" not in r]

        if not valid_runs:
            return {"runs": runs, "aggregated": None}

        # スコアの収集
        scores = {
            "logic_and_fact": [],
            "constraint_adherence": [],
            "helpfulness_and_creativity": [],
            "total_score": [],
        }

        confidences = {"high": 0, "medium": 0, "low": 0}
        critical_fail_count = 0

        for run in valid_runs:
            # スコアの取得
            score_data = run.get("score", {})

            if "logic_and_fact" in score_data:
                scores["logic_and_fact"].append(float(score_data["logic_and_fact"]))

            if "constraint_adherence" in score_data:
                scores["constraint_adherence"].append(
                    float(score_data["constraint_adherence"])
                )

            if "helpfulness_and_creativity" in score_data:
                scores["helpfulness_and_creativity"].append(
                    float(score_data["helpfulness_and_creativity"])
                )
            elif "helpfulness" in score_data:
                # 短い名前でも対応
                scores["helpfulness_and_creativity"].append(
                    float(score_data["helpfulness"])
                )

            # total_score
            total = run.get("total_score")
            if total is not None:
                scores["total_score"].append(float(total))

            # confidence
            confidence = run.get("confidence", "low")
            if confidence in confidences:
                confidences[confidence] += 1
            else:
                confidences["low"] += 1

            # critical_fail
            if run.get("critical_fail", False):
                critical_fail_count += 1

        # 統計値の計算
        def calc_stats(values: List[float]) -> tuple:
            """平均と標準偏差を計算"""
            if not values:
                return 0.0, 0.0
            mean = statistics.mean(values)
            std = statistics.stdev(values) if len(values) > 1 else 0.0
            return mean, std

        logic_mean, logic_std = calc_stats(scores["logic_and_fact"])
        constraint_mean, constraint_std = calc_stats(scores["constraint_adherence"])
        helpfulness_mean, helpfulness_std = calc_stats(
            scores["helpfulness_and_creativity"]
        )
        total_mean, total_std = calc_stats(scores["total_score"])

        return {
            "runs": runs,
            "aggregated": {
                "logic_and_fact_mean": round(logic_mean, 1),
                "logic_and_fact_std": round(logic_std, 1),
                "constraint_adherence_mean": round(constraint_mean, 1),
                "constraint_adherence_std": round(constraint_std, 1),
                "helpfulness_mean": round(helpfulness_mean, 1),
                "helpfulness_std": round(helpfulness_std, 1),
                "total_score_mean": round(total_mean, 1),
                "total_score_std": round(total_std, 1),
                "critical_fail": critical_fail_count > 0,
                "confidence_distribution": confidences,
            },
        }

    @staticmethod
    def aggregate_all_judges(
        judge_results: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        全judge系統の結果を横断的に集計

        Args:
            judge_results: judgeファミリーごとの結果辞書

        Returns:
            横断サマリー
        """
        summary = {
            "by_judge": {},
            "cross_judge": {
                "score_variance_warnings": [],
                "low_confidence_tasks": [],
                "critical_fail_tasks": [],
            },
        }

        for judge_family, result in judge_results.items():
            agg = result.get("aggregated")
            if agg:
                summary["by_judge"][judge_family] = {
                    "total_score_mean": agg.get("total_score_mean", 0),
                    "total_score_std": agg.get("total_score_std", 0),
                    "critical_fail": agg.get("critical_fail", False),
                    "confidence_distribution": agg.get("confidence_distribution", {}),
                }

                # 分散警告（標準偏差 > 5）
                if agg.get("total_score_std", 0) > 5:
                    summary["cross_judge"]["score_variance_warnings"].append(
                        judge_family
                    )

                # low confidence
                conf_dist = agg.get("confidence_distribution", {})
                if conf_dist.get("low", 0) > 0:
                    summary["cross_judge"]["low_confidence_tasks"].append(judge_family)

                # critical fail
                if agg.get("critical_fail", False):
                    summary["cross_judge"]["critical_fail_tasks"].append(judge_family)

        return summary
