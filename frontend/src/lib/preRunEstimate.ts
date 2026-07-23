/**
 * Pre-run cost / wall-clock duration estimates.
 *
 * intent: DEC-001..006 (UI/pre-run-estimate) — multi-run similarity pool,
 * unitize before mix, wall-clock as wait, asymmetric subject gates;
 * never zero-fill unknown cost (INV-001); never mix other-subject into subject cost (INV-002).
 *
 * Formula/constants: `_docs/reference/UI/pre-run-estimate/reference.md`
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
    /** Injected clock for deterministic tests (ms since epoch). */
    nowMs?: number;
};

export type PreRunEstimate = {
    costUsd: number | null;
    costSource: PreRunEstimateSource;
    durationMs: number | null;
    durationSource: PreRunEstimateSource;
    /** Highest-weight contributing run id, if any. */
    matchedRunId: string | null;
    /** L_plan / weight-averaged L_hist for the primary channel used (1 when N/A). */
    scale: number;
    labels: {
        cost: string;
        duration: string;
    };
};

/** Rough ms per pipeline step when no wall history exists (DEC-004). */
export const ASSUMED_MS_PER_STEP = 12_000;

/** Treat load ratio within this band as unscaled history. */
export const SCALE_NEAR_BAND = { min: 0.85, max: 1.15 };

/** Distance decay (reference). */
export const WEIGHT_ALPHA = 0.35;
/** Soft subject-mismatch gate for judge channels (reference). */
export const WEIGHT_BETA = 0.25;
/** Soft subject-mismatch gate for wall (reference); γ > 0. */
export const WEIGHT_GAMMA = 0.1;
/** Recency half-life in days (reference). */
export const WEIGHT_HALF_LIFE_DAYS = 90;
export const WEIGHT_LAMBDA = Math.LN2 / WEIGHT_HALF_LIFE_DAYS;

export type EstimateChannel = 'subject_cost' | 'judge_cost' | 'wall';

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

/** History summaries lack run counts → assume 1 subject run and 1 judge run. */
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

export function matchDistance(
    run: Pick<EvaluationRun, 'taskCount' | 'judgeCount'>,
    taskCount: number,
    judgeCount: number,
): number {
    const dTasks = Math.abs((run.taskCount || 0) - taskCount);
    const dJudges = Math.abs((run.judgeCount || 0) - Math.max(1, judgeCount));
    return dTasks + 2 * dJudges;
}

export function ageDays(timestamp: string | undefined, nowMs: number): number {
    if (!timestamp) return 0;
    const t = Date.parse(timestamp);
    if (!Number.isFinite(t)) return 0;
    return Math.max(0, (nowMs - t) / (1000 * 60 * 60 * 24));
}

/** Subject gate s_{i,c} from reference. */
export function subjectGate(channel: EstimateChannel, subjectMatch: boolean): number {
    if (subjectMatch) return 1;
    switch (channel) {
        case 'subject_cost':
            // intent-invariant: INV-002 (UI/pre-run-estimate) — other-subject never enters subject cost
            return 0;
        case 'judge_cost':
            return WEIGHT_BETA;
        case 'wall':
            return WEIGHT_GAMMA;
        default:
            return 0;
    }
}

