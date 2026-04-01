/**
 * API クライアント — server.py との通信層
 *
 * 責務:
 *  - fetch ラッパー
 *  - snake_case → camelCase 変換
 *  - /api/models のネスト構造 → Model[] フラット化
 *  - 結果データ (benchmark_result) → EvaluationRun 変換
 */

import type {
    Provider,
    Model,
    Task,
    EvaluationRun,
    StrictModePreset,
    TaskResult,
    JudgeEvaluation,
    AxisScore,
    TaskType,
} from '../types';

// ---------------------------------------------------------------------------
// Base fetch
// ---------------------------------------------------------------------------

const BASE = '/api';

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${BASE}${path}`, {
        ...init,
        headers: {
            'Content-Type': 'application/json',
            ...init?.headers,
        },
    });
    if (!res.ok) {
        const body = await res.text();
        throw new Error(`API ${res.status}: ${body}`);
    }
    return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------

export async function fetchTasks(): Promise<Task[]> {
    const raw = await apiFetch<Array<{ id: string; type: string; prompt_preview: string }>>('/tasks');
    return raw.map((t) => ({
        id: t.id,
        type: t.type as TaskType,
        promptPreview: t.prompt_preview,
    }));
}

// ---------------------------------------------------------------------------
// API Keys
// ---------------------------------------------------------------------------

export interface KeyStatus {
    openai: boolean;
    anthropic: boolean;
    gemini: boolean;
    openrouter: boolean;
}

export async function fetchKeyStatus(): Promise<KeyStatus> {
    return apiFetch<KeyStatus>('/keys/status');
}

export async function saveKey(
    provider: Provider,
    key: string,
): Promise<void> {
    await apiFetch<{ status: string }>('/keys', {
        method: 'POST',
        body: JSON.stringify({ [provider]: key }),
    });
}

export async function deleteKey(provider: Provider): Promise<void> {
    await apiFetch<{ status: string }>('/keys', {
        method: 'DELETE',
        body: JSON.stringify({ [provider]: true }),
    });
}

export interface OpenRouterAdminStatus {
    configured: boolean;
}

export interface OpenRouterCredits {
    configured: boolean;
    totalCredits?: number | null;
    totalUsage?: number | null;
    remainingCredits?: number | null;
}

export async function fetchOpenRouterAdminStatus(): Promise<OpenRouterAdminStatus> {
    return apiFetch<OpenRouterAdminStatus>('/openrouter/admin/status');
}

export async function saveOpenRouterAdminKey(key: string): Promise<void> {
    await apiFetch<{ status: string }>('/openrouter/admin/key', {
        method: 'POST',
        body: JSON.stringify({ key }),
    });
}

export async function deleteOpenRouterAdminKey(): Promise<void> {
    await apiFetch<{ status: string }>('/openrouter/admin/key', {
        method: 'DELETE',
    });
}

interface RawOpenRouterCredits {
    configured: boolean;
    total_credits?: number | null;
    total_usage?: number | null;
    remaining_credits?: number | null;
}

export async function fetchOpenRouterCredits(): Promise<OpenRouterCredits> {
    const raw = await apiFetch<RawOpenRouterCredits>('/openrouter/credits');
    return {
        configured: raw.configured,
        totalCredits: raw.total_credits,
        totalUsage: raw.total_usage,
        remainingCredits: raw.remaining_credits,
    };
}

// ---------------------------------------------------------------------------
// Models — flatten nested structure → Model[]
// ---------------------------------------------------------------------------

interface RawModelsResponse {
    providers: Record<string, { models: string[] }>;
    updated_at: string | null;
    errors: string[];
    missing_keys: string[];
}

export interface ModelsResult {
    models: Model[];
    updatedAt: string | null;
    errors: string[];
    missingKeys: string[];
}

const PROVIDER_MAP: Record<string, Provider> = {
    openai: 'openai',
    anthropic: 'anthropic',
    gemini: 'gemini',
    openrouter: 'openrouter',
};

export async function fetchModels(force = false): Promise<ModelsResult> {
    const raw = await apiFetch<RawModelsResponse>(`/models${force ? '?force=true' : ''}`);
    const models: Model[] = [];
    for (const [providerKey, data] of Object.entries(raw.providers || {})) {
        const provider = PROVIDER_MAP[providerKey];
        if (!provider) continue;
        for (const name of data.models || []) {
            models.push({ id: name, name, provider });
        }
    }
    return {
        models,
        updatedAt: raw.updated_at ?? null,
        errors: raw.errors ?? [],
        missingKeys: raw.missing_keys ?? [],
    };
}

// ---------------------------------------------------------------------------
// Strict Mode
// ---------------------------------------------------------------------------

interface RawStrictModePreset {
    id: string;
    label: string;
    description: string;
    subject_model_policy: 'variable';
    judge_models: Array<{
        id: string;
        label: string;
        provider: Provider;
    }>;
    task_ids: string[];
    judge_runs: number;
    subject_temperature: number;
    judge_temperature: number;
}

export async function fetchStrictModePreset(): Promise<StrictModePreset> {
    const raw = await apiFetch<RawStrictModePreset>('/strict-mode/preset');
    return {
        id: raw.id,
        label: raw.label,
        description: raw.description,
        subjectModelPolicy: raw.subject_model_policy,
        judgeModels: raw.judge_models,
        taskIds: raw.task_ids,
        judgeRuns: raw.judge_runs,
        subjectTemperature: raw.subject_temperature,
        judgeTemperature: raw.judge_temperature,
    };
}

// ---------------------------------------------------------------------------
// Results — list summaries
// ---------------------------------------------------------------------------

interface RawResultSummary {
    filename: string;
    filepath: string;
    target_model: string;
    executed_at: string;
    execution_duration_ms?: number;
    estimated_cost_usd?: number;
    cost_estimate_status?: 'available' | 'partial' | 'unavailable';
    subject_total_tokens?: number;
    subject_estimated_cost_usd?: number;
    subject_cost_per_1m_tokens_usd?: number;
    strict_mode_requested?: boolean;
    strict_mode_enforced?: boolean;
    strict_mode_eligible?: boolean;
    strict_mode_preset_id?: string | null;
    strict_mode_preset_label?: string | null;
    strict_mode_profile_id?: string | null;
    strict_mode_profile_label?: string | null;
    task_count: number;
    judge_count: number;
    avg_score: number;
    max_score: number;
    min_score: number;
    run_id: string;
}

export interface ResultSummary {
    filename: string;
    targetModel: string;
    executedAt: string;
    executionDurationMs?: number;
    estimatedCostUsd?: number;
    costEstimateStatus?: 'available' | 'partial' | 'unavailable';
    subjectTotalTokens?: number;
    subjectEstimatedCostUsd?: number;
    subjectCostPer1mTokensUsd?: number;
    strictModeRequested?: boolean;
    strictModeEnforced?: boolean;
    strictModeEligible?: boolean;
    strictModePresetId?: string | null;
    strictModePresetLabel?: string | null;
    strictModeProfileId?: string | null;
    strictModeProfileLabel?: string | null;
    taskCount: number;
    judgeCount: number;
    avgScore: number;
    maxScore: number;
    minScore: number;
    runId: string;
}

export async function fetchResultSummaries(): Promise<ResultSummary[]> {
    const raw = await apiFetch<RawResultSummary[]>('/results');
    return raw.map((r) => ({
        filename: r.filename,
        targetModel: r.target_model,
        executedAt: r.executed_at,
        executionDurationMs: r.execution_duration_ms,
        estimatedCostUsd: r.estimated_cost_usd,
        costEstimateStatus: r.cost_estimate_status,
        subjectTotalTokens: r.subject_total_tokens,
        subjectEstimatedCostUsd: r.subject_estimated_cost_usd,
        subjectCostPer1mTokensUsd: r.subject_cost_per_1m_tokens_usd,
        strictModeRequested: r.strict_mode_requested,
        strictModeEnforced: r.strict_mode_enforced,
        strictModeEligible: r.strict_mode_eligible,
        strictModePresetId: r.strict_mode_preset_id,
        strictModePresetLabel: r.strict_mode_preset_label,
        strictModeProfileId: r.strict_mode_profile_id,
        strictModeProfileLabel: r.strict_mode_profile_label,
        taskCount: r.task_count,
        judgeCount: r.judge_count,
        avgScore: r.avg_score,
        maxScore: r.max_score,
        minScore: r.min_score,
        runId: r.run_id,
    }));
}

// ---------------------------------------------------------------------------
// Results — detail → EvaluationRun
// ---------------------------------------------------------------------------

/**
 * server.py の benchmark_result をフロントエンドの EvaluationRun に変換する。
 *
 * server.py 構造:
 *   { run_id, target_model, judge_models: string[], judge_runs, executed_at,
 *     tasks: TaskData[], cancelled, completed_tasks, total_tasks,
 *     average_score, best_score }
 *
 * TaskData:
 *   { task_name, task_type, input_prompt, response,
 *     judge_results: Record<judge_model, { runs: Run[], aggregated: Agg }> }
 */

interface RawBenchmarkResult {
    run_id: string;
    target_model: string;
    judge_models: string[];
    judge_runs: number;
    executed_at: string;
    execution_duration_ms?: number;
    estimated_cost_usd?: number;
    cost_estimate_status?: 'available' | 'partial' | 'unavailable';
    strict_mode?: {
        version?: string;
        requested?: boolean;
        enforced?: boolean;
        eligible?: boolean;
        preset_id?: string | null;
        preset_label?: string | null;
        profile_id?: string | null;
        profile_label?: string | null;
        reasons?: string[];
    };
    usage_summary?: {
        totals?: {
            total_tokens?: number;
            estimated_cost_usd?: number;
        };
    };
    tasks: RawTaskData[];
    cancelled: boolean;
    completed_tasks: number;
    total_tasks: number;
    average_score: number;
    best_score: number;
}

interface RawTaskData {
    task_name: string;
    task_type: string;
    input_prompt: string;
    response: string;
    subject_usage?: {
        model?: string;
        provider?: string;
        total_tokens?: number;
        input_tokens?: number;
        output_tokens?: number;
        estimated_cost_usd?: number;
    };
    judge_results: Record<string, RawJudgeResult>;
}

interface RawJudgeRun {
    score: Record<string, unknown>;
    total_score: number;
    confidence: string;
    critical_fail: boolean;
    reasoning: unknown;
}

interface RawAggregated {
    logic_and_fact_mean: number;
    logic_and_fact_std: number;
    constraint_adherence_mean: number;
    constraint_adherence_std: number;
    helpfulness_mean: number;
    helpfulness_std: number;
    total_score_mean: number;
    total_score_std: number;
    critical_fail: boolean;
    confidence_distribution: { high: number; medium: number; low: number };
}

interface RawJudgeResult {
    runs: RawJudgeRun[];
    aggregated: RawAggregated;
}

function toAxisScore(mean: number, std: number): AxisScore {
    return { mean: Math.round(mean * 10) / 10, sd: Math.round(std * 10) / 10 };
}

function normalizeReasoning(reasoning: unknown): string | null {
    if (typeof reasoning === 'string') {
        return reasoning;
    }
    if (reasoning && typeof reasoning === 'object') {
        const entries = Object.entries(reasoning as Record<string, unknown>)
            .filter(([, value]) => typeof value === 'string' && value)
            .map(([key, value]) => `${key}: ${value as string}`);
        return entries.length > 0 ? entries.join('\n\n') : JSON.stringify(reasoning, null, 2);
    }
    return null;
}

function convertJudgeResult(judgeModel: string, raw: RawJudgeResult): JudgeEvaluation {
    const agg = raw.aggregated;
    return {
        judgeModelId: judgeModel,
        judgeModelName: judgeModel,
        logicAndFact: toAxisScore(agg.logic_and_fact_mean, agg.logic_and_fact_std),
        constraintAdherence: toAxisScore(agg.constraint_adherence_mean, agg.constraint_adherence_std),
        helpfulness: toAxisScore(agg.helpfulness_mean, agg.helpfulness_std),
        totalScore: toAxisScore(agg.total_score_mean, agg.total_score_std),
        confidenceDistribution: agg.confidence_distribution ?? { high: 0, medium: 0, low: 0 },
        criticalFail: {
            detected: agg.critical_fail ?? false,
            reason: '',  // server.py にはない → 空文字フォールバック
        },
        reasoningSamples: (raw.runs || [])
            .map((r) => normalizeReasoning(r.reasoning))
            .filter((value): value is string => Boolean(value)),
    };
}

function convertTask(raw: RawTaskData): TaskResult {
    const evaluations: JudgeEvaluation[] = [];
    for (const [judgeModel, judgeResult] of Object.entries(raw.judge_results || {})) {
        evaluations.push(convertJudgeResult(judgeModel, judgeResult));
    }
    return {
        taskId: raw.task_name,
        taskType: (raw.task_type || 'fact') as TaskType,
        subjectResponse: raw.response || '',
        judgeEvaluations: evaluations,
    };
}

export function convertBenchmarkResult(raw: RawBenchmarkResult): EvaluationRun {
    const subjectTotalTokens = (raw.tasks || []).reduce(
        (sum, task) => sum + Number(task.subject_usage?.total_tokens || 0),
        0,
    );
    const subjectEstimatedCostUsd = (raw.tasks || []).reduce(
        (sum, task) => sum + Number(task.subject_usage?.estimated_cost_usd || 0),
        0,
    );
    const subjectCostPer1mTokensUsd = subjectTotalTokens > 0 && subjectEstimatedCostUsd > 0
        ? Number(((subjectEstimatedCostUsd / subjectTotalTokens) * 1_000_000).toFixed(6))
        : undefined;

    return {
        id: raw.run_id,
        subjectModelId: raw.target_model,
        subjectModelName: raw.target_model,
        judgeModels: (raw.judge_models || []).map((m) => ({ id: m, name: m })),
        timestamp: raw.executed_at,
        executionDurationMs: raw.execution_duration_ms,
        estimatedCostUsd: raw.estimated_cost_usd,
        costEstimateStatus: raw.cost_estimate_status,
        subjectTotalTokens,
        subjectEstimatedCostUsd: subjectEstimatedCostUsd > 0 ? subjectEstimatedCostUsd : undefined,
        subjectCostPer1mTokensUsd,
        strictMode: raw.strict_mode ? {
            version: raw.strict_mode.version,
            requested: Boolean(raw.strict_mode.requested),
            enforced: Boolean(raw.strict_mode.enforced),
            eligible: Boolean(raw.strict_mode.eligible),
            presetId: raw.strict_mode.preset_id,
            presetLabel: raw.strict_mode.preset_label,
            profileId: raw.strict_mode.profile_id,
            profileLabel: raw.strict_mode.profile_label,
            reasons: raw.strict_mode.reasons ?? [],
        } : undefined,
        taskResults: (raw.tasks || []).map(convertTask),
        averageScore: raw.average_score ?? 0,
        bestScore: raw.best_score ?? 0,
        taskCount: raw.completed_tasks ?? raw.tasks?.length ?? 0,
    };
}

export async function fetchResultDetail(filename: string): Promise<EvaluationRun> {
    const raw = await apiFetch<RawBenchmarkResult>(`/results/${filename}`);
    return convertBenchmarkResult(raw);
}

export async function deleteResult(filename: string): Promise<{ status: string; filename: string; run_id: string }> {
    return apiFetch<{ status: string; filename: string; run_id: string }>(`/results/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
    });
}

// ---------------------------------------------------------------------------
// Run — start benchmark (returns SSE URL info for sse.ts)
// ---------------------------------------------------------------------------

export interface RunParams {
    targetModel: string;
    judgeModels: string[];
    selectedTaskIds: string[];
    judgeRuns: number;
    subjectTemp: number;
    strictMode: boolean;
    strictPresetId?: string | null;
}

export function buildRunRequestBody(params: RunParams): string {
    return JSON.stringify({
        target_model: params.targetModel,
        judge_models: params.judgeModels,
        selected_task_ids: params.selectedTaskIds,
        judge_runs: params.judgeRuns,
        subject_temp: params.subjectTemp,
        strict_mode: params.strictMode,
        strict_preset_id: params.strictPresetId ?? null,
    });
}

export async function cancelRun(runId: string): Promise<void> {
    await apiFetch<{ status: string }>(`/run/cancel?run_id=${encodeURIComponent(runId)}`, {
        method: 'POST',
    });
}
