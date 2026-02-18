import { create } from 'zustand';
import type { RunStatus, RunProgress, EvaluationRun } from '../types';

interface RunState {
    status: RunStatus;
    progress: RunProgress | null;
    result: EvaluationRun | null;
    resultFilePath: string | null;
    runId: string | null;
    cancelRequested: boolean;
    errorMessage: string | null;

    startRun: (totalSteps: number) => void;
    setRunId: (runId: string) => void;
    updateProgress: (update: Partial<RunProgress> & { totalSteps?: number }) => void;
    completeRun: (result: EvaluationRun, savedPath?: string) => void;
    cancelRun: () => void;
    requestCancel: () => void;
    reset: () => void;
    setResult: (result: EvaluationRun | null) => void;
    setError: (message: string) => void;
}

export const useRunStore = create<RunState>((set) => ({
    status: 'idle',
    progress: null,
    result: null,
    resultFilePath: null,
    runId: null,
    cancelRequested: false,
    errorMessage: null,

    startRun: (totalSteps) =>
        set({
            status: 'running',
            cancelRequested: false,
            errorMessage: null,
            runId: null,
            progress: {
                currentStep: 0,
                totalSteps,
                currentTaskIndex: 0,
                currentTaskId: '',
                currentJudgeModel: '',
                elapsedMs: 0,
            },
            result: null,
            resultFilePath: null,
        }),

    setRunId: (runId) => set({ runId }),

    updateProgress: (update) =>
        set((s) => ({
            progress: s.progress
                ? { ...s.progress, ...update }
                : {
                    currentStep: update.currentStep ?? 0,
                    totalSteps: update.totalSteps ?? 0,
                    currentTaskIndex: update.currentTaskIndex ?? 0,
                    currentTaskId: update.currentTaskId ?? '',
                    currentJudgeModel: update.currentJudgeModel ?? '',
                    elapsedMs: update.elapsedMs ?? 0,
                },
        })),

    completeRun: (result, savedPath) =>
        set({
            status: 'completed',
            result,
            resultFilePath: savedPath ?? null,
        }),

    cancelRun: () => set({ status: 'cancelled' }),

    requestCancel: () => set({ cancelRequested: true }),

    reset: () =>
        set({
            status: 'idle',
            progress: null,
            result: null,
            resultFilePath: null,
            runId: null,
            cancelRequested: false,
            errorMessage: null,
        }),

    setResult: (result) => set({ result }),

    setError: (message) =>
        set({
            status: 'error',
            errorMessage: message,
        }),
}));
