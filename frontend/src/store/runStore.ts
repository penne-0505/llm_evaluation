import { create } from 'zustand';
import type { RunStatus, RunProgress, EvaluationRun, HolisticRunProgress } from '../types';

/** intent: DEC-001 (Core/concurrent-evaluation-jobs) — 同時上限 3 */
export const MAX_CONCURRENT_JOBS = 3;

export interface RunJob {
    jobId: string;
    label: string;
    status: RunStatus;
    progress: RunProgress | null;
    holisticProgress: HolisticRunProgress | null;
    result: EvaluationRun | null;
    resultFilePath: string | null;
    runId: string | null;
    cancelRequested: boolean;
    errorMessage: string | null;
}

function createEmptyProgress(totalSteps: number): RunProgress {
    return {
        startedAtMs: Date.now(),
        currentStep: 0,
        totalSteps,
        currentTaskIndex: 0,
        currentTaskId: '',
        currentJudgeModel: '',
        elapsedMs: 0,
        completedTaskCount: 0,
        activeTaskCount: 0,
        queuedTaskCount: 0,
        completedTasks: [],
        activeTasks: [],
        queuedTasks: [],
        etaMs: null,
        etaStatus: 'unavailable',
    };
}

function patchJob(
    jobs: RunJob[],
    jobId: string,
    patch: Partial<RunJob> | ((job: RunJob) => Partial<RunJob>),
): RunJob[] {
    return jobs.map((job) => {
        if (job.jobId !== jobId) return job;
        const next = typeof patch === 'function' ? patch(job) : patch;
        return { ...job, ...next };
    });
}

interface RunState {
    jobs: RunJob[];

    runningCount: () => number;
    canStartAnother: () => boolean;

    startJob: (jobId: string, label: string, totalSteps: number) => void;
    setJobRunId: (jobId: string, runId: string) => void;
    updateJobProgress: (
        jobId: string,
        update: Partial<RunProgress> & { totalSteps?: number },
    ) => void;
    updateJobHolisticProgress: (jobId: string, update: HolisticRunProgress) => void;
    completeJob: (jobId: string, result: EvaluationRun, savedPath?: string) => void;
    cancelJob: (jobId: string) => void;
    requestJobCancel: (jobId: string) => void;
    setJobError: (jobId: string, message: string) => void;
    dismissJob: (jobId: string) => void;
    resetAll: () => void;

    /**
     * 後方互換: 単一ジョブ時代の API。
     * 最新ジョブ（末尾）を対象にする。ジョブが無ければ idle 相当。
     */
    status: RunStatus;
    progress: RunProgress | null;
    holisticProgress: HolisticRunProgress | null;
    result: EvaluationRun | null;
    resultFilePath: string | null;
    runId: string | null;
    cancelRequested: boolean;
    errorMessage: string | null;
    startRun: (totalSteps: number) => void;
    setRunId: (runId: string) => void;
    updateProgress: (update: Partial<RunProgress> & { totalSteps?: number }) => void;
    updateHolisticProgress: (update: HolisticRunProgress) => void;
    completeRun: (result: EvaluationRun, savedPath?: string) => void;
    cancelRun: () => void;
    requestCancel: () => void;
    reset: () => void;
    setResult: (result: EvaluationRun | null) => void;
    clearResult: () => void;
    setError: (message: string) => void;
}

function syncLegacy(jobs: RunJob[]): Pick<
    RunState,
    | 'status'
    | 'progress'
    | 'holisticProgress'
    | 'result'
    | 'resultFilePath'
    | 'runId'
    | 'cancelRequested'
    | 'errorMessage'
> {
    const latest = jobs.length > 0 ? jobs[jobs.length - 1] : null;
    if (!latest) {
        return {
            status: 'idle',
            progress: null,
            holisticProgress: null,
            result: null,
            resultFilePath: null,
            runId: null,
            cancelRequested: false,
            errorMessage: null,
        };
    }
    return {
        status: latest.status,
        progress: latest.progress,
        holisticProgress: latest.holisticProgress,
        result: latest.result,
        resultFilePath: latest.resultFilePath,
        runId: latest.runId,
        cancelRequested: latest.cancelRequested,
        errorMessage: latest.errorMessage,
    };
}

let legacyJobSeq = 0;

