import assert from 'node:assert/strict';
import test from 'node:test';
import type { EvaluationRun, JudgeEvaluation, TaskResult } from '../types/index.ts';
import {
    computeJudgeSummaries,
    formatHeroScore,
    formatReliabilityReason,
    isHeroScoreAvailable,
} from './judgeReliability.ts';

function je(
    id: string,
    mean: number,
    overrides: Partial<JudgeEvaluation> = {},
): JudgeEvaluation {
    return {
        judgeModelId: id,
        judgeModelName: id,
        logicAndFact: { mean: 0, sd: 0 },
        constraintAdherence: { mean: 0, sd: 0 },
        helpfulness: { mean: 0, sd: 0 },
        totalScore: { mean, sd: 0 },
        confidenceDistribution: { high: 1, medium: 0, low: 0 },
        criticalFail: { detected: false },
        reasoningSamples: [],
        apiReasoningSamples: [],
        ...overrides,
    };
}

function task(id: string, judges: JudgeEvaluation[]): TaskResult {
    return {
        taskId: id,
        taskType: 'fact',
        inputPrompt: 'p',
        subjectPrompt: '',
        subjectResponse: 'r',
        subjectUsage: null,
        subjectRuns: [],
        subjectRunCount: 1,
        judgeEvaluations: judges,
        toolTrace: [],
        hasSubjectTools: false,
    };
}

function baseRun(overrides: Partial<EvaluationRun> = {}): EvaluationRun {
    return {
        id: 'run-1',
        subjectModelId: 'subject',
        subjectModelName: 'Subject',
        judgeModels: [
            { id: 'judge-a', name: 'judge-a' },
            { id: 'judge-b', name: 'judge-b' },
        ],
        timestamp: '2026-07-23T00:00:00Z',
        averageScore: 75,
        bestScore: 90,
        taskCount: 2,
        taskResults: [
            task('01', [je('judge-a', 80), je('judge-b', 70)]),
            task('02', [je('judge-a', 90), je('judge-b', 60)]),
        ],
        holisticTaskResults: [],
        ...overrides,
    };
}

test('formatReliabilityReason maps backend codes only', () => {
    assert.equal(formatReliabilityReason('high_variance'), 'ばらつき大（試行間 SD）');
    assert.equal(formatReliabilityReason('low_confidence'), '低信頼レビューあり');
    assert.equal(formatReliabilityReason('critical_fail'), '重大な失敗を検出');
    assert.equal(formatReliabilityReason('cross_judge_divergence'), 'judge 間スコア乖離');
    assert.equal(formatReliabilityReason('unknown_code'), 'unknown_code');
});

test('formatHeroScore shows em-dash for null', () => {
    assert.equal(formatHeroScore(null), '\u2014');
    assert.equal(formatHeroScore(undefined), '\u2014');
    assert.equal(formatHeroScore(85.5), '85.5');
    assert.equal(isHeroScoreAvailable(null), false);
    assert.equal(isHeroScoreAvailable(0), true);
});

test('computeJudgeSummaries excludes lineages when toggle ON', () => {
    const run = baseRun({
        excludeUnreliableJudges: true,
        scoreAggregation: {
            averageScoreBefore: 75,
            averageScoreAfter: 85,
            bestScoreBefore: 90,
            bestScoreAfter: 90,
            excludedJudges: [{ judgeId: 'judge-b', reasons: ['high_variance'] }],
            includedJudges: ['judge-a'],
            allExcluded: false,
            unreliableCandidates: [{ judgeId: 'judge-b', reasons: ['high_variance'] }],
        },
    });
    const summaries = computeJudgeSummaries(run);
    assert.equal(summaries.length, 1);
    assert.equal(summaries[0].judgeModelId, 'judge-a');
    assert.equal(summaries[0].averageScore, 85);
});

test('computeJudgeSummaries keeps all judges when toggle OFF', () => {
    const run = baseRun({
        excludeUnreliableJudges: false,
        scoreAggregation: {
            averageScoreBefore: 75,
            averageScoreAfter: 75,
            bestScoreBefore: 90,
            bestScoreAfter: 90,
            excludedJudges: [],
            includedJudges: ['judge-a', 'judge-b'],
            allExcluded: false,
            unreliableCandidates: [{ judgeId: 'judge-b', reasons: ['high_variance'] }],
        },
    });
    const summaries = computeJudgeSummaries(run);
    assert.equal(summaries.length, 2);
});

test('all-excluded run exposes N/A hero contract', () => {
    const run = baseRun({
        averageScore: null,
        bestScore: null,
        excludeUnreliableJudges: true,
        scoreAggregation: {
            averageScoreBefore: 45,
            averageScoreAfter: null,
            bestScoreBefore: 50,
            bestScoreAfter: null,
            excludedJudges: [
                { judgeId: 'judge-a', reasons: ['high_variance'] },
                { judgeId: 'judge-b', reasons: ['critical_fail'] },
            ],
            includedJudges: [],
            allExcluded: true,
            unreliableCandidates: [],
        },
    });
    assert.equal(formatHeroScore(run.averageScore), '\u2014');
    assert.equal(run.scoreAggregation?.allExcluded, true);
    assert.equal(computeJudgeSummaries(run).length, 0);
});
