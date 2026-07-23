import test from 'node:test';
import assert from 'node:assert/strict';

import {
    createExecutionPreset,
    overwriteExecutionPresetConfig,
} from '../lib/executionPresets.ts';

const initialConfig = {
    subjectModel: 'openrouter/subject',
    judgeModels: ['openrouter/judge'],
    holisticJudgeModels: [],
    taskSelections: { '01': true, '02': false },
    runHolistic: false,
    judgeRunCount: 4,
    subjectTemperature: 0.25,
};

test('createExecutionPreset assigns identity, timestamps, and schema version', () => {
    const preset = createExecutionPreset(
        'preset-1',
        'Smoke',
        '2026-07-22T00:00:00Z',
        initialConfig,
    );

    assert.equal(preset.id, 'preset-1');
    assert.equal(preset.name, 'Smoke');
    assert.equal(preset.schemaVersion, 1);
    assert.equal(preset.createdAt, '2026-07-22T00:00:00Z');
    assert.equal(preset.updatedAt, '2026-07-22T00:00:00Z');
    assert.deepEqual(preset.config, initialConfig);
});

test('overwriteExecutionPresetConfig preserves identity and replaces the snapshot', () => {
    const preset = createExecutionPreset(
        'preset-1',
        'Smoke',
        '2026-07-22T00:00:00Z',
        initialConfig,
    );
    const nextConfig = {
        ...initialConfig,
        taskSelections: { '01': false, '02': true },
        runHolistic: true,
    };

    const updated = overwriteExecutionPresetConfig(
        preset,
        nextConfig,
        '2026-07-22T01:00:00Z',
    );

    assert.equal(updated.id, preset.id);
    assert.equal(updated.name, preset.name);
    assert.equal(updated.createdAt, preset.createdAt);
    assert.equal(updated.updatedAt, '2026-07-22T01:00:00Z');
    assert.deepEqual(updated.config, nextConfig);
});