export const useRunStore = create<RunState>((set, get) => ({
    jobs: [],
    status: 'idle',
    progress: null,
    holisticProgress: null,
    result: null,
    resultFilePath: null,
    runId: null,
    cancelRequested: false,
    errorMessage: null,

    runningCount: () => get().jobs.filter((j) => j.status === 'running').length,

    canStartAnother: () => get().runningCount() < MAX_CONCURRENT_JOBS,

    startJob: (jobId, label, totalSteps) =>
        set((s) => {
            const running = s.jobs.filter((j) => j.status === 'running').length;
            if (running >= MAX_CONCURRENT_JOBS) {
                return s;
            }
            const job: RunJob = {
                jobId,
                label,
                status: 'running',
                cancelRequested: false,
                errorMessage: null,
                runId: null,
                progress: createEmptyProgress(totalSteps),
                holisticProgress: null,
                result: null,
                resultFilePath: null,
            };
            const jobs = [...s.jobs, job];
            return { jobs, ...syncLegacy(jobs) };
        }),

    setJobRunId: (jobId, runId) =>
        set((s) => {
            const jobs = patchJob(s.jobs, jobId, { runId });
            return { jobs, ...syncLegacy(jobs) };
        }),

    updateJobProgress: (jobId, update) =>
        set((s) => {
            const jobs = patchJob(s.jobs, jobId, (job) => ({
                progress: job.progress
                    ? { ...job.progress, ...update }
                    : createEmptyProgress(update.totalSteps ?? 0),
            }));
            return { jobs, ...syncLegacy(jobs) };
        }),

    updateJobHolisticProgress: (jobId, update) =>
        set((s) => {
            const jobs = patchJob(s.jobs, jobId, { holisticProgress: update });
            return { jobs, ...syncLegacy(jobs) };
        }),

    completeJob: (jobId, result, savedPath) =>
        set((s) => {
            const jobs = patchJob(s.jobs, jobId, {
                status: 'completed',
                result,
                resultFilePath: savedPath ?? null,
            });
            return { jobs, ...syncLegacy(jobs) };
        }),

    cancelJob: (jobId) =>
        set((s) => {
            const jobs = patchJob(s.jobs, jobId, { status: 'cancelled' });
            return { jobs, ...syncLegacy(jobs) };
        }),

    requestJobCancel: (jobId) =>
        set((s) => {
            const jobs = patchJob(s.jobs, jobId, { cancelRequested: true });
            return { jobs, ...syncLegacy(jobs) };
        }),

    setJobError: (jobId, message) =>
        set((s) => {
            const jobs = patchJob(s.jobs, jobId, {
                status: 'error',
                errorMessage: message,
            });
            return { jobs, ...syncLegacy(jobs) };
        }),

    dismissJob: (jobId) =>
        set((s) => {
            const jobs = s.jobs.filter((j) => j.jobId !== jobId);
            return { jobs, ...syncLegacy(jobs) };
        }),

    resetAll: () =>
        set({
            jobs: [],
            ...syncLegacy([]),
        }),

    // ---- legacy single-slot API (operates on latest job) ----
    startRun: (totalSteps) => {
        legacyJobSeq += 1;
        const jobId = `legacy_${legacyJobSeq}`;
        get().startJob(jobId, 'run', totalSteps);
    },

    setRunId: (runId) => {
        const latest = get().jobs[get().jobs.length - 1];
        if (latest) get().setJobRunId(latest.jobId, runId);
    },

    updateProgress: (update) => {
        const latest = get().jobs[get().jobs.length - 1];
        if (latest) get().updateJobProgress(latest.jobId, update);
    },

    updateHolisticProgress: (update) => {
        const latest = get().jobs[get().jobs.length - 1];
        if (latest) get().updateJobHolisticProgress(latest.jobId, update);
    },

    completeRun: (result, savedPath) => {
        const latest = get().jobs[get().jobs.length - 1];
        if (latest) get().completeJob(latest.jobId, result, savedPath);
    },

    cancelRun: () => {
        const latest = get().jobs[get().jobs.length - 1];
        if (latest) get().cancelJob(latest.jobId);
    },

    requestCancel: () => {
        const latest = get().jobs[get().jobs.length - 1];
        if (latest) get().requestJobCancel(latest.jobId);
    },

    reset: () => get().resetAll(),

    setResult: (result) => {
        const latest = get().jobs[get().jobs.length - 1];
        if (!latest) return;
        set((s) => {
            const jobs = patchJob(s.jobs, latest.jobId, { result });
            return { jobs, ...syncLegacy(jobs) };
        });
    },

    clearResult: () => {
        const latest = get().jobs[get().jobs.length - 1];
        if (!latest) return;
        if (latest.status === 'completed') {
            get().dismissJob(latest.jobId);
            return;
        }
        set((s) => {
            const jobs = patchJob(s.jobs, latest.jobId, {
                result: null,
                resultFilePath: null,
            });
            return { jobs, ...syncLegacy(jobs) };
        });
    },

    setError: (message) => {
        const latest = get().jobs[get().jobs.length - 1];
        if (latest) get().setJobError(latest.jobId, message);
    },
}));
