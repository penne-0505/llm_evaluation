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
    initialize: () => Promise<void>;
    loadRunDetail: (runId: string) => Promise<EvaluationRun | undefined>;
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

    getRunById: (id) => get().runs.find((r) => r.id === id),

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
                taskResults: [],  // 詳細ロード時に埋まる
                averageScore: Math.round((s.avgScore ?? 0) * 10) / 10,
                bestScore: Math.round((s.maxScore ?? 0) * 10) / 10,
                taskCount: s.taskCount,
                judgeCount: s.judgeCount ?? 0,
            }));
            set({ runs, summaries, isLoaded: true });
        } catch (err) {
            set({
                loadError: err instanceof Error ? err.message : 'Failed to load history',
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
                runs: s.runs.map((r) => (r.id === runId ? detail : r)),
            }));
            return detail;
        } catch {
            return existing;
        }
    },
}));
