import test from 'node:test';
import assert from 'node:assert/strict';

import { convertBenchmarkResult, buildRunRequestBody } from './client.ts';

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
    assert.deepStrictEqual(
        converted.taskResults[0]?.judgeEvaluations[0]?.reasoningSamples,
        ['ok'],
    );
    assert.deepStrictEqual(
        converted.taskResults[0]?.judgeEvaluations[0]?.apiReasoningSamples,
        [],
    );
    assert.equal(converted.taskResults[0]?.inputPrompt, 'prompt');
    assert.equal(converted.taskResults[0]?.subjectPrompt, '');
    assert.deepStrictEqual(converted.taskResults[0]?.toolTrace, []);
    assert.equal(converted.taskResults[0]?.hasSubjectTools, false);
    assert.equal(converted.holisticTaskResults.length, 1);
    assert.equal(converted.holisticTaskResults[0]?.judgeEvaluations.length, 0);
    assert.equal(converted.holisticTaskResults[0]?.inputPrompt, 'holistic prompt');
    assert.equal(converted.holisticTaskResults[0]?.subjectPrompt, '');
    assert.deepStrictEqual(converted.holisticTaskResults[0]?.toolTrace, []);
    assert.equal(converted.holisticTaskResults[0]?.hasSubjectTools, false);
});

test('convertBenchmarkResult separates api_reasoning from scoring reasoning', () => {
    const converted = convertBenchmarkResult({
        run_id: 'run_api_reasoning',
        target_model: 'openrouter/openai/gpt-5.4',
        judge_models: ['judge-ok'],
        judge_runs: 1,
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
                                reasoning: {
                                    logic_and_fact: 'score rationale',
                                },
                                api_reasoning: 'model internal thinking',
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
                },
            },
        ],
        cancelled: false,
        completed_tasks: 1,
        total_tasks: 1,
        average_score: 100,
        best_score: 100,
    });

    const je = converted.taskResults[0]?.judgeEvaluations[0];
    assert.ok(je);
    assert.equal(je.reasoningSamples.length, 1);
    assert.match(je.reasoningSamples[0] ?? '', /score rationale/);
    assert.deepStrictEqual(je.apiReasoningSamples, ['model internal thinking']);
});

test('convertBenchmarkResult maps has_subject_tools and keeps unused tool tasks visible to the UI', () => {
    const converted = convertBenchmarkResult({
        run_id: 'run_tools',
        target_model: 'openrouter/openai/gpt-5.4',
        judge_models: ['judge-ok'],
        judge_runs: 1,
        executed_at: '2026-04-19T12:00:00Z',
        tasks: [
            {
                task_name: '08',
                task_type: 'fact',
                input_prompt: 'prompt',
                response: 'response',
                tool_trace: [],
                has_subject_tools: true,
                judge_results: {},
            },
        ],
        cancelled: false,
        completed_tasks: 1,
        total_tasks: 1,
        average_score: 0,
        best_score: 0,
    });

    assert.equal(converted.taskResults[0]?.hasSubjectTools, true);
    assert.deepStrictEqual(converted.taskResults[0]?.toolTrace, []);
});

test('convertBenchmarkResult maps holistic_judge_models separately from judge_models', () => {
    const converted = convertBenchmarkResult({
        run_id: 'run_holistic_judges',
        target_model: 'openrouter/openai/gpt-5.4',
        judge_models: ['judge-per-task'],
        holistic_judge_models: ['judge-holistic'],
        judge_runs: 1,
        executed_at: '2026-07-23T12:00:00Z',
        tasks: [],
        holistic_tasks: [],
        cancelled: false,
        completed_tasks: 0,
        total_tasks: 0,
        average_score: 0,
        best_score: 0,
    });

    assert.deepStrictEqual(converted.judgeModels, [
        { id: 'judge-per-task', name: 'judge-per-task' },
    ]);
    assert.deepStrictEqual(converted.holisticJudgeModels, [
        { id: 'judge-holistic', name: 'judge-holistic' },
    ]);
});

