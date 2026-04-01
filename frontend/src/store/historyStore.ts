import { create } from 'zustand';
import type { EvaluationRun } from '../types';
import { fetchResultSummaries, fetchResultDetail, type ResultSummary } from '../api/client';

interface HistoryState {
    runs: EvaluationRun[];
    summaries: ResultSummary[];
    isLoaded: boolean;
    loadError: string | null;

    addRun: (run: EvaluationRun) => void;
    getRunById: (id: string) => EvaluationRun | undefined;
    getSummaryByRunId: (runId: string) => ResultSummary | undefined;
    initialize: () => Promise<void>;
    loadRunDetail: (runId: string) => Promise<EvaluationRun | undefined>;
    upsertRun: (run: EvaluationRun) => void;
    removeRun: (runId: string) => void;
}

export const useHistoryStore = create<HistoryState>()((set, get) => ({
    runs: [],
    summaries: [],
    isLoaded: false,
    loadError: null,

    addRun: (run) =>
        set((s) => ({
            runs: [run, ...s.runs],
        })),

    upsertRun: (run) =>
        set((s) => {
            const existing = s.runs.find((item) => item.id === run.id);
            if (!existing) {
                return { runs: [run, ...s.runs] };
            }
            return {
                runs: s.runs.map((item) => (item.id === run.id ? { ...item, ...run } : item)),
            };
        }),

    getRunById: (id) => get().runs.find((r) => r.id === id),
    getSummaryByRunId: (runId) => get().summaries.find((s) => s.runId === runId),

    initialize: async () => {
        if (get().isLoaded) return;
        try {
            const summaries = await fetchResultSummaries();
            // サマリーから EvaluationRun の骨格を作成（詳細は遅延読み込み）
            const runs: EvaluationRun[] = summaries.map((s) => ({
                id: s.runId,
                subjectModelId: s.targetModel,
                subjectModelName: s.targetModel,
                judgeModels: [],  // サマリーにはjudge名が含まれない → 詳細ロード時に埋まる
                timestamp: s.executedAt,
                executionDurationMs: s.executionDurationMs,
                estimatedCostUsd: s.estimatedCostUsd,
                costEstimateStatus: s.costEstimateStatus,
                subjectTotalTokens: s.subjectTotalTokens,
                subjectEstimatedCostUsd: s.subjectEstimatedCostUsd,
                subjectCostPer1mTokensUsd: s.subjectCostPer1mTokensUsd,
                strictMode: {
                    requested: Boolean(s.strictModeRequested),
                    enforced: Boolean(s.strictModeEnforced),
                    eligible: Boolean(s.strictModeEligible),
                    presetId: s.strictModePresetId,
                    presetLabel: s.strictModePresetLabel,
                    profileId: s.strictModeProfileId,
                    profileLabel: s.strictModeProfileLabel,
                    reasons: [],
                },
                taskResults: [],  // 詳細ロード時に埋まる
                averageScore: Math.round((s.avgScore ?? 0) * 10) / 10,
                bestScore: Math.round((s.maxScore ?? 0) * 10) / 10,
                taskCount: s.taskCount,
                judgeCount: s.judgeCount ?? 0,
            }));
            set((state) => {
                const existingById = new Map(state.runs.map((run) => [run.id, run]));
                const mergedRuns = runs.map((run) => {
                    const existing = existingById.get(run.id);
                    return existing ? { ...run, ...existing } : run;
                });
                const runsById = new Map(mergedRuns.map((run) => [run.id, run]));
                for (const existing of state.runs) {
                    if (!runsById.has(existing.id)) {
                        mergedRuns.push(existing);
                    }
                }
                return { runs: mergedRuns, summaries, isLoaded: true };
            });
        } catch (err) {
            set({
                loadError: err instanceof Error ? err.message : '履歴の読み込みに失敗しました',
                isLoaded: true,
            });
        }
    },

    loadRunDetail: async (runId: string) => {
        const existing = get().runs.find((r) => r.id === runId);
        // 既にタスク結果がロードされていればそのまま返す
        if (existing && existing.taskResults.length > 0) return existing;

        // サマリーからファイル名を取得
        const summary = get().summaries.find((s) => s.runId === runId);
        if (!summary) return undefined;

        try {
            const detail = await fetchResultDetail(summary.filename);
            // ストア内の該当 run を詳細データで更新
            set((s) => ({
                runs: s.runs.map((r) => (r.id === runId ? { ...r, ...detail } : r)),
            }));
            return detail;
        } catch {
            return existing;
        }
    },

    removeRun: (runId) =>
        set((state) => ({
            runs: state.runs.filter((run) => run.id !== runId),
            summaries: state.summaries.filter((summary) => summary.runId !== runId),
        })),
}));
