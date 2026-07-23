import assert from 'node:assert/strict';
import test from 'node:test';
import type { EvaluationRun } from '../types/index.ts';
import {
    computeTimeRoi,
    formatTimeRoi,
    resolveTimeRoiDenominator,
    resolveTimingSummary,
    runProcessingDurationMs,
    runScoreSum,
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

test('AC-002 CostSection and Dashboard share Σscore / processing-minutes denominator', () => {
    const run = baseRun({
        executionDurationMs: 20_000,
        taskCount: 2,
        averageScore: 80,
        timingSummary: {
            subjectDurationMs: 1500,
            judgeDurationMs: 3500,
            totalDurationMs: 5000,
        },
    });

    const detail = resolveTimeRoiDenominator(resolveTimingSummary(run), 'total');
    assert.equal(detail.ms, 5000);
    assert.equal(detail.label, '総時間');
    // Σscore = 80 * 2 = 160; minutes = 5000/60000; ROI = 160 / (1/12) = 1920 点/分
    assert.equal(runScoreSum(run), 160);
    assert.equal(computeTimeRoi(runScoreSum(run), detail.ms), 1920);
    assert.equal(formatTimeRoi(runScoreSum(run), runProcessingDurationMs(run)), '1920 点/分');
    // parallel wall-clock is larger than processing total — must not be used
    assert.ok((run.executionDurationMs ?? 0) > (detail.ms ?? 0));
});

test('AC-003 missing timing yields N/A without wall-clock fallback', () => {
    const legacy = baseRun({
        executionDurationMs: 12_345,
        averageScore: 90,
        taskCount: 3,
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
    assert.equal(computeTimeRoi(runScoreSum(legacy), denom.ms), undefined);
    assert.equal(formatTimeRoi(runScoreSum(legacy), runProcessingDurationMs(legacy)), 'N/A');
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

test('DEC-005 multi-task run does not shrink ROI vs single-task same efficiency', () => {
    // Each task: score 80 in 60s → 80 点/分 whether 1 or 11 tasks
    const one = baseRun({
        averageScore: 80,
        taskCount: 1,
        timingSummary: {
            subjectDurationMs: 20_000,
            judgeDurationMs: 40_000,
            totalDurationMs: 60_000,
        },
    });
    const many = baseRun({
        averageScore: 80,
        taskCount: 11,
        timingSummary: {
            subjectDurationMs: 220_000,
            judgeDurationMs: 440_000,
            totalDurationMs: 660_000,
        },
    });
    assert.equal(
        computeTimeRoi(runScoreSum(one), runProcessingDurationMs(one)),
        80,
    );
    assert.equal(
        computeTimeRoi(runScoreSum(many), runProcessingDurationMs(many)),
        80,
    );
});

test('latest-run scale: Σscore/Σtime yields readable 点/分 (not collapsed to 0)', () => {
    // Mirrors 20260724_014205: avg 40.9, n=11, total ~3039314ms → ~8.9 点/分
    const run = baseRun({
        averageScore: 40.9,
        taskCount: 11,
        timingSummary: {
            subjectDurationMs: 640960,
            judgeDurationMs: 2398354,
            totalDurationMs: 3039314,
        },
    });
    const roi = computeTimeRoi(runScoreSum(run), runProcessingDurationMs(run));
    assert.equal(roi, 8.9);
    assert.equal(formatTimeRoi(runScoreSum(run), runProcessingDurationMs(run)), '8.9 点/分');
});
