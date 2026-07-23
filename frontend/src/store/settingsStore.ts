import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type {
    Provider,
    ApiKeyEntry,
    Model,
    Task,
    EvalParams,
    EvaluationMode,
    StrictModePreset,
    ToolMode,
    ExecutionPreset,
} from '../types';
import {
    captureExecutionPresetConfig,
    createExecutionPreset,
    EXECUTION_PRESET_SCHEMA_VERSION,
    overwriteExecutionPresetConfig,
    resolveExecutionPresetConfig,
} from '../lib/executionPresets';
import {
    fetchTasks,
    fetchModels,
    fetchKeyStatus,
    fetchStrictModePreset,
    saveKey as apiSaveKey,
    deleteKey as apiDeleteKey,
} from '../api/client';

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

    // Holistic judge models (empty = fallback to judgeModelIds)
    holisticJudgeModelIds: string[];
    freeTextHolisticJudges: string[];
    toggleHolisticJudgeModel: (id: string) => void;
    addFreeTextHolisticJudge: (v: string) => void;
    removeFreeTextHolisticJudge: (v: string) => void;

    // Parameters
    evaluationMode: EvaluationMode;
    strictPreset: StrictModePreset | null;
    strictPresetLoading: boolean;
    setEvaluationMode: (mode: EvaluationMode) => void;
    refreshStrictPreset: () => Promise<void>;
    evalParams: EvalParams;
    setJudgeRunCount: (n: number) => void;
    setSubjectRunCount: (n: number) => void;
    setSubjectTemperature: (t: number) => void;

    // Tasks
    tasks: Task[];
    tasksLoading: boolean;
    selectedTaskIds: string[];
    taskToolModeOverrides: Record<string, ToolMode>;
    toggleTask: (id: string) => void;
    selectAllTasks: () => void;
    deselectAllTasks: () => void;
    setTaskToolMode: (taskId: string, mode: ToolMode) => void;
    refreshTasks: () => Promise<void>;

    // Holistic
    runHolistic: boolean;
    setRunHolistic: (v: boolean) => void;

    // Exclude unreliable judges from hero average
    excludeUnreliableJudges: boolean;
    setExcludeUnreliableJudges: (v: boolean) => void;

    // Parallel execution
    subjectParallel: boolean;
    judgeParallel: boolean;
    setSubjectParallel: (v: boolean) => void;
    setJudgeParallel: (v: boolean) => void;

    // Named execution presets
    executionPresets: ExecutionPreset[];
    saveExecutionPreset: (name: string) => string | null;
    overwriteExecutionPreset: (id: string) => boolean;
    loadExecutionPreset: (id: string) => boolean;
    deleteExecutionPreset: (id: string) => void;
}

type CloudProvider = Exclude<Provider, 'lmstudio'>;

