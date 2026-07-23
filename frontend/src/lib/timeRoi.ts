import type { EvaluationRun, TaskTiming, TimingSummary } from '../types';
import { isHeroScoreAvailable } from './judgeReliability';

export type TimeRoiTab = 'total' | 'subject' | 'judge';

/**
 * intent: DEC-001/003 (Core/time-roi-task-timing) — ROI denominator is task_timing
 * subject+judge totals only; never fall back to executionDurationMs (wall-clock).
 */
export function resolveTimingSummary(run: EvaluationRun): TimingSummary | undefined {
    if (run.timingSummary) {
        return run.timingSummary;
    }
    return sumTaskTimings(run.taskResults);
}

export function sumTaskTimings(
    tasks: Array<{ taskTiming?: TaskTiming }>,
): TimingSummary | undefined {
    if (!tasks.length) {
        return undefined;
    }
    let subjectDurationMs = 0;
    let judgeDurationMs = 0;
    for (const task of tasks) {
        if (!task.taskTiming) {
            return undefined;
        }
        subjectDurationMs += Number(task.taskTiming.subjectDurationMs || 0);
        judgeDurationMs += Number(task.taskTiming.judgeDurationMs || 0);
    }
    return {
        subjectDurationMs,
        judgeDurationMs,
        totalDurationMs: subjectDurationMs + judgeDurationMs,
    };
}

export function resolveTimeRoiDenominator(
    summary: TimingSummary | undefined,
    tab: TimeRoiTab,
): { ms: number | undefined; label: string; available: boolean } {
    if (!summary) {
        const label =
            tab === 'subject' ? '被検時間' : tab === 'judge' ? 'Judge時間' : '総時間';
        return { ms: undefined, label, available: false };
    }

    if (tab === 'subject') {
        const ms = summary.subjectDurationMs;
        return {
            ms: ms > 0 ? ms : undefined,
            label: '被検時間',
            available: ms > 0,
        };
    }
    if (tab === 'judge') {
        const ms = summary.judgeDurationMs;
        return {
            ms: ms > 0 ? ms : undefined,
            label: 'Judge時間',
            available: ms > 0,
        };
    }
    const ms = summary.totalDurationMs;
    return {
        ms: ms > 0 ? ms : undefined,
        label: '総時間',
        available: ms > 0,
    };
}

/**
 * intent: DEC-005 (Core/time-roi-task-timing) — numerator is Σtask score
 * (averageScore × taskCount), matching averageScore as the unweighted task mean.
 */
export function runScoreSum(run: Pick<EvaluationRun, 'averageScore' | 'taskCount'>): number | undefined {
    if (!isHeroScoreAvailable(run.averageScore) || run.averageScore <= 0) {
        return undefined;
    }
    const n = Number(run.taskCount || 0);
    if (!Number.isFinite(n) || n <= 0) {
        return undefined;
    }
    return run.averageScore * n;
}

/**
 * intent: DEC-005 (Core/time-roi-task-timing) — Σscore / processing minutes → 点/分
 * (aligned with cost ROI's 点/$ unit pattern).
 */
export function computeTimeRoi(
    scoreSum: number | null | undefined,
    ms: number | undefined,
): number | undefined {
    if (scoreSum === null || scoreSum === undefined || !ms || ms <= 0 || scoreSum <= 0) {
        return undefined;
    }
    const minutes = ms / 60_000;
    if (minutes <= 0) {
        return undefined;
    }
    return Number((scoreSum / minutes).toFixed(1));
}

export function formatTimeRoi(
    scoreSum: number | null | undefined,
    ms: number | undefined,
): string {
    const roi = computeTimeRoi(scoreSum, ms);
    return roi === undefined ? 'N/A' : `${roi} 点/分`;
}

/** Processing-time ms for Dashboard avg / ROI (DEC-004). */
export function runProcessingDurationMs(run: EvaluationRun): number | undefined {
    const summary = resolveTimingSummary(run);
    if (!summary || summary.totalDurationMs <= 0) {
        return undefined;
    }
    return summary.totalDurationMs;
}
