import assert from 'node:assert/strict';
import test from 'node:test';
import type { EvaluationRun } from '../types/index.ts';
import { buildModelAggregates } from './modelAggregates.ts';
import { formatHeroScore } from './judgeReliability.ts';

function baseRun(overrides: Partial<EvaluationRun> = {}): EvaluationRun {
    return {
        id: 'run-1',
        subjectModelId: 'model-a',
        subjectModelName: 'Model A',
        judgeModels: [],
        timestamp: '2026-07-23T00:00:00Z',
        averageScore: 80,
        bestScore: 90,
        taskCount: 1,
        taskResults: [],
        holisticTaskResults: [],
        ...overrides,
    };
}

test('AC-001/003 null-only hero aggregates stay null (not 0)', () => {
    const rows = buildModelAggregates([
        baseRun({
            id: 'null-1',
            averageScore: null,
            bestScore: null,
        }),
        baseRun({
            id: 'null-2',
            timestamp: '2026-07-23T01:00:00Z',
            averageScore: null,
            bestScore: null,
        }),
    ]);

    assert.equal(rows.length, 1);
    assert.equal(rows[0].avgScore, null);
    assert.equal(rows[0].bestScore, null);
    assert.equal(rows[0].runCount, 2);
    assert.equal(formatHeroScore(rows[0].avgScore), '\u2014');
    assert.equal(formatHeroScore(rows[0].bestScore), '\u2014');
});

test('mixed null and numeric heroes: mean/max ignore null, null-only model sorts last', () => {
    const rows = buildModelAggregates([
        baseRun({
            id: 'scored',
            subjectModelId: 'model-scored',
            subjectModelName: 'Scored',
            averageScore: 70,
            bestScore: 75,
        }),
        baseRun({
            id: 'scored-2',
            subjectModelId: 'model-scored',
            subjectModelName: 'Scored',
            timestamp: '2026-07-23T02:00:00Z',
            averageScore: null,
            bestScore: null,
        }),
        baseRun({
            id: 'empty',
            subjectModelId: 'model-empty',
            subjectModelName: 'Empty',
            averageScore: null,
            bestScore: null,
        }),
    ]);

    assert.equal(rows.length, 2);
    assert.equal(rows[0].id, 'model-scored');
    assert.equal(rows[0].avgScore, 70);
    assert.equal(rows[0].bestScore, 75);
    assert.equal(rows[0].runCount, 2);
    assert.equal(rows[1].id, 'model-empty');
    assert.equal(rows[1].avgScore, null);
    assert.equal(rows[1].bestScore, null);
});

test('genuine zero hero remains 0 (distinct from null)', () => {
    const rows = buildModelAggregates([
        baseRun({
            averageScore: 0,
            bestScore: 0,
        }),
    ]);
    assert.equal(rows[0].avgScore, 0);
    assert.equal(rows[0].bestScore, 0);
    assert.equal(formatHeroScore(rows[0].avgScore), '0');
});
