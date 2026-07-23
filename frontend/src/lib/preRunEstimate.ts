/**
 * Pre-run cost / wall-clock duration estimates.
 *
 * intent: DEC-001..005 (UI/pre-run-estimate) — history-first matching by subject,
 * config load scaling as assist, heuristic duration only when no history;
 * never zero-fill unknown cost (INV-001).
 */

import type { EvaluationRun } from '../types';

export type PreRunEstimateSource =
    | 'history'
    | 'history_scaled'
    | 'heuristic'
    | 'unavailable';

export type PreRunEstimateInput = {
    subjectModelId: string | null;
    freeTextSubject?: string;
    taskCount: number;
    judgeCount: number;
    subjectRunCount: number;
    judgeRunCount: number;
    /** Used only for no-history duration heuristic (DEC-004). */
    totalSteps: number;
};

export type PreRunEstimate = {
    costUsd: number | null;
    costSource: PreRunEstimateSource;
    durationMs: number | null;
    durationSource: PreRunEstimateSource;
    matchedRunId: string | null;
    scale: number;
    labels: {
        cost: string;
        duration: string;
    };
};

/** Rough ms per pipeline step when no subject history exists (DEC-004). */
export const ASSUMED_MS_PER_STEP = 12_000;

/** Treat load ratio within this band as unscaled history (DEC-003). */
export const SCALE_NEAR_BAND = { min: 0.85, max: 1.15 };

export function plannedLoad(input: {
    taskCount: number;
    judgeCount: number;
    subjectRunCount: number;
    judgeRunCount: number;
}): number {
    const tasks = Math.max(0, Number(input.taskCount) || 0);
    const judges = Math.max(1, Number(input.judgeCount) || 1);
    const subjectRuns = Math.max(1, Number(input.subjectRunCount) || 1);
    const judgeRuns = Math.max(1, Number(input.judgeRunCount) || 1);
    return tasks * (subjectRuns + judges * judgeRuns);
}

/** History summaries lack run counts → assume 1 subject run and 1 judge run (DEC-003). */
export function historicalLoad(taskCount: number, judgeCount: number): number {
    const tasks = Math.max(0, Number(taskCount) || 0);
    const judges = Math.max(1, Number(judgeCount) || 1);
    return tasks * (1 + judges);
}

export function subjectMatchesRun(
    run: Pick<EvaluationRun, 'subjectModelId' | 'subjectModelName'>,
    subjectModelId: string | null,
    freeTextSubject?: string,
): boolean {
    if (subjectModelId) {
        return run.subjectModelId === subjectModelId;
    }
    const free = (freeTextSubject || '').trim();
    if (!free) return false;
    return run.subjectModelId === free || run.subjectModelName === free;
}

function matchDistance(
    run: Pick<EvaluationRun, 'taskCount' | 'judgeCount'>,
    taskCount: number,
    judgeCount: number,
): number {
    const dTasks = Math.abs((run.taskCount || 0) - taskCount);
    const dJudges = Math.abs((run.judgeCount || 0) - Math.max(1, judgeCount));
    return dTasks + 2 * dJudges;
}

export function pickBestHistoricalRun(
    runs: EvaluationRun[],
    input: Pick<PreRunEstimateInput, 'subjectModelId' | 'freeTextSubject' | 'taskCount' | 'judgeCount'>,
): EvaluationRun | null {
    const candidates = runs.filter((run) =>
        subjectMatchesRun(run, input.subjectModelId, input.freeTextSubject),
    );
    if (candidates.length === 0) return null;

    candidates.sort((a, b) => {
        const da = matchDistance(a, input.taskCount, input.judgeCount);
        const db = matchDistance(b, input.taskCount, input.judgeCount);
        if (da !== db) return da - db;
        return (b.timestamp || '').localeCompare(a.timestamp || '');
    });
    return candidates[0] ?? null;
}

function sourceLabel(source: PreRunEstimateSource): string {
    switch (source) {
        case 'history':
            return '履歴';
        case 'history_scaled':
            return '履歴+構成補正';
        case 'heuristic':
            return '粗い推定';
        case 'unavailable':
        default:
            return '不明';
    }
}

function needsScale(
    scale: number,
    run: Pick<EvaluationRun, 'taskCount' | 'judgeCount'>,
    input: Pick<PreRunEstimateInput, 'taskCount' | 'judgeCount' | 'subjectRunCount' | 'judgeRunCount'>,
): boolean {
    if (scale < SCALE_NEAR_BAND.min || scale > SCALE_NEAR_BAND.max) return true;
    if ((run.taskCount || 0) !== input.taskCount) return true;
    if ((run.judgeCount || 0) !== Math.max(1, input.judgeCount)) return true;
    if (input.subjectRunCount !== 1 || input.judgeRunCount !== 1) return true;
    return false;
}

export function computePreRunEstimate(
    runs: EvaluationRun[],
    input: PreRunEstimateInput,
): PreRunEstimate {
    const empty: PreRunEstimate = {
        costUsd: null,
        costSource: 'unavailable',
        durationMs: null,
        durationSource: 'unavailable',
        matchedRunId: null,
        scale: 1,
        labels: {
            cost: sourceLabel('unavailable'),
            duration: sourceLabel('unavailable'),
        },
    };

    if (input.taskCount <= 0) {
        return empty;
    }

    const match = pickBestHistoricalRun(runs, input);
    if (!match) {
        const steps = Math.max(0, Number(input.totalSteps) || 0);
        const durationMs = steps > 0 ? steps * ASSUMED_MS_PER_STEP : null;
        const durationSource: PreRunEstimateSource =
            durationMs != null ? 'heuristic' : 'unavailable';
        return {
            ...empty,
            // intent-invariant: INV-001 (UI/pre-run-estimate) — unknown cost stays null
            costUsd: null,
            costSource: 'unavailable',
            durationMs,
            durationSource,
            labels: {
                cost: sourceLabel('unavailable'),
                duration: sourceLabel(durationSource),
            },
        };
    }

    const Lplan = plannedLoad(input);
    const Lhist = historicalLoad(match.taskCount, match.judgeCount || 1);
    const scale = Lhist > 0 ? Lplan / Lhist : 1;
    const scaled = needsScale(scale, match, input);
    const source: PreRunEstimateSource = scaled ? 'history_scaled' : 'history';
    const factor = scaled ? scale : 1;

    const rawCost =
        typeof match.estimatedCostUsd === 'number' && Number.isFinite(match.estimatedCostUsd)
            ? match.estimatedCostUsd
            : null;
    const rawDuration =
        typeof match.executionDurationMs === 'number' &&
        Number.isFinite(match.executionDurationMs) &&
        match.executionDurationMs > 0
            ? match.executionDurationMs
            : null;

    const costUsd = rawCost != null ? rawCost * factor : null;
    const durationMs = rawDuration != null ? rawDuration * factor : null;

    return {
        costUsd,
        costSource: costUsd != null ? source : 'unavailable',
        durationMs,
        durationSource: durationMs != null ? source : 'unavailable',
        matchedRunId: match.id,
        scale: factor,
        labels: {
            cost: sourceLabel(costUsd != null ? source : 'unavailable'),
            duration: sourceLabel(durationMs != null ? source : 'unavailable'),
        },
    };
}

export function formatPreRunCost(costUsd: number | null): string {
    if (costUsd === null || !Number.isFinite(costUsd)) return '—';
    if (costUsd < 0.01) return `$${costUsd.toFixed(4)}`;
    return `$${costUsd.toFixed(2)}`;
}
