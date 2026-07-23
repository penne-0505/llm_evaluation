import type { EvaluationRun, TaskTiming, TimingSummary } from '../types';

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

export function computeTimeRoi(
    score: number | null | undefined,
    ms: number | undefined,
): number | undefined {
    if (score === null || score === undefined || !ms || ms <= 0 || score <= 0) {
        return undefined;
    }
    return Number((score / (ms / 1000)).toFixed(1));
}

export function formatTimeRoi(
    score: number | null | undefined,
    ms: number | undefined,
): string {
    const roi = computeTimeRoi(score, ms);
    return roi === undefined ? 'N/A' : `${roi} 点/秒`;
}

/** Processing-time ms for Dashboard avg / ROI (DEC-004). */
export function runProcessingDurationMs(run: EvaluationRun): number | undefined {
    const summary = resolveTimingSummary(run);
    if (!summary || summary.totalDurationMs <= 0) {
        return undefined;
    }
    return summary.totalDurationMs;
}