function createExecutionPresetId(): string {
    if (typeof globalThis.crypto?.randomUUID === 'function') {
        return globalThis.crypto.randomUUID();
    }
    return `preset-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
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
                                error: err instanceof Error ? err.message : '保存に失敗しました',
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
                    const providers: CloudProvider[] = ['openrouter'];
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
                if (get().evaluationMode === 'strict') return;
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
                if (get().evaluationMode === 'strict') return;
                if (v.trim() && !get().freeTextJudges.includes(v.trim())) {
                    set((s) => ({ freeTextJudges: [...s.freeTextJudges, v.trim()] }));
                }
            },
            removeFreeTextJudge: (v) => {
                if (get().evaluationMode === 'strict') return;
                set((s) => ({ freeTextJudges: s.freeTextJudges.filter((x) => x !== v) }));
            },

            // --- Holistic judges (DEC-005: not locked by strict mode) ---
            holisticJudgeModelIds: [],
            freeTextHolisticJudges: [],
            toggleHolisticJudgeModel: (id) => {
                const ids = get().holisticJudgeModelIds;
                set({
                    holisticJudgeModelIds: ids.includes(id)
                        ? ids.filter((x) => x !== id)
                        : [...ids, id],
                });
            },
            addFreeTextHolisticJudge: (v) => {
                if (v.trim() && !get().freeTextHolisticJudges.includes(v.trim())) {
                    set((s) => ({
                        freeTextHolisticJudges: [...s.freeTextHolisticJudges, v.trim()],
                    }));
                }
            },
            removeFreeTextHolisticJudge: (v) => {
                set((s) => ({
                    freeTextHolisticJudges: s.freeTextHolisticJudges.filter((x) => x !== v),
                }));
            },

            // --- Parameters ---
            evaluationMode: 'standard',
            strictPreset: null,
            strictPresetLoading: false,
            setEvaluationMode: (mode) => {
                set({ evaluationMode: mode });
                if (mode === 'strict') {
                    const preset = get().strictPreset;
                    if (preset) {
                        set((s) => ({
                            judgeModelIds: preset.judgeModels.map((judge) => judge.id),
                            freeTextJudges: [],
                            selectedTaskIds: preset.taskIds,
                            evalParams: {
                                ...s.evalParams,
                                judgeRunCount: preset.judgeRuns,
                                subjectTemperature: preset.subjectTemperature,
                                judgeTemperature: preset.judgeTemperature,
                            },
                        }));
                    }
                }
            },
            refreshStrictPreset: async () => {
                set({ strictPresetLoading: true });
                try {
                    const preset = await fetchStrictModePreset();
                    set((s) => ({
                        strictPreset: preset,
                        strictPresetLoading: false,
                        ...(s.evaluationMode === 'strict'
                            ? {
                                judgeModelIds: preset.judgeModels.map((judge) => judge.id),
                                freeTextJudges: [],
                                selectedTaskIds: preset.taskIds,
                                evalParams: {
                                    ...s.evalParams,
                                    judgeRunCount: preset.judgeRuns,
                                    subjectTemperature: preset.subjectTemperature,
                                    judgeTemperature: preset.judgeTemperature,
                                },
                            }
                            : {}),
                    }));
                } catch {
                    set({ strictPresetLoading: false });
                }
            },
            evalParams: {
                judgeRunCount: 3,
                subjectRunCount: 1,
                subjectTemperature: 0.7,
                judgeTemperature: 0.0,
            },
            setJudgeRunCount: (n) => set((s) => ({
                evalParams: {
                    ...s.evalParams,
                    judgeRunCount: s.evaluationMode === 'strict' && s.strictPreset ? s.strictPreset.judgeRuns : n,
                },
            })),
            setSubjectRunCount: (n) => set((s) => ({
                evalParams: {
                    ...s.evalParams,
                    // intent: DEC-005 — clamp 1–5（strict でも独立ノブ）
                    subjectRunCount: Math.min(5, Math.max(1, Math.round(n))),
                },
            })),
            setSubjectTemperature: (t) => set((s) => ({
                evalParams: {
                    ...s.evalParams,
                    subjectTemperature: s.evaluationMode === 'strict' && s.strictPreset ? s.strictPreset.subjectTemperature : t,
                },
            })),

            // --- Tasks ---
            tasks: [],
            tasksLoading: false,
            selectedTaskIds: [],
            taskToolModeOverrides: {},
            toggleTask: (id) => {
                if (get().evaluationMode === 'strict') return;
                const ids = get().selectedTaskIds;
                set({ selectedTaskIds: ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id] });
            },
            selectAllTasks: () => {
                if (get().evaluationMode === 'strict') return;
                set((s) => ({ selectedTaskIds: s.tasks.map((t) => t.id) }));
            },
            deselectAllTasks: () => {
                if (get().evaluationMode === 'strict') return;
                set({ selectedTaskIds: [] });
            },

            setTaskToolMode: (taskId, mode) =>
                set((s) => ({ taskToolModeOverrides: { ...s.taskToolModeOverrides, [taskId]: mode } })),

            refreshTasks: async () => {
                set({ tasksLoading: true });
                try {
                    const tasks = await fetchTasks();
                    set({ tasks, tasksLoading: false });
                } catch {
                    set({ tasksLoading: false });
                }
            },

            // --- Holistic ---
            runHolistic: true,
            setRunHolistic: (v) => set({ runHolistic: v }),

            // --- Exclude unreliable judges ---
            // intent: DEC-003 (Core/exclude-unreliable-judges) — default OFF
            excludeUnreliableJudges: false,
            setExcludeUnreliableJudges: (v) => set({ excludeUnreliableJudges: v }),

            // --- Parallel execution ---
            subjectParallel: true,
            judgeParallel: true,
            setSubjectParallel: (v) => set({ subjectParallel: v }),
            setJudgeParallel: (v) => set({ judgeParallel: v }),

            // --- Named execution presets ---
            executionPresets: [],
            saveExecutionPreset: (name) => {
                const normalizedName = name.trim();
                if (!normalizedName) return null;
                if (get().executionPresets.some((preset) => preset.name === normalizedName)) {
                    return null;
                }

                const state = get();
                const timestamp = new Date().toISOString();
                const id = createExecutionPresetId();
                const preset = createExecutionPreset(
                    id,
                    normalizedName,
                    timestamp,
                    captureExecutionPresetConfig({
                        subjectModelId: state.subjectModelId,
                        judgeModelIds: state.judgeModelIds,
                        freeTextSubject: state.freeTextSubject,
                        freeTextJudges: state.freeTextJudges,
                        holisticJudgeModelIds: state.holisticJudgeModelIds,
                        freeTextHolisticJudges: state.freeTextHolisticJudges,
                        tasks: state.tasks,
                        selectedTaskIds: state.selectedTaskIds,
                        runHolistic: state.runHolistic,
                        excludeUnreliableJudges: state.excludeUnreliableJudges,
                        judgeRunCount: state.evalParams.judgeRunCount,
                        subjectRunCount: state.evalParams.subjectRunCount,
                        subjectTemperature: state.evalParams.subjectTemperature,
                    }),
                );
                set((current) => ({
                    executionPresets: [...current.executionPresets, preset],
                }));
                return id;
            },
            overwriteExecutionPreset: (id) => {
                const state = get();
                const existing = state.executionPresets.find((preset) => preset.id === id);
                if (!existing) return false;
                const config = captureExecutionPresetConfig({
                    subjectModelId: state.subjectModelId,
                    judgeModelIds: state.judgeModelIds,
                    freeTextSubject: state.freeTextSubject,
                    freeTextJudges: state.freeTextJudges,
                    holisticJudgeModelIds: state.holisticJudgeModelIds,
                    freeTextHolisticJudges: state.freeTextHolisticJudges,
                    tasks: state.tasks,
                    selectedTaskIds: state.selectedTaskIds,
                    runHolistic: state.runHolistic,
                    excludeUnreliableJudges: state.excludeUnreliableJudges,
                    judgeRunCount: state.evalParams.judgeRunCount,
                    subjectRunCount: state.evalParams.subjectRunCount,
                    subjectTemperature: state.evalParams.subjectTemperature,
                });
                set((current) => ({
                    executionPresets: current.executionPresets.map((preset) =>
                        preset.id === id
                            ? overwriteExecutionPresetConfig(
                                preset,
                                config,
                                new Date().toISOString(),
                            )
                            : preset,
                    ),
                }));
                return true;
            },
            loadExecutionPreset: (id) => {
                const state = get();
                const preset = state.executionPresets.find((candidate) => candidate.id === id);
                if (!preset) return false;
                if (preset.schemaVersion !== EXECUTION_PRESET_SCHEMA_VERSION) {
                    console.warn('[execution-preset] unsupported schema version', {
                        presetId: preset.id,
                        schemaVersion: preset.schemaVersion,
                    });
                    return false;
                }

                const resolved = resolveExecutionPresetConfig(
                    preset.config,
                    state.availableModels,
                    state.tasks,
                );
                if (resolved.missingModelIds.length > 0) {
                    console.warn('[execution-preset] ignored unavailable models', {
                        presetId: preset.id,
                        modelIds: resolved.missingModelIds,
                    });
                }
                if (resolved.missingTaskIds.length > 0) {
                    console.warn('[execution-preset] ignored unavailable tasks', {
                        presetId: preset.id,
                        taskIds: resolved.missingTaskIds,
                    });
                }

                set((current) => ({
                    evaluationMode: 'standard',
                    subjectModelId: resolved.subjectModelId,
                    judgeModelIds: resolved.judgeModelIds,
                    freeTextSubject: resolved.freeTextSubject,
                    freeTextJudges: resolved.freeTextJudges,
                    holisticJudgeModelIds: resolved.holisticJudgeModelIds,
                    freeTextHolisticJudges: resolved.freeTextHolisticJudges,
                    selectedTaskIds: resolved.selectedTaskIds,
                    runHolistic: resolved.runHolistic,
                    excludeUnreliableJudges: resolved.excludeUnreliableJudges,
                    evalParams: {
                        ...current.evalParams,
                        judgeRunCount: resolved.judgeRunCount,
                        subjectRunCount: resolved.subjectRunCount,
                        subjectTemperature: resolved.subjectTemperature,
                    },
                }));
                return true;
            },
            deleteExecutionPreset: (id) => {
                set((state) => ({
                    executionPresets: state.executionPresets.filter((preset) => preset.id !== id),
                }));
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
                holisticJudgeModelIds: state.holisticJudgeModelIds,
                freeTextHolisticJudges: state.freeTextHolisticJudges,
                evaluationMode: state.evaluationMode,
                evalParams: state.evalParams,
                selectedTaskIds: state.selectedTaskIds,
                taskToolModeOverrides: state.taskToolModeOverrides,
                runHolistic: state.runHolistic,
                excludeUnreliableJudges: state.excludeUnreliableJudges,
                subjectParallel: state.subjectParallel,
                judgeParallel: state.judgeParallel,
                executionPresets: state.executionPresets,
            }),
            merge: (persisted, current) => {
                const p = (persisted || {}) as Partial<SettingsState>;
                const evalParams = {
                    ...current.evalParams,
                    ...(p.evalParams || {}),
                    subjectRunCount: Math.min(
                        5,
                        Math.max(1, Math.round(p.evalParams?.subjectRunCount ?? 1)),
                    ),
                };
                return {
                    ...current,
                    ...p,
                    evalParams,
                };
            },
        }
    )
);
