/**
 * ResultDetail exclusion display contracts (AC-003 / AC-004).
 * Pure helpers live in judgeReliability; this file maps them to ResultDetail usage.
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import type { EvaluationRun } from '../types/index.ts';
import {
    computeJudgeSummaries,
    formatHeroScore,
    formatReliabilityReason,
} from '../lib/judgeReliability.ts';

test('ResultDetail exclusion panel shows reason labels and before/after', () => {
    const aggregation = {
        averageScoreBefore: 72.5,
        averageScoreAfter: 85,
        bestScoreBefore: 90,
        bestScoreAfter: 90,
        excludedJudges: [
            { judgeId: 'judge-noisy', reasons: ['high_variance', 'low_confidence'] },
        ],
        includedJudges: ['judge-ok'],
        allExcluded: false,
        unreliableCandidates: [],
    };
    const reasonText = aggregation.excludedJudges[0].reasons
        .map(formatReliabilityReason)
        .join(' · ');
    assert.match(reasonText, /ばらつき大/);
    assert.match(reasonText, /低信頼/);
    assert.equal(formatHeroScore(aggregation.averageScoreBefore), '72.5');
    assert.equal(formatHeroScore(aggregation.averageScoreAfter), '85');
});

test('ResultDetail N/A hero when allExcluded', () => {
    const run: Pick<EvaluationRun, 'averageScore' | 'bestScore' | 'scoreAggregation'> = {
        averageScore: null,
        bestScore: null,
        scoreAggregation: {
            averageScoreBefore: 40,
            averageScoreAfter: null,
            bestScoreBefore: 50,
            bestScoreAfter: null,
            excludedJudges: [{ judgeId: 'a', reasons: ['critical_fail'] }],
            includedJudges: [],
            allExcluded: true,
            unreliableCandidates: [],
        },
    };
    assert.equal(formatHeroScore(run.averageScore), '\u2014');
    assert.equal(run.scoreAggregation?.allExcluded, true);
});

test('ResultDetail cross-task summary drops excluded lineages', () => {
    const run = {
        id: 'r',
        subjectModelId: 's',
        subjectModelName: 'S',
        judgeModels: [],
        timestamp: '2026-07-23T00:00:00Z',
        averageScore: 85,
        bestScore: 90,
        taskCount: 1,
        excludeUnreliableJudges: true,
        scoreAggregation: {
            averageScoreBefore: 75,
            averageScoreAfter: 85,
            bestScoreBefore: 90,
            bestScoreAfter: 90,
            excludedJudges: [{ judgeId: 'bad', reasons: ['cross_judge_divergence'] }],
            includedJudges: ['good'],
            allExcluded: false,
            unreliableCandidates: [],
        },
        taskResults: [
            {
                taskId: '01',
                taskType: 'fact' as const,
                inputPrompt: '',
                subjectPrompt: '',
                subjectResponse: '',
                subjectUsage: null,
                subjectRuns: [],
                subjectRunCount: 1,
                toolTrace: [],
                hasSubjectTools: false,
                judgeEvaluations: [
                    {
                        judgeModelId: 'good',
                        judgeModelName: 'good',
                        logicAndFact: { mean: 0, sd: 0 },
                        constraintAdherence: { mean: 0, sd: 0 },
                        helpfulness: { mean: 0, sd: 0 },
                        totalScore: { mean: 85, sd: 0 },
                        confidenceDistribution: { high: 1, medium: 0, low: 0 },
                        criticalFail: { detected: false },
                        reasoningSamples: [],
                        apiReasoningSamples: [],
                    },
                    {
                        judgeModelId: 'bad',
                        judgeModelName: 'bad',
                        logicAndFact: { mean: 0, sd: 0 },
                        constraintAdherence: { mean: 0, sd: 0 },
                        helpfulness: { mean: 0, sd: 0 },
                        totalScore: { mean: 65, sd: 0 },
                        confidenceDistribution: { high: 1, medium: 0, low: 0 },
                        criticalFail: { detected: false },
                        reasoningSamples: [],
                        apiReasoningSamples: [],
                    },
                ],
            },
        ],
        holisticTaskResults: [],
    } satisfies EvaluationRun;
    const summaries = computeJudgeSummaries(run);
    assert.deepEqual(
        summaries.map((s) => s.judgeModelId),
        ['good'],
    );
});
