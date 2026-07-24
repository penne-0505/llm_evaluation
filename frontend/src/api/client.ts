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
    ToolMode,
    ToolTraceStep,
    RegistryProvider,
    ProviderKind,
    PricingProfile,
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
    const raw = await apiFetch<Array<{ id: string; type: string; prompt_preview: string; tool_mode?: string }>>('/tasks');
    return raw.map((t) => ({
        id: t.id,
        type: t.type as TaskType,
        promptPreview: t.prompt_preview,
        ...(t.tool_mode ? { toolMode: t.tool_mode as ToolMode } : {}),
    }));
}

// ---------------------------------------------------------------------------
// API Keys / Provider registry
// ---------------------------------------------------------------------------

export interface KeyStatus {
    openrouter: boolean;
    providers?: Record<string, boolean>;
}

export async function fetchKeyStatus(): Promise<KeyStatus> {
    return apiFetch<KeyStatus>('/keys/status');
}

/** 後方互換: openrouter のみ。registry は saveProviderKey を使う。 */
export async function saveKey(
    provider: Provider,
    key: string,
): Promise<void> {
    if (provider === 'openrouter') {
        await apiFetch<{ status: string }>('/keys', {
            method: 'POST',
            body: JSON.stringify({ [provider]: key }),
        });
        return;
    }
    await saveProviderKey(provider, key);
}

export async function deleteKey(provider: Provider): Promise<void> {
    if (provider === 'openrouter') {
        await apiFetch<{ status: string }>('/keys', {
            method: 'DELETE',
            body: JSON.stringify({ [provider]: true }),
        });
        return;
    }
    await deleteProviderKey(provider);
}

interface RawRegistryProvider {
    id: string;
    display_name: string;
    kind: ProviderKind;
    base_url?: string;
    pricing_profile: PricingProfile;
    profile?: string;
    builtin: boolean;
    has_key: boolean;
}

function mapRegistryProvider(raw: RawRegistryProvider): RegistryProvider {
    return {
        id: raw.id,
        displayName: raw.display_name,
        kind: raw.kind,
        baseUrl: raw.base_url,
        pricingProfile: raw.pricing_profile,
        profile: raw.profile,
        builtin: raw.builtin,
        hasKey: raw.has_key,
    };
}

export async function fetchProviders(): Promise<RegistryProvider[]> {
    const raw = await apiFetch<{ providers: RawRegistryProvider[] }>('/providers');
    return (raw.providers || []).map(mapRegistryProvider);
}

export async function createProvider(input: {
    displayName: string;
    kind: ProviderKind;
    baseUrl?: string;
    pricingProfile?: PricingProfile;
}): Promise<RegistryProvider> {
    const raw = await apiFetch<RawRegistryProvider>('/providers', {
        method: 'POST',
        body: JSON.stringify({
            display_name: input.displayName,
            kind: input.kind,
            ...(input.baseUrl ? { base_url: input.baseUrl } : {}),
            ...(input.pricingProfile ? { pricing_profile: input.pricingProfile } : {}),
        }),
    });
    return mapRegistryProvider(raw);
}

export async function updateProvider(
    providerId: string,
    patch: {
        displayName?: string;
        baseUrl?: string;
        clearBaseUrl?: boolean;
        pricingProfile?: PricingProfile;
    },
): Promise<RegistryProvider> {
    const raw = await apiFetch<RawRegistryProvider>(`/providers/${encodeURIComponent(providerId)}`, {
        method: 'PATCH',
        body: JSON.stringify({
            ...(patch.displayName !== undefined ? { display_name: patch.displayName } : {}),
            ...(patch.baseUrl !== undefined ? { base_url: patch.baseUrl } : {}),
            ...(patch.clearBaseUrl ? { clear_base_url: true } : {}),
            ...(patch.pricingProfile !== undefined
                ? { pricing_profile: patch.pricingProfile }
                : {}),
        }),
    });
    return mapRegistryProvider(raw);
}

export async function deleteProvider(providerId: string): Promise<void> {
    await apiFetch<{ status: string }>(`/providers/${encodeURIComponent(providerId)}`, {
        method: 'DELETE',
    });
}

export async function saveProviderKey(providerId: string, key: string): Promise<void> {
    await apiFetch<{ status: string }>(`/providers/${encodeURIComponent(providerId)}/key`, {
        method: 'POST',
        body: JSON.stringify({ key }),
    });
}

