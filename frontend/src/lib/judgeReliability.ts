/**
 * Judge reliability display helpers.
 *
 * intent: INV-002 (Core/exclude-unreliable-judges) — reason codes come from backend;
 * frontend only maps codes to labels and filters UI from saved score_aggregation.
 */

import type { EvaluationRun, JudgeSummary, ReviewFlag, TaskResult } from '../types';

/** Mirrors backend `core/judge_reliability.py` HIGH_VARIANCE_STD_THRESHOLD */
export const HIGH_VARIANCE_STD_THRESHOLD = 5;

/** Mirrors backend `core/judge_reliability.py` CROSS_JUDGE_DIVERGENCE_RANGE_THRESHOLD */
export const CROSS_JUDGE_DIVERGENCE_RANGE_THRESHOLD = 15;

export const RELIABILITY_REASON_LABELS: Record<string, string> = {
    high_variance: 'ばらつき大（試行間 SD）',
    low_confidence: '低信頼レビューあり',
    critical_fail: '重大な失敗を検出',
    cross_judge_divergence: 'judge 間スコア乖離',
};

export function formatReliabilityReason(code: string): string {
    return RELIABILITY_REASON_LABELS[code] ?? code;
}

function formatTrialSd(sd: number): string {
    return Number.isInteger(sd) ? String(sd) : sd.toFixed(1);
}

/**
 * True when judge-mean range on a task exceeds the backend divergence threshold.
 * intent: DEC-001 (Core/exclude-unreliable-judges) — review flags must include the
 * same participants flagged for cross_judge_divergence exclusion.
 */
export function taskHasCrossJudgeDivergence(
    taskResult: Pick<TaskResult, 'judgeEvaluations'>,
): boolean {
    const means = taskResult.judgeEvaluations.map((je) => je.totalScore.mean);
    if (means.length < 2) return false;
    return Math.max(...means) - Math.min(...means) > CROSS_JUDGE_DIVERGENCE_RANGE_THRESHOLD;
}

/** Footer「要確認」flags — criteria aligned with backend collect_unreliable_judges. */
export function computeReviewFlags(run: EvaluationRun): ReviewFlag[] {
    const flags: ReviewFlag[] = [];
    run.taskResults.forEach((tr) => {
        // intent: DEC-001 (Core/exclude-unreliable-judges) — divergence is task-scoped;
        // every participating judge on a divergent task gets the same reason.
        const divergent = taskHasCrossJudgeDivergence(tr);
        tr.judgeEvaluations.forEach((je) => {
            const reasons: string[] = [];
            if (je.totalScore.sd > HIGH_VARIANCE_STD_THRESHOLD) {
                reasons.push(`ばらつき大（試行間 SD ${formatTrialSd(je.totalScore.sd)}）`);
            }
            if (je.criticalFail.detected) reasons.push('重大な失敗を検出');
            if (je.confidenceDistribution.low > 0) {
                reasons.push(`低信頼レビュー ${je.confidenceDistribution.low} 件`);
            }
            if (divergent) {
                reasons.push(formatReliabilityReason('cross_judge_divergence'));
            }
            if (reasons.length > 0) {
                flags.push({
                    taskId: tr.taskId,
                    judgeModelName: je.judgeModelName,
                    reasons,
                });
            }
        });
    });
    return flags;
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
