import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Provider, ApiKeyEntry, Model, Task, EvalParams } from '../types';
import { fetchTasks, fetchModels, fetchKeyStatus, saveKey as apiSaveKey, deleteKey as apiDeleteKey } from '../api/client';

interface SettingsState {
    // API Keys
    apiKeys: Partial<Record<Provider, ApiKeyEntry>>;
    setApiKey: (provider: Provider, key: string) => Promise<void>;
    deleteApiKey: (provider: Provider) => Promise<void>;
    refreshKeyStatus: () => Promise<void>;

    // Models
    availableModels: Model[];
    modelsLastUpdated: string | null;
    modelsLoading: boolean;
    subjectModelId: string | null;
    judgeModelIds: string[];
    setSubjectModel: (id: string | null) => void;
    toggleJudgeModel: (id: string) => void;
    refreshModels: (force?: boolean) => Promise<void>;

    // Free-text model inputs
    freeTextSubject: string;
    freeTextJudges: string[];
    setFreeTextSubject: (v: string) => void;
    addFreeTextJudge: (v: string) => void;
    removeFreeTextJudge: (v: string) => void;

    // Parameters
    evalParams: EvalParams;
    setJudgeRunCount: (n: number) => void;
    setSubjectTemperature: (t: number) => void;

    // Tasks
    tasks: Task[];
    tasksLoading: boolean;
    selectedTaskIds: string[];
    toggleTask: (id: string) => void;
    selectAllTasks: () => void;
    deselectAllTasks: () => void;
    refreshTasks: () => Promise<void>;
}

export const useSettingsStore = create<SettingsState>()(
    persist(
        (set, get) => ({
            // --- API Keys ---
            apiKeys: {},

            setApiKey: async (provider, key) => {
                try {
                    await apiSaveKey(provider, key);
                    set((s) => ({
                        apiKeys: {
                            ...s.apiKeys,
                            [provider]: { provider, key: '••••••••', isValid: true },
                        },
                    }));
                    // モデル一覧も再取得（新しいキーでプロバイダーが使えるようになる可能性）
                    get().refreshModels();
                } catch (err) {
                    set((s) => ({
                        apiKeys: {
                            ...s.apiKeys,
                            [provider]: {
                                provider,
                                key,
                                isValid: false,
                                error: err instanceof Error ? err.message : 'Failed to save',
                            },
                        },
                    }));
                }
            },

            deleteApiKey: async (provider) => {
                try {
                    await apiDeleteKey(provider);
                    set((s) => {
                        const next = { ...s.apiKeys };
                        delete next[provider];
                        return { apiKeys: next };
                    });
                } catch {
                    // 削除失敗は静かに無視
                }
            },

            refreshKeyStatus: async () => {
                try {
                    const status = await fetchKeyStatus();
                    const providers: Provider[] = ['openai', 'anthropic', 'gemini', 'openrouter'];
                    const newKeys: Partial<Record<Provider, ApiKeyEntry>> = {};
                    for (const p of providers) {
                        if (status[p]) {
                            newKeys[p] = { provider: p, key: '••••••••', isValid: true };
                        }
                    }
                    set({ apiKeys: newKeys });
                } catch {
                    // ステータス取得失敗は静かに無視
                }
            },

            // --- Models ---
            availableModels: [],
            modelsLastUpdated: null,
            modelsLoading: false,
            subjectModelId: null,
            judgeModelIds: [],
            setSubjectModel: (id) => set({ subjectModelId: id }),
            toggleJudgeModel: (id) => {
                const ids = get().judgeModelIds;
                set({
                    judgeModelIds: ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id],
                });
            },

            refreshModels: async (force = false) => {
                set({ modelsLoading: true });
                try {
                    const result = await fetchModels(force);
                    set({
                        availableModels: result.models,
                        modelsLastUpdated: result.updatedAt || new Date().toISOString(),
                        modelsLoading: false,
                    });
                } catch {
                    set({ modelsLoading: false });
                }
            },

            // --- Free-text ---
            freeTextSubject: '',
            freeTextJudges: [],
            setFreeTextSubject: (v) => set({ freeTextSubject: v }),
            addFreeTextJudge: (v) => {
                if (v.trim() && !get().freeTextJudges.includes(v.trim())) {
                    set((s) => ({ freeTextJudges: [...s.freeTextJudges, v.trim()] }));
                }
            },
            removeFreeTextJudge: (v) => set((s) => ({ freeTextJudges: s.freeTextJudges.filter((x) => x !== v) })),

            // --- Parameters ---
            evalParams: {
                judgeRunCount: 3,
                subjectTemperature: 0.7,
                judgeTemperature: 0.0,
            },
            setJudgeRunCount: (n) => set((s) => ({ evalParams: { ...s.evalParams, judgeRunCount: n } })),
            setSubjectTemperature: (t) => set((s) => ({ evalParams: { ...s.evalParams, subjectTemperature: t } })),

            // --- Tasks ---
            tasks: [],
            tasksLoading: false,
            selectedTaskIds: [],
            toggleTask: (id) => {
                const ids = get().selectedTaskIds;
                set({ selectedTaskIds: ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id] });
            },
            selectAllTasks: () => set((s) => ({ selectedTaskIds: s.tasks.map((t) => t.id) })),
            deselectAllTasks: () => set({ selectedTaskIds: [] }),

            refreshTasks: async () => {
                set({ tasksLoading: true });
                try {
                    const tasks = await fetchTasks();
                    set({ tasks, tasksLoading: false });
                } catch {
                    set({ tasksLoading: false });
                }
            },
        }),
        {
            name: 'llm-eval-settings',
            // persist はモデル選択やパラメータのみ（モデルリスト・タスクはAPIから毎回取得）
            partialize: (state) => ({
                subjectModelId: state.subjectModelId,
                judgeModelIds: state.judgeModelIds,
                freeTextSubject: state.freeTextSubject,
                freeTextJudges: state.freeTextJudges,
                evalParams: state.evalParams,
                selectedTaskIds: state.selectedTaskIds,
            }),
        }
    )
);
