/**
 * Dashboard model leaderboard aggregation.
 *
 * intent: DEC-004 (Core/exclude-unreliable-judges) — null hero stays null in
 * aggregates; never coerce empty score sets to 0 (INV-001).
 */

import type { EvaluationRun } from '../types';
import { isHeroScoreAvailable } from './judgeReliability';
import { mean, stddev } from './stats';
import { runProcessingDurationMs } from './timeRoi';

const UNCLASSIFIED_PRESET_ID = '__unclassified__';

export type ModelAggregate = {
    id: string;
    name: string;
    shortName: string;
    avgScore: number | null;
    bestScore: number | null;
    variability: number;
    runCount: number;
    latest: string;
    avgCostPer1m?: number;
    avgExecutionTimeMs?: number;
    /** Dominant preset among this model's runs (for color when filter is OFF). */
    dominantPresetId: string;
};

function getRunPresetId(run: EvaluationRun): string {
    return run.strictMode?.presetId || UNCLASSIFIED_PRESET_ID;
}

function dominantPresetId(runs: EvaluationRun[]): string {
    const counts = new Map<string, number>();
    runs.forEach((run) => {
        const id = getRunPresetId(run);
        counts.set(id, (counts.get(id) || 0) + 1);
    });
    let best = UNCLASSIFIED_PRESET_ID;
    let bestCount = -1;
    counts.forEach((count, id) => {
        if (count > bestCount) {
            best = id;
            bestCount = count;
        }
    });
    return best;
}

function sortKey(avgScore: number | null): number {
    return isHeroScoreAvailable(avgScore) ? avgScore : Number.NEGATIVE_INFINITY;
}

export function buildModelAggregates(runs: EvaluationRun[]): ModelAggregate[] {
    const map = new Map<
        string,
        {
            name: string;
            scores: number[];
            best: number | null;
            latest: string;
            costPer1m: number[];
            executionTimes: number[];
            runs: EvaluationRun[];
        }
    >();

    runs.forEach((run) => {
        const entry = map.get(run.subjectModelId) || {
            name: run.subjectModelName,
            scores: [],
            best: null as number | null,
            latest: '',
            costPer1m: [],
            executionTimes: [],
            runs: [],
        };
        if (isHeroScoreAvailable(run.averageScore)) {
            entry.scores.push(run.averageScore);
        }
        if (isHeroScoreAvailable(run.bestScore)) {
            entry.best =
                entry.best === null
                    ? run.bestScore
                    : Math.max(entry.best, run.bestScore);
        }
        if (!entry.latest || run.timestamp > entry.latest) {
            entry.latest = run.timestamp;
        }
        if (typeof run.subjectCostPer1mTokensUsd === 'number') {
            entry.costPer1m.push(run.subjectCostPer1mTokensUsd);
        }
        // intent: DEC-004 (Core/time-roi-task-timing) — wall-clock ではなく処理時間合算
        const processingMs = runProcessingDurationMs(run);
        if (typeof processingMs === 'number' && processingMs > 0) {
            entry.executionTimes.push(processingMs);
        }
        entry.runs.push(run);
        map.set(run.subjectModelId, entry);
    });

    return Array.from(map.entries())
        .map(([id, entry]) => ({
            id,
            name: entry.name,
            shortName:
                entry.name.length > 16
                    ? `${entry.name.slice(0, 14)}…`
                    : entry.name,
            // intent: DEC-004 (Core/exclude-unreliable-judges) — empty → null, never 0
            avgScore:
                entry.scores.length > 0
                    ? Math.round(mean(entry.scores) * 10) / 10
                    : null,
            bestScore: entry.best,
            variability:
                entry.scores.length > 1
                    ? Math.round(stddev(entry.scores) * 10) / 10
                    : 0,
            runCount: entry.runs.length,
            latest: entry.latest,
            avgCostPer1m:
                entry.costPer1m.length > 0
                    ? Number(mean(entry.costPer1m).toFixed(6))
                    : undefined,
            avgExecutionTimeMs:
                entry.executionTimes.length > 0
                    ? Number(mean(entry.executionTimes).toFixed(0))
                    : undefined,
            dominantPresetId: dominantPresetId(entry.runs),
        }))
        .sort((a, b) => sortKey(b.avgScore) - sortKey(a.avgScore));
}