test('buildRunRequestBody includes holistic_judge_models for three patterns', () => {
    const standardOnly = JSON.parse(
        buildRunRequestBody({
            targetModel: 'subject',
            judgeModels: ['judge-a'],
            holisticJudgeModels: [],
            selectedTaskIds: ['01'],
            judgeRuns: 3,
            subjectTemp: 0.6,
            strictMode: false,
            runHolistic: false,
        }),
    );
    assert.deepEqual(standardOnly.holistic_judge_models, []);
    assert.equal(standardOnly.run_holistic, false);

    const fallback = JSON.parse(
        buildRunRequestBody({
            targetModel: 'subject',
            judgeModels: ['judge-a'],
            selectedTaskIds: ['01'],
            judgeRuns: 3,
            subjectTemp: 0.6,
            strictMode: false,
            runHolistic: true,
        }),
    );
    assert.deepEqual(fallback.holistic_judge_models, []);

    const both = JSON.parse(
        buildRunRequestBody({
            targetModel: 'subject',
            judgeModels: ['judge-a'],
            holisticJudgeModels: ['judge-holistic'],
            selectedTaskIds: ['01'],
            judgeRuns: 3,
            subjectTemp: 0.6,
            strictMode: false,
            runHolistic: true,
        }),
    );
    assert.deepEqual(both.judge_models, ['judge-a']);
    assert.deepEqual(both.holistic_judge_models, ['judge-holistic']);
});

test('convertBenchmarkResult maps task_timing and tolerates legacy tasks without it', () => {
    const withTiming = convertBenchmarkResult({
        run_id: 'run_timing',
        target_model: 'openrouter/openai/gpt-5.4',
        judge_models: ['judge-ok'],
        judge_runs: 1,
        executed_at: '2026-07-23T12:00:00Z',
        execution_duration_ms: 20_000,
        timing_summary: {
            subject_duration_ms: 1200,
            judge_duration_ms: 3400,
            total_duration_ms: 4600,
        },
        tasks: [
            {
                task_name: '01',
                task_type: 'fact',
                input_prompt: 'prompt',
                response: 'response',
                task_timing: {
                    subject_duration_ms: 1200,
                    judge_duration_ms: 3400,
                },
                judge_results: {},
            },
        ],
        cancelled: false,
        completed_tasks: 1,
        total_tasks: 1,
        average_score: 0,
        best_score: 0,
    });
    assert.deepStrictEqual(withTiming.taskResults[0]?.taskTiming, {
        subjectDurationMs: 1200,
        judgeDurationMs: 3400,
    });
    assert.deepStrictEqual(withTiming.timingSummary, {
        subjectDurationMs: 1200,
        judgeDurationMs: 3400,
        totalDurationMs: 4600,
    });
    assert.equal(withTiming.executionDurationMs, 20_000);

    const legacy = convertBenchmarkResult({
        run_id: 'run_legacy',
        target_model: 'openrouter/openai/gpt-5.4',
        judge_models: ['judge-ok'],
        judge_runs: 1,
        executed_at: '2026-07-23T12:00:00Z',
        execution_duration_ms: 9999,
        tasks: [
            {
                task_name: '01',
                task_type: 'fact',
                input_prompt: 'prompt',
                response: 'response',
                judge_results: {},
            },
        ],
        cancelled: false,
        completed_tasks: 1,
        total_tasks: 1,
        average_score: 0,
        best_score: 0,
    });
    assert.equal(legacy.taskResults[0]?.taskTiming, undefined);
    assert.equal(legacy.timingSummary, undefined);
});

test('buildRunRequestBody includes subject_runs and defaults to 1', () => {
    const withRuns = JSON.parse(
        buildRunRequestBody({
            targetModel: 'subject',
            judgeModels: ['judge-a'],
            selectedTaskIds: ['01'],
            judgeRuns: 3,
            subjectRuns: 4,
            subjectTemp: 0.6,
            strictMode: false,
        }),
    );
    assert.equal(withRuns.subject_runs, 4);
    assert.equal(withRuns.judge_runs, 3);

    const defaulted = JSON.parse(
        buildRunRequestBody({
            targetModel: 'subject',
            judgeModels: ['judge-a'],
            selectedTaskIds: ['01'],
            judgeRuns: 2,
            subjectTemp: 0.6,
            strictMode: false,
        }),
    );
    assert.equal(defaulted.subject_runs, 1);
});

