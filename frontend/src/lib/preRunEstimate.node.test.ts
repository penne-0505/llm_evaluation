import assert from 'node:assert/strict';
import test from 'node:test';
import type { EvaluationRun } from '../types/index.ts';
import {
    ASSUMED_MS_PER_STEP,
    WEIGHT_BETA,
    WEIGHT_GAMMA,
    channelWeight,
    computePreRunEstimate,
    formatPreRunCost,
    historicalLoad,
    plannedLoad,
    subjectGate,
} from './preRunEstimate.ts';

const NOW = Date.parse('2026-07-24T00:00:00Z');

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
        subjectEstimatedCostUsd: 1.5,
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
    nowMs: NOW,
};

test('plannedLoad and historicalLoad formulas', () => {
    assert.equal(plannedLoad({ taskCount: 10, judgeCount: 2, subjectRunCount: 1, judgeRunCount: 1 }), 30);
    assert.equal(historicalLoad(10, 2), 30);
    assert.equal(plannedLoad({ taskCount: 10, judgeCount: 2, subjectRunCount: 2, judgeRunCount: 3 }), 80);
});

test('INV-002 subjectGate zeroes subject_cost on mismatch', () => {
    assert.equal(subjectGate('subject_cost', false), 0);
    assert.equal(subjectGate('subject_cost', true), 1);
    assert.equal(subjectGate('judge_cost', false), WEIGHT_BETA);
    assert.equal(subjectGate('wall', false), WEIGHT_GAMMA);
});

test('AC-001 identical single history returns unscaled estimate', () => {
    const estimate = computePreRunEstimate([run()], baseInput);
    assert.equal(estimate.matchedRunId, 'run-a');
    assert.equal(estimate.costSource, 'history');
    assert.equal(estimate.durationSource, 'history');
    // subject 1.5 + judge 0.5 = 2.0 at L=44
    assert.ok(Math.abs((estimate.costUsd ?? 0) - 2) < 1e-9);
    assert.equal(estimate.durationMs, 1_200_000);
    assert.equal(estimate.labels.cost, '履歴');
});

test('AC-001 closer run outweighs farther run of same subject', () => {
    const close = run({
        id: 'close',
        timestamp: '2026-07-20T00:00:00Z',
        taskCount: 11,
        judgeCount: 3,
        estimatedCostUsd: 2.0,
        subjectEstimatedCostUsd: 2.0,
        executionDurationMs: 1_000_000,
    });
    const far = run({
        id: 'far',
        timestamp: '2026-07-20T00:00:00Z',
        taskCount: 2,
        judgeCount: 1,
        estimatedCostUsd: 100,
        subjectEstimatedCostUsd: 100,
        executionDurationMs: 9_000_000,
    });
    const estimate = computePreRunEstimate([close, far], baseInput);
    const wClose = channelWeight('subject_cost', true, 0, 4);
    const wFar = channelWeight('subject_cost', true, 13, 4);
    assert.ok(wClose > wFar * 10);
    const farOnly = computePreRunEstimate([far], baseInput);
    // Pooled estimate must stay far closer to the near run than to the distant outlier alone.
    assert.ok((estimate.costUsd ?? 0) < (farOnly.costUsd ?? 0) * 0.1);
    assert.ok((estimate.costUsd ?? 0) > 1);
    assert.equal(estimate.matchedRunId, 'close');
});

test('AC-002 scales when task count differs', () => {
    const estimate = computePreRunEstimate([run()], {
        ...baseInput,
        taskCount: 22,
    });
    assert.equal(estimate.costSource, 'history_scaled');
    assert.equal(estimate.durationSource, 'history_scaled');
    assert.ok(Math.abs(estimate.scale - 2) < 1e-9);
    assert.ok(Math.abs((estimate.costUsd ?? 0) - 4) < 1e-9);
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

test('AC-006 other-subject only: subject cost excluded, wall may use thin γ', () => {
    const other = run({
        id: 'other',
        subjectModelId: 'other-model',
        estimatedCostUsd: 99,
        subjectEstimatedCostUsd: 80,
        executionDurationMs: 600_000,
    });
    const estimate = computePreRunEstimate([other], baseInput);
    // judge_cost = 19 may contribute with β; subject 80 must not
    assert.notEqual(estimate.costUsd, 99);
    if (estimate.costUsd != null) {
        // Only judge portion scaled: rate 19/44 * L_plan(44) = 19 * β-weighted → still 19 if only one sample
        assert.ok(Math.abs(estimate.costUsd - 19) < 1e-6);
    }
    assert.equal(estimate.durationSource, 'history');
    assert.ok(Math.abs((estimate.durationMs ?? 0) - 600_000) < 1e-6);
    assert.ok(channelWeight('wall', false, 0, 4) > 0);
    assert.equal(channelWeight('subject_cost', false, 0, 4), 0);
});

test('AC-007 mixed subjects: subject cost from match only; wall includes thin cross', () => {
    const same = run({
        id: 'same',
        subjectEstimatedCostUsd: 1.0,
        estimatedCostUsd: 1.2,
        executionDurationMs: 1_000_000,
        timestamp: '2026-07-22T00:00:00Z',
    });
    const other = run({
        id: 'other',
        subjectModelId: 'other-model',
        subjectEstimatedCostUsd: 50,
        estimatedCostUsd: 60,
        executionDurationMs: 2_000_000,
        timestamp: '2026-07-22T00:00:00Z',
    });
    const estimate = computePreRunEstimate([same, other], baseInput);
    // Subject cost pool: only same (1.0). Judge: same 0.2 + other 10 with β.
    assert.ok((estimate.costUsd ?? 0) < 20);
    assert.ok((estimate.costUsd ?? 0) > 1.0);
    // Duration: both contribute; same weight 1, other γ=0.1 → between 1e6 and 2e6
    assert.ok((estimate.durationMs ?? 0) > 1_000_000);
    assert.ok((estimate.durationMs ?? 0) < 2_000_000);
});

test('legacy total-only cost on same subject still estimates', () => {
    const estimate = computePreRunEstimate(
        [run({ estimatedCostUsd: 2.0, subjectEstimatedCostUsd: undefined })],
        baseInput,
    );
    assert.ok(Math.abs((estimate.costUsd ?? 0) - 2) < 1e-9);
    assert.equal(estimate.costSource, 'history');
});

test('missing historical cost stays unavailable even when duration scales', () => {
    const estimate = computePreRunEstimate(
        [
            run({
                estimatedCostUsd: undefined,
                subjectEstimatedCostUsd: undefined,
                executionDurationMs: 600_000,
            }),
        ],
        { ...baseInput, taskCount: 22 },
    );
    assert.equal(estimate.costUsd, null);
    assert.equal(estimate.costSource, 'unavailable');
    assert.equal(estimate.durationSource, 'history_scaled');
    assert.equal(estimate.durationMs, 1_200_000);
});
