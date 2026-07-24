// === Providers ===
/** registry id または lmstudio。カタログは任意の registry id を返し得る。 */
export type Provider = string;

export type ProviderKind = 'openai_compatible' | 'anthropic';

export type PricingProfile = 'openrouter' | 'openai' | 'anthropic' | 'google' | 'none';

export interface RegistryProvider {
    id: string;
    displayName: string;
    kind: ProviderKind;
    baseUrl?: string;
    pricingProfile: PricingProfile;
    profile?: string;
    builtin: boolean;
    hasKey: boolean;
}

export const PROVIDER_LABELS: Record<string, string> = {
    openrouter: 'OpenRouter',
    lmstudio: 'LM Studio',
    openai: 'OpenAI',
    'google-ai-studio': 'Google AI Studio',
    anthropic: 'Anthropic',
};

export function providerDisplayName(
    providerId: string,
    registry?: RegistryProvider[],
): string {
    const fromRegistry = registry?.find((p) => p.id === providerId)?.displayName;
    if (fromRegistry) return fromRegistry;
    return PROVIDER_LABELS[providerId] ?? providerId;
}

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
export type TaskType = 'fact' | 'creative' | 'speculative' | 'holistic';

export type ToolMode = 'native' | 'text' | 'auto';

export interface Task {
    id: string;
    type: TaskType;
    promptPreview: string;
    toolMode?: ToolMode;
}