test('convertBenchmarkResult maps subject_runs array for ResultDetail', () => {
    const converted = convertBenchmarkResult({
        run_id: 'run_multi',
        target_model: 'subject',
        judge_models: ['judge-a'],
        judge_runs: 1,
        executed_at: '2026-07-23T00:00:00Z',
        tasks: [
            {
                task_name: '01',
                task_type: 'fact',
                input_prompt: 'prompt',
                response: 'first',
                subject_run_count: 2,
                subject_runs: [
                    {
                        run_index: 1,
                        response: 'first',
                        subject_usage: {
                            provider: 'stub',
                            model: 'm',
                            input_tokens: 1,
                            output_tokens: 2,
                            total_tokens: 3,
                        },
                        tool_trace: [],
                        error: null,
                    },
                    {
                        run_index: 2,
                        response: '[ERROR] x',
                        error: 'x',
                        tool_trace: [],
                    },
                ],
                judge_results: {},
            },
        ],
        cancelled: false,
        completed_tasks: 1,
        total_tasks: 1,
        average_score: 0,
        best_score: 0,
    });
    const task = converted.taskResults[0];
    assert.equal(task?.subjectRunCount, 2);
    assert.equal(task?.subjectRuns?.length, 2);
    assert.equal(task?.subjectRuns?.[0]?.response, 'first');
    assert.equal(task?.subjectRuns?.[1]?.error, 'x');
    assert.equal(task?.subjectResponse, 'first');
});

test('buildRunRequestBody includes exclude_unreliable_judges default false', () => {
    const body = JSON.parse(
        buildRunRequestBody({
            targetModel: 'subject',
            judgeModels: ['judge-a'],
            selectedTaskIds: ['01'],
            judgeRuns: 3,
            subjectTemp: 0.6,
            strictMode: false,
        }),
    );
    assert.equal(body.exclude_unreliable_judges, false);

    const on = JSON.parse(
        buildRunRequestBody({
            targetModel: 'subject',
            judgeModels: ['judge-a'],
            selectedTaskIds: ['01'],
            judgeRuns: 3,
            subjectTemp: 0.6,
            strictMode: false,
            excludeUnreliableJudges: true,
        }),
    );
    assert.equal(on.exclude_unreliable_judges, true);
});

test('convertBenchmarkResult maps null hero scores and score_aggregation', () => {
    const converted = convertBenchmarkResult({
        run_id: 'run-exclude',
        target_model: 'subject',
        judge_models: ['judge-a', 'judge-b'],
        judge_runs: 1,
        executed_at: '2026-07-23T00:00:00Z',
        exclude_unreliable_judges: true,
        score_aggregation: {
            average_score_before: 45,
            average_score_after: null,
            best_score_before: 50,
            best_score_after: null,
            excluded_judges: [
                { judge_id: 'judge-a', reasons: ['high_variance'] },
                { judge_id: 'judge-b', reasons: ['critical_fail'] },
            ],
            included_judges: [],
            all_excluded: true,
            unreliable_candidates: [],
        },
        tasks: [],
        cancelled: false,
        completed_tasks: 0,
        total_tasks: 0,
        average_score: null,
        best_score: null,
    });
    assert.equal(converted.averageScore, null);
    assert.equal(converted.bestScore, null);
    assert.equal(converted.excludeUnreliableJudges, true);
    assert.equal(converted.scoreAggregation?.allExcluded, true);
    assert.equal(converted.scoreAggregation?.excludedJudges[0]?.judgeId, 'judge-a');
    assert.deepEqual(converted.scoreAggregation?.excludedJudges[0]?.reasons, ['high_variance']);
});