export function channelWeight(
    channel: EstimateChannel,
    subjectMatch: boolean,
    distance: number,
    age: number,
): number {
    const s = subjectGate(channel, subjectMatch);
    if (s <= 0) return 0;
    return s * Math.exp(-WEIGHT_ALPHA * distance) * Math.exp(-WEIGHT_LAMBDA * age);
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

type ChannelSample = {
    runId: string;
    rate: number;
    weight: number;
    Lhist: number;
    taskCount: number;
    judgeCount: number;
};

function finitePositive(n: unknown): n is number {
    return typeof n === 'number' && Number.isFinite(n) && n > 0;
}

function finiteNonNeg(n: unknown): n is number {
    return typeof n === 'number' && Number.isFinite(n) && n >= 0;
}

function subjectCostValue(run: EvaluationRun): number | null {
    if (finiteNonNeg(run.subjectEstimatedCostUsd)) {
        return run.subjectEstimatedCostUsd;
    }
    // Legacy summaries: only total cost — treat as subject-gated total when same subject.
    if (finiteNonNeg(run.estimatedCostUsd) && run.subjectEstimatedCostUsd == null) {
        return run.estimatedCostUsd;
    }
    return null;
}

function judgeCostValue(run: EvaluationRun): number | null {
    if (!finiteNonNeg(run.estimatedCostUsd)) return null;
    if (!finiteNonNeg(run.subjectEstimatedCostUsd)) return null;
    const judge = run.estimatedCostUsd - run.subjectEstimatedCostUsd;
    if (!Number.isFinite(judge) || judge < 0) return null;
    return judge;
}

function wallValue(run: EvaluationRun): number | null {
    if (!finitePositive(run.executionDurationMs)) return null;
    return run.executionDurationMs;
}

function collectChannelSamples(
    runs: EvaluationRun[],
    input: PreRunEstimateInput,
    channel: EstimateChannel,
    valueOf: (run: EvaluationRun) => number | null,
): ChannelSample[] {
    const nowMs = input.nowMs ?? Date.now();
    const samples: ChannelSample[] = [];
    for (const run of runs) {
        const value = valueOf(run);
        if (value == null) continue;
        const Lhist = historicalLoad(run.taskCount, run.judgeCount || 1);
        if (Lhist <= 0) continue;
        const match = subjectMatchesRun(run, input.subjectModelId, input.freeTextSubject);
        const d = matchDistance(run, input.taskCount, input.judgeCount);
        const age = ageDays(run.timestamp, nowMs);
        const weight = channelWeight(channel, match, d, age);
        if (weight <= 0) continue;
        samples.push({
            runId: run.id,
            rate: value / Lhist,
            weight,
            Lhist,
            taskCount: run.taskCount || 0,
            judgeCount: run.judgeCount || 0,
        });
    }
    return samples;
}

export function weightedRate(samples: ChannelSample[]): {
    rate: number | null;
    sumW: number;
    meanLhist: number;
    topRunId: string | null;
} {
    let sumW = 0;
    let sumWR = 0;
    let sumWL = 0;
    let topRunId: string | null = null;
    let topW = -1;
    for (const s of samples) {
        sumW += s.weight;
        sumWR += s.weight * s.rate;
        sumWL += s.weight * s.Lhist;
        if (s.weight > topW) {
            topW = s.weight;
            topRunId = s.runId;
        }
    }
    if (sumW <= 0) {
        return { rate: null, sumW: 0, meanLhist: 0, topRunId: null };
    }
    return {
        rate: sumWR / sumW,
        sumW,
        meanLhist: sumWL / sumW,
        topRunId,
    };
}

function needsScaledLabel(
    input: PreRunEstimateInput,
    samples: ChannelSample[],
    meanLhist: number,
    Lplan: number,
): boolean {
    if (input.subjectRunCount !== 1 || input.judgeRunCount !== 1) return true;
    if (meanLhist > 0) {
        const scale = Lplan / meanLhist;
        if (scale < SCALE_NEAR_BAND.min || scale > SCALE_NEAR_BAND.max) return true;
    }
    const planJudges = Math.max(1, input.judgeCount);
    for (const s of samples) {
        if (s.taskCount !== input.taskCount || s.judgeCount !== planJudges) return true;
    }
    return false;
}

function emptyEstimate(): PreRunEstimate {
    return {
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
}

export function computePreRunEstimate(
    runs: EvaluationRun[],
    input: PreRunEstimateInput,
): PreRunEstimate {
    if (input.taskCount <= 0) {
        return emptyEstimate();
    }

    const Lplan = plannedLoad(input);

    const subjectSamples = collectChannelSamples(runs, input, 'subject_cost', subjectCostValue);
    const judgeSamples = collectChannelSamples(runs, input, 'judge_cost', judgeCostValue);
    const wallSamples = collectChannelSamples(runs, input, 'wall', wallValue);

    const subjectPool = weightedRate(subjectSamples);
    const judgePool = weightedRate(judgeSamples);
    const wallPool = weightedRate(wallSamples);

    let costUsd: number | null = null;
    const costParts: number[] = [];
    if (subjectPool.rate != null) costParts.push(subjectPool.rate * Lplan);
    if (judgePool.rate != null) costParts.push(judgePool.rate * Lplan);
    if (costParts.length > 0) {
        costUsd = costParts.reduce((a, b) => a + b, 0);
    }

    // intent-invariant: INV-001 (UI/pre-run-estimate) — unknown cost stays null
    const costSamples = [...subjectSamples, ...judgeSamples];
    const costMeanL =
        subjectPool.sumW + judgePool.sumW > 0
            ? ((subjectPool.meanLhist * subjectPool.sumW + judgePool.meanLhist * judgePool.sumW) /
                  (subjectPool.sumW + judgePool.sumW))
            : 0;
    const costScaled =
        costUsd != null && needsScaledLabel(input, costSamples, costMeanL, Lplan);
    const costSource: PreRunEstimateSource =
        costUsd == null ? 'unavailable' : costScaled ? 'history_scaled' : 'history';
    const costScale =
        costUsd != null && costMeanL > 0 ? Lplan / costMeanL : 1;

    let durationMs: number | null = null;
    let durationSource: PreRunEstimateSource = 'unavailable';
    let durationScale = 1;
    if (wallPool.rate != null) {
        durationMs = wallPool.rate * Lplan;
        const wallScaled = needsScaledLabel(input, wallSamples, wallPool.meanLhist, Lplan);
        durationSource = wallScaled ? 'history_scaled' : 'history';
        durationScale = wallPool.meanLhist > 0 ? Lplan / wallPool.meanLhist : 1;
    } else {
        const steps = Math.max(0, Number(input.totalSteps) || 0);
        if (steps > 0) {
            durationMs = steps * ASSUMED_MS_PER_STEP;
            durationSource = 'heuristic';
        }
    }

    const matchedRunId =
        wallPool.topRunId ?? subjectPool.topRunId ?? judgePool.topRunId ?? null;

    // Prefer duration scale for UI when both present; else cost.
    const scale =
        durationSource === 'history' || durationSource === 'history_scaled'
            ? durationScale
            : costScale;

    return {
        costUsd,
        costSource,
        durationMs,
        durationSource,
        matchedRunId,
        scale,
        labels: {
            cost: sourceLabel(costSource),
            duration: sourceLabel(durationSource),
        },
    };
}

export function formatPreRunCost(costUsd: number | null): string {
    if (costUsd === null || !Number.isFinite(costUsd)) return '—';
    if (costUsd < 0.01) return `$${costUsd.toFixed(4)}`;
    return `$${costUsd.toFixed(2)}`;
}
