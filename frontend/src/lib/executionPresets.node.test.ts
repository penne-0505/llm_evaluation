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
        holisticJudgeModelIds: [],
        freeTextHolisticJudges: [],
        tasks,
        selectedTaskIds: ['02'],
        runHolistic: false,
        excludeUnreliableJudges: false,
        judgeRunCount: 4,
        subjectRunCount: 1,
        subjectTemperature: 0.35,
    });

    assert.deepEqual(config.taskSelections, { '01': false, '02': true });
    assert.equal(config.subjectModel, 'openrouter/subject');
    assert.deepEqual(config.judgeModels, ['openrouter/judge-a']);
    assert.deepEqual(config.holisticJudgeModels, []);
    assert.equal(config.runHolistic, false);
    assert.equal(config.excludeUnreliableJudges, false);
    assert.equal(config.judgeRunCount, 4);
    assert.equal(config.subjectRunCount, 1);
    assert.equal(config.subjectTemperature, 0.35);
});

test('resolveExecutionPresetConfig clamps subjectRunCount and defaults legacy presets', () => {
    const clamped = resolveExecutionPresetConfig(
        {
            subjectModel: 'openrouter/subject',
            judgeModels: ['openrouter/judge-a'],
            holisticJudgeModels: [],
            taskSelections: { '01': true },
            runHolistic: false,
            excludeUnreliableJudges: false,
            judgeRunCount: 2,
            subjectRunCount: 99,
            subjectTemperature: 0.5,
        },
        models,
        tasks,
    );
    assert.equal(clamped.subjectRunCount, 5);

    const legacy = resolveExecutionPresetConfig(
        {
            subjectModel: 'openrouter/subject',
            judgeModels: ['openrouter/judge-a'],
            taskSelections: { '01': true },
            runHolistic: false,
            judgeRunCount: 2,
            subjectTemperature: 0.5,
        } as unknown as Parameters<typeof resolveExecutionPresetConfig>[0],
        models,
        tasks,
    );
    assert.equal(legacy.subjectRunCount, 1);
    assert.equal(legacy.excludeUnreliableJudges, false);
});

test('resolveExecutionPresetConfig silently filters unavailable models and tasks', () => {
    const resolved = resolveExecutionPresetConfig(
        {
            subjectModel: 'openrouter/missing-subject',
            judgeModels: ['openrouter/judge-a', 'openrouter/missing-judge'],
            holisticJudgeModels: ['openrouter/missing-holistic'],
            taskSelections: { '01': true, '02': false, '99': true },
            runHolistic: true,
            excludeUnreliableJudges: false,
            judgeRunCount: 8,
            subjectRunCount: 1,
            subjectTemperature: -0.5,
        },
        models,
        tasks,
    );

    assert.equal(resolved.subjectModelId, null);
    assert.deepEqual(resolved.judgeModelIds, ['openrouter/judge-a']);
    assert.deepEqual(resolved.holisticJudgeModelIds, []);
    assert.equal(resolved.freeTextSubject, '');
    assert.deepEqual(resolved.freeTextJudges, []);
    assert.deepEqual(resolved.selectedTaskIds, ['01']);
    assert.deepEqual(resolved.missingModelIds, [
        'openrouter/missing-subject',
        'openrouter/missing-judge',
        'openrouter/missing-holistic',
    ]);
    assert.deepEqual(resolved.missingTaskIds, ['99']);
    assert.equal(resolved.judgeRunCount, 5);
    assert.equal(resolved.subjectTemperature, 0);
});

test('resolveExecutionPresetConfig restores selected tasks in the available task order', () => {
    const availableTasks: Task[] = [
        { id: '02', type: 'creative', promptPreview: 'task 02' },
        { id: '04', type: 'fact', promptPreview: 'task 04' },
        { id: '10', type: 'speculative', promptPreview: 'task 10' },
        { id: '11', type: 'fact', promptPreview: 'task 11' },
    ];

    const resolved = resolveExecutionPresetConfig(
        {
            subjectModel: null,
            judgeModels: [],
            holisticJudgeModels: [],
            taskSelections: {
                '02': true,
                '04': true,
                '10': true,
                '11': true,
                '99': true,
            },
            runHolistic: false,
            excludeUnreliableJudges: false,
            judgeRunCount: 1,
            subjectRunCount: 1,
            subjectTemperature: 0,
        },
        models,
        availableTasks,
    );

    assert.deepEqual(resolved.selectedTaskIds, ['02', '04', '10', '11']);
    assert.deepEqual(resolved.missingTaskIds, ['99']);
});

test('capture and resolve preserve manual models when the catalog is unavailable', () => {
    const config = captureExecutionPresetConfig({
        subjectModelId: null,
        judgeModelIds: [],
        freeTextSubject: 'lmstudio/manual-subject',
        freeTextJudges: ['lmstudio/manual-judge'],
        holisticJudgeModelIds: [],
        freeTextHolisticJudges: ['lmstudio/manual-holistic'],
        tasks,
        selectedTaskIds: ['01'],
        runHolistic: true,
        excludeUnreliableJudges: false,
        judgeRunCount: 2,
        subjectRunCount: 1,
        subjectTemperature: 0.6,
    });
    const resolved = resolveExecutionPresetConfig(config, [], tasks);

    assert.equal(resolved.subjectModelId, null);
    assert.deepEqual(resolved.judgeModelIds, []);
    assert.equal(resolved.freeTextSubject, 'lmstudio/manual-subject');
    assert.deepEqual(resolved.freeTextJudges, ['lmstudio/manual-judge']);
    assert.deepEqual(resolved.freeTextHolisticJudges, ['lmstudio/manual-holistic']);
    assert.deepEqual(resolved.missingModelIds, []);
});

test('capture and resolve round-trip holisticJudgeModels including empty fallback', () => {
    const modelsWithHolistic: Model[] = [
        ...models,
        { id: 'openrouter/holistic-judge', name: 'Holistic Judge', provider: 'openrouter' },
    ];

    const withOverride = captureExecutionPresetConfig({
        subjectModelId: 'openrouter/subject',
        judgeModelIds: ['openrouter/judge-a'],
        freeTextSubject: '',
        freeTextJudges: [],
        holisticJudgeModelIds: ['openrouter/holistic-judge'],
        freeTextHolisticJudges: [],
        tasks,
        selectedTaskIds: ['01'],
        runHolistic: true,
        excludeUnreliableJudges: false,
        judgeRunCount: 3,
        subjectRunCount: 1,
        subjectTemperature: 0.6,
    });
    assert.deepEqual(withOverride.holisticJudgeModels, ['openrouter/holistic-judge']);

    const resolvedOverride = resolveExecutionPresetConfig(
        withOverride,
        modelsWithHolistic,
        tasks,
    );
    assert.deepEqual(resolvedOverride.holisticJudgeModelIds, ['openrouter/holistic-judge']);

    const legacyWithoutField = resolveExecutionPresetConfig(
        {
            subjectModel: 'openrouter/subject',
            judgeModels: ['openrouter/judge-a'],
            taskSelections: { '01': true, '02': false },
            runHolistic: true,
            excludeUnreliableJudges: false,
            judgeRunCount: 3,
            subjectRunCount: 1,
            subjectTemperature: 0.6,
        } as unknown as Parameters<typeof resolveExecutionPresetConfig>[0],
        modelsWithHolistic,
        tasks,
    );
    assert.deepEqual(legacyWithoutField.holisticJudgeModelIds, []);
});
