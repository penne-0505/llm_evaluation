import test from 'node:test';
import assert from 'node:assert/strict';

import {
    createExecutionPreset,
    overwriteExecutionPresetConfig,
} from '../lib/executionPresets.ts';
import { useSettingsStore } from './settingsStore.ts';

const initialConfig = {
    judgeModels: ['openrouter/judge'],
    holisticJudgeModels: [],
    taskSelections: { '01': true, '02': false },
    runHolistic: false,
    judgeRunCount: 4,
    subjectTemperature: 0.25,
};

test('AC-001 createExecutionPreset assigns identity, timestamps, and schema v2', () => {
    const preset = createExecutionPreset(
        'preset-1',
        'Smoke',
        '2026-07-22T00:00:00Z',
        initialConfig,
    );

    assert.equal(preset.id, 'preset-1');
    assert.equal(preset.name, 'Smoke');
    assert.equal(preset.schemaVersion, 2);
    assert.equal(preset.createdAt, '2026-07-22T00:00:00Z');
    assert.equal(preset.updatedAt, '2026-07-22T00:00:00Z');
    assert.deepEqual(preset.config, initialConfig);
});

test('overwriteExecutionPresetConfig preserves identity and replaces the snapshot', () => {
    const preset = {
        ...createExecutionPreset(
        'preset-1',
        'Smoke',
        '2026-07-22T00:00:00Z',
        initialConfig,
        ),
        schemaVersion: 1 as const,
        config: { ...initialConfig, subjectModel: 'openrouter/legacy-subject' },
    };
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
    assert.equal(updated.schemaVersion, 2);
    assert.deepEqual(updated.config, nextConfig);
});

test('AC-002/003 / INV-003 loading a legacy preset preserves the current subject', () => {
    const store = useSettingsStore;
    store.setState({
        availableModels: [
            { id: 'openrouter/current-subject', name: 'Current Subject', provider: 'openrouter' },
            { id: 'openrouter/judge', name: 'Judge', provider: 'openrouter' },
        ],
        tasks: [{ id: '01', type: 'fact', promptPreview: 'task 01' }],
        subjectModelId: 'openrouter/current-subject',
        freeTextSubject: 'manual-current-subject',
        judgeModelIds: [],
        preferredHosts: { 'openrouter/current-subject': 'together' },
        executionPresets: [{
            id: 'legacy-preset',
            name: 'Legacy',
            schemaVersion: 1,
            createdAt: '2026-07-22T00:00:00Z',
            updatedAt: '2026-07-22T00:00:00Z',
            config: {
                ...initialConfig,
                subjectModel: 'openrouter/legacy-subject',
                preferredHosts: {
                    'openrouter/legacy-subject': 'legacy-host',
                    'openrouter/judge': 'deepinfra',
                },
            },
        }],
    });

    assert.equal(store.getState().loadExecutionPreset('legacy-preset'), true);

    const loaded = store.getState();
    assert.equal(loaded.subjectModelId, 'openrouter/current-subject');
    assert.equal(loaded.freeTextSubject, 'manual-current-subject');
    assert.deepEqual(loaded.judgeModelIds, ['openrouter/judge']);
    assert.deepEqual(loaded.preferredHosts, {
        'openrouter/current-subject': 'together',
        'openrouter/judge': 'deepinfra',
    });
});
