/**
 * Judge reliability display helpers.
 *
 * intent: INV-002 (Core/exclude-unreliable-judges) — reason codes come from backend;
 * frontend only maps codes to labels and filters UI from saved score_aggregation.
 */

import type { EvaluationRun, JudgeSummary } from '../types';

export const RELIABILITY_REASON_LABELS: Record<string, string> = {
    high_variance: 'ばらつき大（試行間 SD）',
    low_confidence: '低信頼レビューあり',
    critical_fail: '重大な失敗を検出',
    cross_judge_divergence: 'judge 間スコア乖離',
};

export function formatReliabilityReason(code: string): string {
    return RELIABILITY_REASON_LABELS[code] ?? code;
}

export function formatHeroScore(score: number | null | undefined): string {
    if (score === null || score === undefined) return '\u2014';
    return Number.isInteger(score) ? String(score) : score.toFixed(1);
}

export function isHeroScoreAvailable(score: number | null | undefined): score is number {
    return typeof score === 'number' && !Number.isNaN(score);
}

export function excludedJudgeIdSet(run: EvaluationRun): Set<string> {
    if (!run.excludeUnreliableJudges) return new Set();
    const excluded = run.scoreAggregation?.excludedJudges ?? [];
    return new Set(excluded.map((entry) => entry.judgeId));
}

export function computeJudgeSummaries(run: EvaluationRun): JudgeSummary[] {
    const excluded = excludedJudgeIdSet(run);
    const map = new Map<string, { scores: number[]; name: string }>();
    // holistic タスクは別セクションで表示するためサマリーから除外
    run.taskResults.forEach((tr) => {
        tr.judgeEvaluations.forEach((je) => {
            if (excluded.has(je.judgeModelId)) return;
            const existing = map.get(je.judgeModelId) || {
                scores: [],
                name: je.judgeModelName,
            };
            existing.scores.push(je.totalScore.mean);
            map.set(je.judgeModelId, existing);
        });
    });
    return Array.from(map.entries()).map(([id, data]) => ({
        judgeModelId: id,
        judgeModelName: data.name,
        averageScore:
            Math.round(
                (data.scores.reduce((a, b) => a + b, 0) / data.scores.length) * 10,
            ) / 10,
        tasksEvaluated: data.scores.length,
    }));
}
