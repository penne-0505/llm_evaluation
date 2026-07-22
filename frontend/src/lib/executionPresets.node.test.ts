import test from 'node:test';
import assert from 'node:assert/strict';

import {
    captureExecutionPresetConfig,
    resolveExecutionPresetConfig,
} from './executionPresets.ts';
import type { Model, Task } from '../types/index.ts';

const models: Model[] = [
    { id: 'openrouter/subject', name: 'Subject', provider: 'openrouter' },
    { id: 'openrouter/judge-a', name: 'Judge A', provider: 'openrouter' },
];

const tasks: Task[] = [
    { id: '01', type: 'fact', promptPreview: 'task 01' },
    { id: '02', type: 'creative', promptPreview: 'task 02' },
];

test('captureExecutionPresetConfig stores every task as a boolean selection', () => {
    const config = captureExecutionPresetConfig({
        subjectModelId: 'openrouter/subject',
        judgeModelIds: ['openrouter/judge-a'],
        freeTextSubject: '',
        freeTextJudges: [],
        tasks,
        selectedTaskIds: ['02'],
        runHolistic: false,
        judgeRunCount: 4,
        subjectTemperature: 0.35,
    });

    assert.deepEqual(config.taskSelections, { '01': false, '02': true });
    assert.equal(config.subjectModel, 'openrouter/subject');
    assert.deepEqual(config.judgeModels, ['openrouter/judge-a']);
    assert.equal(config.runHolistic, false);
    assert.equal(config.judgeRunCount, 4);
    assert.equal(config.subjectTemperature, 0.35);
});

test('resolveExecutionPresetConfig silently filters unavailable models and tasks', () => {
    const resolved = resolveExecutionPresetConfig(
        {
            subjectModel: 'openrouter/missing-subject',
            judgeModels: ['openrouter/judge-a', 'openrouter/missing-judge'],
            taskSelections: { '01': true, '02': false, '99': true },
            runHolistic: true,
            judgeRunCount: 8,
            subjectTemperature: -0.5,
        },
        models,
        tasks,
    );

    assert.equal(resolved.subjectModelId, null);
    assert.deepEqual(resolved.judgeModelIds, ['openrouter/judge-a']);
    assert.equal(resolved.freeTextSubject, '');
    assert.deepEqual(resolved.freeTextJudges, []);
    assert.deepEqual(resolved.selectedTaskIds, ['01']);
    assert.deepEqual(resolved.missingModelIds, [
        'openrouter/missing-subject',
        'openrouter/missing-judge',
    ]);
    assert.deepEqual(resolved.missingTaskIds, ['99']);
    assert.equal(resolved.judgeRunCount, 5);
    assert.equal(resolved.subjectTemperature, 0);
});

test('capture and resolve preserve manual models when the catalog is unavailable', () => {
    const config = captureExecutionPresetConfig({
        subjectModelId: null,
        judgeModelIds: [],
        freeTextSubject: 'lmstudio/manual-subject',
        freeTextJudges: ['lmstudio/manual-judge'],
        tasks,
        selectedTaskIds: ['01'],
        runHolistic: true,
        judgeRunCount: 2,
        subjectTemperature: 0.6,
    });
    const resolved = resolveExecutionPresetConfig(config, [], tasks);

    assert.equal(resolved.subjectModelId, null);
    assert.deepEqual(resolved.judgeModelIds, []);
    assert.equal(resolved.freeTextSubject, 'lmstudio/manual-subject');
    assert.deepEqual(resolved.freeTextJudges, ['lmstudio/manual-judge']);
    assert.deepEqual(resolved.missingModelIds, []);
});
