import assert from 'node:assert/strict';
import test from 'node:test';

import type { Model, StrictModePreset, Task } from '../types';
import {
    filterModelsByStrictJudgeLeaves,
    getStrictModeIssues,
    judgeModelLeafId,
    resolveStrictJudgeSelection,
} from './strictMode.ts';

const preset: StrictModePreset = {
    id: 'official-v3',
    label: 'Official Strict v3',
    description: 'test',
    subjectModelPolicy: 'variable',
    judgeModels: [
        { id: 'openrouter/moonshotai/kimi-k3', label: 'Kimi K3', provider: 'openrouter' },
        { id: 'openrouter/openai/gpt-5.6-terra', label: 'GPT-5.6 Terra', provider: 'openrouter' },
        { id: 'openrouter/qwen/qwen3.7-max', label: 'Qwen3.7 Max', provider: 'openrouter' },
    ],
    taskIds: ['01', '02'],
    judgeRuns: 3,
    subjectTemperature: 0.45,
    judgeTemperature: 0.0,
};

const tasks: Task[] = [
    { id: '01', type: 'fact', promptPreview: 'task 01' },
    { id: '02', type: 'fact', promptPreview: 'task 02' },
];

const models: Model[] = [
    { id: 'openrouter/moonshotai/kimi-k3', name: 'Kimi K3', provider: 'openrouter' },
    { id: 'openai/gpt-5.6-terra', name: 'GPT-5.6 Terra', provider: 'openai' },
    { id: 'openrouter/qwen/qwen3.7-max', name: 'Qwen3.7 Max', provider: 'openrouter' },
    { id: 'openrouter/anthropic/claude-sonnet-5', name: 'Claude', provider: 'openrouter' },
];

test('judgeModelLeafId uses last path segment', () => {
    assert.equal(judgeModelLeafId('openrouter/openai/gpt-5.6-terra'), 'gpt-5.6-terra');
    assert.equal(judgeModelLeafId('openai/gpt-5.6-terra'), 'gpt-5.6-terra');
    assert.equal(judgeModelLeafId('kimi-k3'), 'kimi-k3');
});

test('getStrictModeIssues accepts alternate provider for same leaf', () => {
    const issues = getStrictModeIssues({
        strictPreset: preset,
        availableModels: models,
        tasks,
        selectedTaskIds: ['01', '02'],
        judgeModelIds: [
            'openrouter/moonshotai/kimi-k3',
            'openai/gpt-5.6-terra',
            'openrouter/qwen/qwen3.7-max',
        ],
        judgeRunCount: 3,
        subjectTemperature: 0.45,
    });
    assert.deepEqual(issues, []);
});

test('getStrictModeIssues rejects leaf mismatch', () => {
    const issues = getStrictModeIssues({
        strictPreset: preset,
        availableModels: models,
        tasks,
        selectedTaskIds: ['01', '02'],
        judgeModelIds: [
            'openrouter/moonshotai/kimi-k3',
            'openrouter/anthropic/claude-sonnet-5',
            'openrouter/qwen/qwen3.7-max',
        ],
        judgeRunCount: 3,
        subjectTemperature: 0.45,
    });
    assert.ok(issues.some((issue) => issue.includes('judge set')));
});

test('filterModelsByStrictJudgeLeaves keeps only matching leaves', () => {
    const filtered = filterModelsByStrictJudgeLeaves(models, preset);
    assert.deepEqual(
        filtered.map((m) => m.id).sort(),
        [
            'openai/gpt-5.6-terra',
            'openrouter/moonshotai/kimi-k3',
            'openrouter/qwen/qwen3.7-max',
        ],
    );
});

test('resolveStrictJudgeSelection prefers existing leaf match', () => {
    const resolved = resolveStrictJudgeSelection(
        preset,
        ['openai/gpt-5.6-terra'],
        models,
    );
    assert.equal(resolved[1], 'openai/gpt-5.6-terra');
    assert.equal(resolved[0], 'openrouter/moonshotai/kimi-k3');
});
