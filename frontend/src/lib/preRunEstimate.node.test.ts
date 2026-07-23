import assert from 'node:assert/strict';
import test from 'node:test';
import type { EvaluationRun } from '../types/index.ts';
import {
    ASSUMED_MS_PER_STEP,
    computePreRunEstimate,
    formatPreRunCost,
    historicalLoad,
    pickBestHistoricalRun,
    plannedLoad,
} from './preRunEstimate.ts';

function run(overrides: Partial<EvaluationRun> = {}): EvaluationRun {
    return {
        id: 'run-a',
        subjectModelId: 'model-a',
        subjectModelName: 'Model A',
        judgeModels: [],
        timestamp: '2026-07-20T00:00:00Z',
        averageScore: 50,
        bestScore: 50,
        taskCount: 11,
        judgeCount: 3,
        taskResults: [],
        holisticTaskResults: [],
        executionDurationMs: 1_200_000,
        estimatedCostUsd: 2.0,
        ...overrides,
    };
}

const baseInput = {
    subjectModelId: 'model-a',
    taskCount: 11,
    judgeCount: 3,
    subjectRunCount: 1,
    judgeRunCount: 1,
    totalSteps: 100,
};

test('plannedLoad and historicalLoad use DEC-003 formulas', () => {
    assert.equal(plannedLoad({ taskCount: 10, judgeCount: 2, subjectRunCount: 1, judgeRunCount: 1 }), 30);
    assert.equal(historicalLoad(10, 2), 30);
    assert.equal(plannedLoad({ taskCount: 10, judgeCount: 2, subjectRunCount: 2, judgeRunCount: 3 }), 80);
});

test('AC-001 history match returns unscaled estimate for identical shape', () => {
    const estimate = computePreRunEstimate([run()], baseInput);
    assert.equal(estimate.matchedRunId, 'run-a');
    assert.equal(estimate.costSource, 'history');
    assert.equal(estimate.durationSource, 'history');
    assert.equal(estimate.costUsd, 2);
    assert.equal(estimate.durationMs, 1_200_000);
    assert.equal(estimate.labels.cost, '履歴');
});

test('AC-001 prefers closer task/judge shape then newer timestamp', () => {
    const olderClose = run({
        id: 'older',
        timestamp: '2026-07-01T00:00:00Z',
        taskCount: 11,
        judgeCount: 3,
    });
    const newerFar = run({
        id: 'newer-far',
        timestamp: '2026-07-23T00:00:00Z',
        taskCount: 2,
        judgeCount: 1,
        estimatedCostUsd: 9,
    });
    const picked = pickBestHistoricalRun([newerFar, olderClose], baseInput);
    assert.equal(picked?.id, 'older');
});

test('AC-002 scales when task count differs', () => {
    const estimate = computePreRunEstimate([run()], {
        ...baseInput,
        taskCount: 22,
    });
    assert.equal(estimate.costSource, 'history_scaled');
    assert.equal(estimate.durationSource, 'history_scaled');
    assert.equal(estimate.scale, 2);
    assert.equal(estimate.costUsd, 4);
    assert.equal(estimate.durationMs, 2_400_000);
    assert.equal(estimate.labels.duration, '履歴+構成補正');
});

test('AC-002 scales when judgeRunCount > 1 even if counts match', () => {
    const estimate = computePreRunEstimate([run()], {
        ...baseInput,
        judgeRunCount: 2,
    });
    assert.equal(estimate.costSource, 'history_scaled');
    // L_plan = 11*(1+3*2)=77; L_hist=11*(1+3)=44; scale=77/44
    assert.ok(Math.abs(estimate.scale - 77 / 44) < 1e-9);
});

test('AC-003 / INV-001 no history → heuristic duration, null cost (not 0)', () => {
    const estimate = computePreRunEstimate([], {
        ...baseInput,
        subjectModelId: 'brand-new',
        totalSteps: 10,
    });
    assert.equal(estimate.matchedRunId, null);
    assert.equal(estimate.costUsd, null);
    assert.equal(estimate.costSource, 'unavailable');
    assert.equal(estimate.durationMs, 10 * ASSUMED_MS_PER_STEP);
    assert.equal(estimate.durationSource, 'heuristic');
    assert.equal(formatPreRunCost(estimate.costUsd), '—');
    assert.notEqual(estimate.costUsd, 0);
});

test('other subject models are ignored', () => {
    const estimate = computePreRunEstimate(
        [run({ subjectModelId: 'other', estimatedCostUsd: 99 })],
        baseInput,
    );
    assert.equal(estimate.costSource, 'unavailable');
    assert.equal(estimate.durationSource, 'heuristic');
});

test('missing historical cost stays unavailable even when duration scales', () => {
    const estimate = computePreRunEstimate(
        [run({ estimatedCostUsd: undefined, executionDurationMs: 600_000 })],
        { ...baseInput, taskCount: 22 },
    );
    assert.equal(estimate.costUsd, null);
    assert.equal(estimate.costSource, 'unavailable');
    assert.equal(estimate.durationSource, 'history_scaled');
    assert.equal(estimate.durationMs, 1_200_000);
});