export async function deleteProviderKey(providerId: string): Promise<void> {
    await apiFetch<{ status: string }>(`/providers/${encodeURIComponent(providerId)}/key`, {
        method: 'DELETE',
    });
}

export interface LMStudioConfig {
    configured: boolean;
    baseUrl: string;
    apiTokenConfigured: boolean;
}

interface RawLMStudioConfig {
    configured: boolean;
    base_url: string;
    api_token_configured: boolean;
}

export async function fetchLMStudioConfig(): Promise<LMStudioConfig> {
    const raw = await apiFetch<RawLMStudioConfig>('/lmstudio/config');
    return {
        configured: raw.configured,
        baseUrl: raw.base_url ?? '',
        apiTokenConfigured: raw.api_token_configured,
    };
}

export async function saveLMStudioConfig(baseUrl: string, apiToken?: string): Promise<LMStudioConfig> {
    const raw = await apiFetch<RawLMStudioConfig>('/lmstudio/config', {
        method: 'POST',
        body: JSON.stringify({
            base_url: baseUrl,
            ...(apiToken !== undefined ? { api_token: apiToken } : {}),
        }),
    });
    return {
        configured: raw.configured,
        baseUrl: raw.base_url ?? '',
        apiTokenConfigured: raw.api_token_configured,
    };
}

export async function deleteLMStudioConfig(): Promise<void> {
    await apiFetch<{ status: string }>('/lmstudio/config', {
        method: 'DELETE',
    });
}

export interface OpenRouterAdminStatus {
    configured: boolean;
}

export interface OpenRouterCredits {
    configured: boolean;
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
    openrouter: 'openrouter',
    lmstudio: 'lmstudio',
};

function getModelDisplayName(provider: Provider, id: string): string {
    const prefix = `${provider}/`;
    if (id.startsWith(prefix)) {
        return id.slice(prefix.length);
    }
    return id;
}

