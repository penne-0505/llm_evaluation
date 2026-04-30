import test from 'node:test';
import assert from 'node:assert/strict';

import { convertBenchmarkResult } from './client.ts';

test('convertBenchmarkResult ignores judge results without aggregated payload and still returns a run', () => {
    const converted = convertBenchmarkResult({
        run_id: 'run_123',
        target_model: 'openrouter/openai/gpt-5.4',
        judge_models: ['judge-ok', 'judge-missing'],
        judge_runs: 3,
        executed_at: '2026-04-19T12:00:00Z',
        tasks: [
            {
                task_name: '01',
                task_type: 'fact',
                input_prompt: 'prompt',
                response: 'response',
                judge_results: {
                    'judge-ok': {
                        runs: [
                            {
                                score: {
                                    logic_and_fact: 60,
                                    constraint_adherence: 30,
                                    helpfulness_and_creativity: 10,
                                },
                                total_score: 100,
                                confidence: 'high',
                                critical_fail: false,
                                reasoning: 'ok',
                            },
                        ],
                        aggregated: {
                            logic_and_fact_mean: 60,
                            logic_and_fact_std: 0,
                            constraint_adherence_mean: 30,
                            constraint_adherence_std: 0,
                            helpfulness_mean: 10,
                            helpfulness_std: 0,
                            total_score_mean: 100,
                            total_score_std: 0,
                            critical_fail: false,
                            confidence_distribution: {
                                high: 1,
                                medium: 0,
                                low: 0,
                            },
                        },
                    },
                    'judge-missing': {
                        runs: [],
                        aggregated: null,
                        error: 'all runs skipped',
                    },
                },
            },
        ],
        holistic_tasks: [
            {
                task_name: 'style',
                task_type: 'holistic',
                input_prompt: 'holistic prompt',
                response: '',
                judge_results: {
                    'judge-missing': {
                        runs: [],
                        aggregated: null,
                        error: 'all runs skipped',
                    },
                },
            },
        ],
        cancelled: false,
        completed_tasks: 1,
        total_tasks: 1,
        average_score: 100,
        best_score: 100,
    });

    assert.equal(converted.id, 'run_123');
    assert.equal(converted.taskResults.length, 1);
    assert.equal(converted.taskResults[0]?.judgeEvaluations.length, 1);
    assert.equal(converted.taskResults[0]?.judgeEvaluations[0]?.judgeModelId, 'judge-ok');
    assert.equal(converted.taskResults[0]?.inputPrompt, 'prompt');
    assert.equal(converted.taskResults[0]?.subjectPrompt, '');
    assert.deepStrictEqual(converted.taskResults[0]?.toolTrace, []);
    assert.equal(converted.holisticTaskResults.length, 1);
    assert.equal(converted.holisticTaskResults[0]?.judgeEvaluations.length, 0);
    assert.equal(converted.holisticTaskResults[0]?.inputPrompt, 'holistic prompt');
    assert.equal(converted.holisticTaskResults[0]?.subjectPrompt, '');
    assert.deepStrictEqual(converted.holisticTaskResults[0]?.toolTrace, []);
});
