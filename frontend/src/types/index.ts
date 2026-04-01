// === Providers ===
export type Provider = 'openai' | 'anthropic' | 'gemini' | 'openrouter';

export const PROVIDER_LABELS: Record<Provider, string> = {
    openai: 'OpenAI',
    anthropic: 'Anthropic',
    gemini: 'Gemini',
    openrouter: 'OpenRouter',
};

export interface ApiKeyEntry {
    provider: Provider;
    key: string;
    isValid: boolean;
    error?: string;
}

// === Models ===
export interface Model {
    id: string;
    name: string;
    provider: Provider;
}

// === Tasks ===
export type TaskType = 'fact' | 'creative' | 'speculative';

export interface Task {
    id: string;
    type: TaskType;
    promptPreview: string;
}

// === Evaluation Parameters ===
export interface EvalParams {
    judgeRunCount: number; // 1-5
    subjectTemperature: number; // 0.0-1.0
    judgeTemperature: number; // fixed 0.0
}

export type EvaluationMode = 'standard' | 'strict';

export interface StrictModePreset {
    id: string;
    label: string;
    description: string;
    subjectModelPolicy: 'variable';
    judgeModels: Array<{
        id: string;
        label: string;
        provider: Provider;
    }>;
    taskIds: string[];
    judgeRuns: number;
    subjectTemperature: number;
    judgeTemperature: number;
}

// === Scores ===
export interface AxisScore {
    mean: number;
    sd: number;
}

export interface JudgeEvaluation {
    judgeModelId: string;
    judgeModelName: string;
    logicAndFact: AxisScore;
    constraintAdherence: AxisScore;
    helpfulness: AxisScore;
    totalScore: AxisScore;
    confidenceDistribution: {
        high: number;
        medium: number;
        low: number;
    };
    criticalFail: {
        detected: boolean;
        reason?: string;
    };
    reasoningSamples: string[];
}

// === Results ===
export interface TaskResult {
    taskId: string;
    taskType: TaskType;
    subjectResponse: string;
    judgeEvaluations: JudgeEvaluation[];
}

export interface StrictModeInfo {
    version?: string;
    requested?: boolean;
    enforced?: boolean;
    eligible: boolean;
    presetId?: string | null;
    presetLabel?: string | null;
    profileId?: string | null;
    profileLabel?: string | null;
    reasons?: string[];
}

export interface EvaluationRun {
    id: string;
    subjectModelId: string;
    subjectModelName: string;
    judgeModels: { id: string; name: string }[];
    timestamp: string;
    executionDurationMs?: number;
    estimatedCostUsd?: number;
    costEstimateStatus?: 'available' | 'partial' | 'unavailable';
    subjectTotalTokens?: number;
    subjectEstimatedCostUsd?: number;
    subjectCostPer1mTokensUsd?: number;
    strictMode?: StrictModeInfo;
    taskResults: TaskResult[];
    averageScore: number;
    bestScore: number;
    taskCount: number;
    /** サマリーから取得した judge 数（詳細ロード前は judgeModels が空のため） */
    judgeCount?: number;
}

// === Run State ===
export type RunStatus = 'idle' | 'running' | 'completed' | 'cancelled' | 'error';

export type RunTaskPhase = 'queued' | 'running_subject' | 'running_judges' | 'completed' | 'failed';
export type RunJudgePhase = 'pending' | 'running' | 'completed' | 'error';

export interface ActiveRunTask {
    taskId: string;
    taskIndex: number;
    phase: RunTaskPhase;
    message: string;
    subjectDone: boolean;
    judgeStates: Record<string, RunJudgePhase>;
    judgeCompletedCount: number;
    judgeErrorCount: number;
    judgeTotalCount: number;
    activeJudges: string[];
}

export interface RunProgress {
    startedAtMs?: number;
    currentStep: number;
    totalSteps: number;
    currentTaskIndex: number;
    currentTaskId: string;
    currentJudgeModel: string;
    elapsedMs: number;
    completedTaskCount: number;
    activeTaskCount: number;
    queuedTaskCount: number;
    completedTasks: ActiveRunTask[];
    activeTasks: ActiveRunTask[];
    queuedTasks: ActiveRunTask[];
}

// === Cross-task summary ===
export interface JudgeSummary {
    judgeModelId: string;
    judgeModelName: string;
    averageScore: number;
    tasksEvaluated: number;
}

export interface ReviewFlag {
    taskId: string;
    judgeModelName: string;
    reasons: string[];
}