export async function fetchModels(force = false): Promise<ModelsResult> {
    const raw = await apiFetch<RawModelsResponse>(`/models${force ? '?force=true' : ''}`);
    const models: Model[] = [];
    for (const [providerKey, data] of Object.entries(raw.providers || {})) {
        const provider = PROVIDER_MAP[providerKey] ?? providerKey;
        for (const id of data.models || []) {
            models.push({ id, name: getModelDisplayName(provider, id), provider });
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

interface RawTimingSummary {
    subject_duration_ms?: number;
    judge_duration_ms?: number;
    total_duration_ms?: number;
}

interface RawResultSummary {
    filename: string;
    filepath: string;
    target_model: string;
    executed_at: string;
    execution_duration_ms?: number;
    timing_summary?: RawTimingSummary | null;
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
    avg_score: number | null;
    max_score: number | null;
    min_score: number;
    run_id: string;
    exclude_unreliable_judges?: boolean;
}

export interface ResultSummary {
    filename: string;
    targetModel: string;
    executedAt: string;
    executionDurationMs?: number;
    timingSummary?: import('../types').TimingSummary;
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
    avgScore: number | null;
    maxScore: number | null;
    minScore: number;
    runId: string;
    excludeUnreliableJudges?: boolean;
}

function convertTimingSummary(
    raw: RawTimingSummary | null | undefined,
): import('../types').TimingSummary | undefined {
    if (!raw || typeof raw !== 'object') {
        return undefined;
    }
    const subjectDurationMs = Number(raw.subject_duration_ms || 0);
    const judgeDurationMs = Number(raw.judge_duration_ms || 0);
    const totalDurationMs =
        raw.total_duration_ms != null
            ? Number(raw.total_duration_ms)
            : subjectDurationMs + judgeDurationMs;
    return { subjectDurationMs, judgeDurationMs, totalDurationMs };
}

export async function fetchResultSummaries(): Promise<ResultSummary[]> {
    const raw = await apiFetch<RawResultSummary[]>('/results');
    return raw.map((r) => ({
        filename: r.filename,
        targetModel: r.target_model,
        executedAt: r.executed_at,
        executionDurationMs: r.execution_duration_ms,
        timingSummary: convertTimingSummary(r.timing_summary),
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
        excludeUnreliableJudges: Boolean(r.exclude_unreliable_judges),
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

interface RawUsageSummary {
    calls?: Array<{
        provider: string;
        model: string;
        call_count: number;
        input_tokens: number;
        output_tokens: number;
        total_tokens: number;
        cache_creation_input_tokens: number;
        cache_read_input_tokens: number;
        estimated_cost_usd: number | null;
        priced_call_count: number;
        unpriced_call_count: number;
        pricing_source: string | null;
        duration_ms: number;
    }>;
    totals?: {
        call_count: number;
        input_tokens: number;
        output_tokens: number;
        total_tokens: number;
        cache_creation_input_tokens: number;
        cache_read_input_tokens: number;
        estimated_cost_usd: number | null;
        priced_call_count: number;
        unpriced_call_count: number;
        pricing_status: 'available' | 'partial' | 'unavailable';
        unpriced_models: string[];
        total_duration_ms: number;
    };
}

interface RawBenchmarkResult {
    run_id: string;
    target_model: string;
    judge_models: string[];
    holistic_judge_models?: string[];
    judge_runs: number;
    executed_at: string;
    execution_duration_ms?: number;
    timing_summary?: RawTimingSummary | null;
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
    usage_summary?: RawUsageSummary;
    usage_summary_subject?: RawUsageSummary;
    usage_summary_judge?: RawUsageSummary;
    tasks: RawTaskData[];
    holistic_tasks?: RawTaskData[];
    cancelled: boolean;
    completed_tasks: number;
    total_tasks: number;
    average_score: number | null;
    best_score: number | null;
    exclude_unreliable_judges?: boolean;
    score_aggregation?: {
        average_score_before?: number | null;
        average_score_after?: number | null;
        best_score_before?: number | null;
        best_score_after?: number | null;
        excluded_judges?: Array<{ judge_id: string; reasons: string[] }>;
        included_judges?: string[];
        all_excluded?: boolean;
        unreliable_candidates?: Array<{ judge_id: string; reasons: string[] }>;
    };
}

interface RawTaskData {
    task_name: string;
    task_type: string;
    input_prompt: string;
    subject_prompt?: string;
    response: string;
    subject_usage?: {
        model?: string;
        provider?: string;
        total_tokens?: number;
        input_tokens?: number;
        output_tokens?: number;
        estimated_cost_usd?: number;
        duration_ms?: number;
    };
    tool_trace?: Array<{
        step_index: number;
        tool_name: string;
        arguments: Record<string, unknown>;
        result_summary: string;
        result_detail?: string;
        ok: boolean;
    }>;
    subject_runs?: Array<{
        run_index?: number;
        response?: string;
        subject_usage?: RawTaskData['subject_usage'];
        tool_trace?: RawTaskData['tool_trace'];
        error?: string | null;
    }>;
    subject_run_count?: number;
    has_subject_tools?: boolean;
    task_timing?: {
        subject_duration_ms?: number;
        judge_duration_ms?: number;
    };
    judge_results: Record<string, RawJudgeResult>;
}

interface RawJudgeRun {
    score: Record<string, unknown>;
    total_score: number;
    confidence: string;
    critical_fail: boolean;
    reasoning: unknown;
    /** API thinking; distinct from scoring `reasoning` (DEC-001) */
    api_reasoning?: unknown;
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
    aggregated: RawAggregated | null;
    error?: string;
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

function convertJudgeResult(judgeModel: string, raw: RawJudgeResult): JudgeEvaluation | null {
    const agg = raw.aggregated;
    if (!agg) {
        return null;
    }
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
        // intent: DEC-001 (Core/openai-judge-thinking) — separate from scoring rationale
        apiReasoningSamples: (raw.runs || [])
            .map((r) => normalizeReasoning(r.api_reasoning))
            .filter((value): value is string => Boolean(value)),
    };
}

function convertTask(raw: RawTaskData): TaskResult {
    const evaluations: JudgeEvaluation[] = [];
    for (const [judgeModel, judgeResult] of Object.entries(raw.judge_results || {})) {
        const converted = convertJudgeResult(judgeModel, judgeResult);
        if (converted) {
            evaluations.push(converted);
        }
    }
    const toolTrace: ToolTraceStep[] = (raw.tool_trace || []).map((step) => ({
        stepIndex: step.step_index,
        toolName: step.tool_name,
        arguments: step.arguments,
        resultSummary: step.result_summary,
        resultDetail: step.result_detail || '',
        ok: step.ok,
    }));
    const convertUsage = (
        usage: RawTaskData['subject_usage'] | undefined,
    ): import('../types').SubjectUsage | null =>
        usage
            ? {
                  provider: usage.provider || 'unknown',
                  model: usage.model || 'unknown',
                  inputTokens: usage.input_tokens || 0,
                  outputTokens: usage.output_tokens || 0,
                  totalTokens: usage.total_tokens || 0,
                  estimatedCostUsd: usage.estimated_cost_usd ?? null,
              }
            : null;
    const subjectUsage = convertUsage(raw.subject_usage);
    const subjectRuns: import('../types').SubjectRunRecord[] = (raw.subject_runs || []).map(
        (run, index) => ({
            runIndex: run.run_index ?? index + 1,
            response: run.response || '',
            subjectUsage: convertUsage(run.subject_usage),
            toolTrace: (run.tool_trace || []).map((step) => ({
                stepIndex: step.step_index,
                toolName: step.tool_name,
                arguments: step.arguments,
                resultSummary: step.result_summary,
                resultDetail: step.result_detail || '',
                ok: step.ok,
            })),
            error: run.error ?? null,
        }),
    );
    return {
        taskId: raw.task_name,
        taskType: (raw.task_type || 'fact') as TaskType,
        inputPrompt: raw.input_prompt || '',
        subjectPrompt: raw.subject_prompt || '',
        subjectResponse: raw.response || '',
        subjectUsage,
        subjectRuns,
        subjectRunCount: raw.subject_run_count ?? (subjectRuns.length || 1),
        judgeEvaluations: evaluations,
        toolTrace,
        // Old saved results may omit this; treat missing as false (legacy toolTrace still displays).
        hasSubjectTools: Boolean(raw.has_subject_tools),
        taskTiming: raw.task_timing
            ? {
                  subjectDurationMs: Number(raw.task_timing.subject_duration_ms || 0),
                  judgeDurationMs: Number(raw.task_timing.judge_duration_ms || 0),
              }
            : undefined,
    };
}

function convertUsageSummary(raw: RawBenchmarkResult['usage_summary']): import('../types').UsageSummary | undefined {
    if (!raw) return undefined;
    const rawCalls = raw.calls || [];
    const rawTotals = raw.totals;
    return {
        calls: rawCalls.map((c) => ({
            provider: c.provider,
            model: c.model,
            callCount: c.call_count,
            inputTokens: c.input_tokens,
            outputTokens: c.output_tokens,
            totalTokens: c.total_tokens,
            cacheCreationInputTokens: c.cache_creation_input_tokens,
            cacheReadInputTokens: c.cache_read_input_tokens,
            estimatedCostUsd: c.estimated_cost_usd,
            pricedCallCount: c.priced_call_count,
            unpricedCallCount: c.unpriced_call_count,
            pricingSource: c.pricing_source,
            durationMs: c.duration_ms ?? 0,
        })),
        totals: rawTotals
            ? {
                  callCount: rawTotals.call_count,
                  inputTokens: rawTotals.input_tokens,
                  outputTokens: rawTotals.output_tokens,
                  totalTokens: rawTotals.total_tokens,
                  cacheCreationInputTokens: rawTotals.cache_creation_input_tokens,
                  cacheReadInputTokens: rawTotals.cache_read_input_tokens,
                  estimatedCostUsd: rawTotals.estimated_cost_usd,
                  pricedCallCount: rawTotals.priced_call_count,
                  unpricedCallCount: rawTotals.unpriced_call_count,
                  pricingStatus: rawTotals.pricing_status,
                  unpricedModels: rawTotals.unpriced_models,
                  totalDurationMs: rawTotals.total_duration_ms ?? 0,
              }
            : {
                  callCount: 0,
                  inputTokens: 0,
                  outputTokens: 0,
                  totalTokens: 0,
                  cacheCreationInputTokens: 0,
                  cacheReadInputTokens: 0,
                  estimatedCostUsd: null,
                  pricedCallCount: 0,
                  unpricedCallCount: 0,
                  pricingStatus: 'unavailable',
                  unpricedModels: [],
                  totalDurationMs: 0,
              },
    };
}

function convertExcludedJudges(
    entries: Array<{ judge_id: string; reasons: string[] }> | undefined,
): import('../types').ExcludedJudgeInfo[] {
    return (entries || []).map((entry) => ({
        judgeId: entry.judge_id,
        reasons: [...(entry.reasons || [])],
    }));
}

function convertScoreAggregation(
    raw: RawBenchmarkResult['score_aggregation'],
): import('../types').ScoreAggregation | undefined {
    if (!raw || typeof raw !== 'object') return undefined;
    return {
        averageScoreBefore: raw.average_score_before ?? null,
        averageScoreAfter: raw.average_score_after ?? null,
        bestScoreBefore: raw.best_score_before ?? null,
        bestScoreAfter: raw.best_score_after ?? null,
        excludedJudges: convertExcludedJudges(raw.excluded_judges),
        includedJudges: [...(raw.included_judges || [])],
        allExcluded: Boolean(raw.all_excluded),
        unreliableCandidates: convertExcludedJudges(raw.unreliable_candidates),
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

    // intent: DEC-004 / INV-001 — null は N/A（0 に落とさない）。undefined のみ legacy 0。
    const averageScore = raw.average_score === undefined ? 0 : raw.average_score;
    const bestScore = raw.best_score === undefined ? 0 : raw.best_score;

    return {
        id: raw.run_id,
        subjectModelId: raw.target_model,
        subjectModelName: raw.target_model,
        judgeModels: (raw.judge_models || []).map((m) => ({ id: m, name: m })),
        // intent: DEC-003 (Core/holistic-judge-model) — 通常 judge と別キーで map
        holisticJudgeModels: (raw.holistic_judge_models || []).map((m) => ({ id: m, name: m })),
        timestamp: raw.executed_at,
        executionDurationMs: raw.execution_duration_ms,
        timingSummary: convertTimingSummary(raw.timing_summary),
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
        holisticTaskResults: (raw.holistic_tasks || []).map(convertTask),
        averageScore,
        bestScore,
        excludeUnreliableJudges: Boolean(raw.exclude_unreliable_judges),
        scoreAggregation: convertScoreAggregation(raw.score_aggregation),
        taskCount: raw.completed_tasks ?? raw.tasks?.length ?? 0,
        usageSummary: convertUsageSummary(raw.usage_summary),
        usageSummarySubject: convertUsageSummary(raw.usage_summary_subject),
        usageSummaryJudge: convertUsageSummary(raw.usage_summary_judge),
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
    /** Empty / omitted → backend falls back to judgeModels for holistic. */
    holisticJudgeModels?: string[];
    selectedTaskIds: string[];
    judgeRuns: number;
    subjectRuns?: number;
    subjectTemp: number;
    strictMode: boolean;
    strictPresetId?: string | null;
    taskToolModeOverrides?: Record<string, string>;
    runHolistic?: boolean;
    /** Exclude unreliable judges from hero average; default false. */
    excludeUnreliableJudges?: boolean;
    subjectParallel?: boolean;
    judgeParallel?: boolean;
}

export function buildRunRequestBody(params: RunParams): string {
    const body = JSON.stringify({
        target_model: params.targetModel,
        judge_models: params.judgeModels,
        // intent: DEC-001 (Core/holistic-judge-model) — optional; empty = fallback
        holistic_judge_models: params.holisticJudgeModels ?? [],
        selected_task_ids: params.selectedTaskIds,
        judge_runs: params.judgeRuns,
        subject_runs: params.subjectRuns ?? 1,
        subject_temp: params.subjectTemp,
        strict_mode: params.strictMode,
        strict_preset_id: params.strictPresetId ?? null,
        task_tool_mode_overrides: params.taskToolModeOverrides ?? {},
        run_holistic: params.runHolistic ?? true,
        // intent: DEC-003 (Core/exclude-unreliable-judges) — default OFF
        exclude_unreliable_judges: params.excludeUnreliableJudges ?? false,
        subject_parallel: params.subjectParallel ?? true,
        judge_parallel: params.judgeParallel ?? true,
    });
    return body;
}

export async function cancelRun(runId: string): Promise<void> {
    await apiFetch<{ status: string }>(`/run/cancel?run_id=${encodeURIComponent(runId)}`, {
        method: 'POST',
    });
}

export interface RateLimitProviderConfig {
    max_requests: number;
    window_seconds: number;
    is_default: boolean;
    recommended: {
        max_requests: number;
        window_seconds: number;
    };
}

export interface RateLimitsResponse {
    providers: Record<string, RateLimitProviderConfig>;
    max_concurrent_jobs: number;
}

export async function fetchRateLimits(): Promise<RateLimitsResponse> {
    return apiFetch<RateLimitsResponse>('/rate-limits');
}

export async function saveRateLimits(
    providers: Record<string, { max_requests: number; window_seconds: number }>,
): Promise<RateLimitsResponse> {
    return apiFetch<RateLimitsResponse>('/rate-limits', {
        method: 'PUT',
        body: JSON.stringify({ providers }),
    });
}

export async function resetRateLimits(): Promise<RateLimitsResponse> {
    return apiFetch<RateLimitsResponse>('/rate-limits/reset', {
        method: 'POST',
    });
}
