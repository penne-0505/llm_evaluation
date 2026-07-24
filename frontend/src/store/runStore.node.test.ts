import test from 'node:test';
import assert from 'node:assert/strict';

import { useRunStore, MAX_CONCURRENT_JOBS } from './runStore.ts';
import type { EvaluationRun } from '../types/index.ts';

const completedRun: EvaluationRun = {
    id: 'run_clear_result_test',
    subjectModelId: 'subject-model',
    subjectModelName: 'Subject Model',
    judgeModels: [{ id: 'judge-model', name: 'Judge Model' }],
    timestamp: '2026-06-03T00:00:00Z',
    taskResults: [],
    holisticTaskResults: [],
    averageScore: 80,
    bestScore: 85,
    taskCount: 0,
};

test('clearResult resets a completed run back to the runnable idle state', () => {
    const store = useRunStore.getState();
    store.reset();
    store.startRun(1);
    useRunStore.getState().setRunId('run_clear_result_test');
    useRunStore.getState().completeRun(completedRun, '/tmp/result.json');

    useRunStore.getState().clearResult();

    const state = useRunStore.getState();
    assert.equal(state.status, 'idle');
    assert.equal(state.result, null);
    assert.equal(state.resultFilePath, null);
    assert.equal(state.progress, null);
    assert.equal(state.runId, null);
    assert.equal(state.cancelRequested, false);
    assert.equal(state.errorMessage, null);
});

test('holistic progress is kept separately from standard task progress', () => {
    const store = useRunStore.getState();
    store.reset();
    store.startRun(4);
    useRunStore.getState().updateProgress({
        completedTaskCount: 2,
        activeTaskCount: 0,
        queuedTaskCount: 0,
    });
    useRunStore.getState().updateHolisticProgress({
        status: 'running',
        completedTaskCount: 0,
        failedTaskCount: 0,
        totalTaskCount: 1,
        currentTaskIndex: 0,
        currentTaskId: 'style',
        message: '包括評価 1/1: 実行中',
    });

    const state = useRunStore.getState();
    assert.equal(state.progress?.completedTaskCount, 2);
    assert.deepEqual(state.holisticProgress, {
        status: 'running',
        completedTaskCount: 0,
        failedTaskCount: 0,
        totalTaskCount: 1,
        currentTaskIndex: 0,
        currentTaskId: 'style',
        message: '包括評価 1/1: 実行中',
    });
});

test('allows up to MAX_CONCURRENT_JOBS running jobs and rejects more', () => {
    const store = useRunStore.getState();
    store.resetAll();
    for (let i = 0; i < MAX_CONCURRENT_JOBS; i += 1) {
        store.startJob(`job_${i}`, `model_${i}`, 10);
    }
    assert.equal(store.runningCount(), MAX_CONCURRENT_JOBS);
    assert.equal(store.canStartAnother(), false);
    store.startJob('job_overflow', 'model_x', 10);
    assert.equal(useRunStore.getState().jobs.length, MAX_CONCURRENT_JOBS);
    useRunStore.getState().completeJob('job_0', completedRun);
    assert.equal(useRunStore.getState().runningCount(), MAX_CONCURRENT_JOBS - 1);
    assert.equal(useRunStore.getState().canStartAnother(), true);
});