// === Evaluation Parameters ===
export interface EvalParams {
    judgeRunCount: number; // 1-5
    /** Subject LLM invocations per task (1-5); independent of judgeRunCount. */
    subjectRunCount: number;
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

export interface ExecutionPresetConfig {
    subjectModel: string | null;
    judgeModels: string[];
    /** Empty means fallback to judgeModels for holistic evaluation. */
    holisticJudgeModels: string[];
    taskSelections: Record<string, boolean>;
    runHolistic: boolean;
    /** Exclude unreliable judge lineages from hero average; default false on legacy. */
    excludeUnreliableJudges?: boolean;
    judgeRunCount: number;
    /** Subject LLM runs per task; omitted on legacy presets → resolve as 1. */
    subjectRunCount?: number;
    subjectTemperature: number;
}

export interface ExecutionPreset {
    id: string;
    name: string;
    schemaVersion: 1;
    createdAt: string;
    updatedAt: string;
    config: ExecutionPresetConfig;
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
    /** API thinking / model-internal reasoning (not scoring rationale) */
    apiReasoningSamples: string[];
}

export interface ToolTraceStep {
    stepIndex: number;
    toolName: string;
    arguments: Record<string, unknown>;
    resultSummary: string;
    resultDetail: string;
    ok: boolean;
}

/** Per subject-LLM attempt within a task (list-eval multi-run). */
export interface SubjectRunRecord {
    runIndex: number;
    response: string;
    subjectUsage: SubjectUsage | null;
    toolTrace: ToolTraceStep[];
    error: string | null;
}

export interface UsageSummaryCall {
    provider: string;
    model: string;
    callCount: number;
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
    cacheCreationInputTokens: number;
    cacheReadInputTokens: number;
    estimatedCostUsd: number | null;
    pricedCallCount: number;
    unpricedCallCount: number;
    pricingSource: string | null;
    durationMs: number;
}

export interface UsageSummary {
    calls: UsageSummaryCall[];
    totals: {
        callCount: number;
        inputTokens: number;
        outputTokens: number;
        totalTokens: number;
        cacheCreationInputTokens: number;
        cacheReadInputTokens: number;
        estimatedCostUsd: number | null;
        pricedCallCount: number;
        unpricedCallCount: number;
        pricingStatus: 'available' | 'partial' | 'unavailable';
        unpricedModels: string[];
        totalDurationMs: number;
    };
}

export interface SubjectUsage {
    provider: string;
    model: string;
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
    estimatedCostUsd?: number | null;
}

/** Per-task subject / judge processing time (usage duration_ms aggregate). */
export interface TaskTiming {
    subjectDurationMs: number;
    judgeDurationMs: number;
}

/** Run-level sum of usual-task task_timing (DEC-002 Core/time-roi-task-timing). */
export interface TimingSummary {
    subjectDurationMs: number;
    judgeDurationMs: number;
    totalDurationMs: number;
}

// === Results ===
export interface TaskResult {
    taskId: string;
    taskType: TaskType;
    inputPrompt: string;
    subjectPrompt: string;
    subjectResponse: string;
    subjectUsage: SubjectUsage | null;
    /** Multi-run subject attempts; empty/absent on legacy single-response results. */
    subjectRuns?: SubjectRunRecord[];
    subjectRunCount?: number;
    judgeEvaluations: JudgeEvaluation[];
    toolTrace: ToolTraceStep[];
    /** Subject tools were configured for this task (even if unused). */
    hasSubjectTools: boolean;
    /** Per-task duration breakdown; absent on legacy saved results. */
    taskTiming?: TaskTiming;
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

/** Backend score_aggregation payload (DEC-003/004). */
export interface ExcludedJudgeInfo {
    judgeId: string;
    reasons: string[];
}

export interface ScoreAggregation {
    averageScoreBefore: number | null;
    averageScoreAfter: number | null;
    bestScoreBefore: number | null;
    bestScoreAfter: number | null;
    excludedJudges: ExcludedJudgeInfo[];
    includedJudges: string[];
    allExcluded: boolean;
    unreliableCandidates: ExcludedJudgeInfo[];
}

export interface EvaluationRun {
    id: string;
    subjectModelId: string;
    subjectModelName: string;
    judgeModels: { id: string; name: string }[];
    /** Judges used for holistic phase; empty when holistic did not run. */
    holisticJudgeModels?: { id: string; name: string }[];
    timestamp: string;
    executionDurationMs?: number;
    /** Usual-task task_timing totals; absent on legacy runs → time ROI N/A. */
    timingSummary?: TimingSummary;
    estimatedCostUsd?: number;
    costEstimateStatus?: 'available' | 'partial' | 'unavailable';
    subjectTotalTokens?: number;
    subjectEstimatedCostUsd?: number;
    subjectCostPer1mTokensUsd?: number;
    strictMode?: StrictModeInfo;
    taskResults: TaskResult[];
    holisticTaskResults: TaskResult[];
    /** Hero average; null when exclude-ON and all judges excluded (INV-001). */
    averageScore: number | null;
    bestScore: number | null;
    /** Run-time toggle; absent/false on legacy JSON. */
    excludeUnreliableJudges?: boolean;
    scoreAggregation?: ScoreAggregation;
    taskCount: number;
    usageSummary?: UsageSummary;
    usageSummarySubject?: UsageSummary;
    usageSummaryJudge?: UsageSummary;
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
    taskKind: 'standard' | 'holistic';
    phase: RunTaskPhase;
    message: string;
    subjectDone: boolean;
    judgeStates: Record<string, RunJudgePhase>;
    judgeCompletedCount: number;
    judgeErrorCount: number;
    judgeTotalCount: number;
    activeJudges: string[];
}

export type HolisticRunStatus = 'started' | 'running' | 'completed';

export interface HolisticRunProgress {
    status: HolisticRunStatus;
    completedTaskCount: number;
    failedTaskCount: number;
    totalTaskCount: number;
    currentTaskIndex: number | null;
    currentTaskId: string;
    message: string;
}

export type EtaStatus =
    | 'measured'
    | 'history_blend'
    | 'history'
    | 'step_fallback'
    | 'unavailable';

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
    /** Remaining-time estimate in ms; null when unavailable. */
    etaMs?: number | null;
    /** intent: DEC-003 — distinguish measured vs step fallback vs unavailable. */
    etaStatus?: EtaStatus;
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
