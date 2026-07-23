import assert from 'node:assert/strict';
import test from 'node:test';
import type { EvaluationRun } from '../types/index.ts';
import {
    computeTimeRoi,
    formatTimeRoi,
    resolveTimeRoiDenominator,
    resolveTimingSummary,
    runProcessingDurationMs,
    sumTaskTimings,
} from './timeRoi.ts';

function baseRun(overrides: Partial<EvaluationRun> = {}): EvaluationRun {
    return {
        id: 'run-1',
        subjectModelId: 'model-a',
        subjectModelName: 'Model A',
        judgeModels: [],
        timestamp: '2026-07-23T00:00:00Z',
        averageScore: 80,
        bestScore: 80,
        taskCount: 1,
        taskResults: [],
        holisticTaskResults: [],
        ...overrides,
    };
}

test('sumTaskTimings aggregates subject+judge and rejects partial legacy tasks', () => {
    assert.deepEqual(
        sumTaskTimings([
            { taskTiming: { subjectDurationMs: 1000, judgeDurationMs: 2000 } },
            { taskTiming: { subjectDurationMs: 500, judgeDurationMs: 1500 } },
        ]),
        { subjectDurationMs: 1500, judgeDurationMs: 3500, totalDurationMs: 5000 },
    );
    assert.equal(
        sumTaskTimings([
            { taskTiming: { subjectDurationMs: 1000, judgeDurationMs: 2000 } },
            {},
        ]),
        undefined,
    );
});

test('AC-002 CostSection and Dashboard share subject+judge denominator', () => {
    const run = baseRun({
        executionDurationMs: 20_000,
        timingSummary: {
            subjectDurationMs: 1500,
            judgeDurationMs: 3500,
            totalDurationMs: 5000,
        },
        averageScore: 80,
    });

    const detail = resolveTimeRoiDenominator(resolveTimingSummary(run), 'total');
    assert.equal(detail.ms, 5000);
    assert.equal(detail.label, '総時間');
    assert.equal(computeTimeRoi(run.averageScore, detail.ms), 16);
    assert.equal(formatTimeRoi(run.averageScore, runProcessingDurationMs(run)), '16 点/秒');
    // parallel wall-clock is larger than processing total — must not be used
    assert.ok((run.executionDurationMs ?? 0) > (detail.ms ?? 0));
});

test('AC-003 missing timing yields N/A without wall-clock fallback', () => {
    const legacy = baseRun({
        executionDurationMs: 12_345,
        averageScore: 90,
        taskResults: [{
            taskId: '01',
            taskType: 'fact',
            inputPrompt: '',
            subjectPrompt: '',
            subjectResponse: '',
            subjectUsage: null,
            judgeEvaluations: [],
            toolTrace: [],
            hasSubjectTools: false,
        }],
    });

    assert.equal(resolveTimingSummary(legacy), undefined);
    assert.equal(runProcessingDurationMs(legacy), undefined);
    const denom = resolveTimeRoiDenominator(undefined, 'total');
    assert.equal(denom.available, false);
    assert.equal(computeTimeRoi(legacy.averageScore, denom.ms), undefined);
    assert.equal(formatTimeRoi(legacy.averageScore, runProcessingDurationMs(legacy)), 'N/A');
});

test('DEC-004 subject/judge tabs use timing breakdown only', () => {
    const summary = {
        subjectDurationMs: 2000,
        judgeDurationMs: 3000,
        totalDurationMs: 5000,
    };
    assert.deepEqual(resolveTimeRoiDenominator(summary, 'subject'), {
        ms: 2000,
        label: '被検時間',
        available: true,
    });
    assert.deepEqual(resolveTimeRoiDenominator(summary, 'judge'), {
        ms: 3000,
        label: 'Judge時間',
        available: true,
    });
});
