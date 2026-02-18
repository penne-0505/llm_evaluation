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
    // server.py returns: { id, type, prompt }[] — already camelCase-compatible
    const raw = await apiFetch<Array<{ id: string; type: string; prompt: string }>>('/tasks');
    return raw.map((t) => ({
        id: t.id,
        type: t.type as TaskType,
        prompt: t.prompt,
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
// Results — list summaries
// ---------------------------------------------------------------------------

interface RawResultSummary {
    filename: string;
    filepath: string;
    target_model: string;
    executed_at: string;
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
    judge_results: Record<string, RawJudgeResult>;
}

interface RawJudgeRun {
    score: Record<string, unknown>;
    total_score: number;
    confidence: string;
    critical_fail: boolean;
    reasoning: string;
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
        reasoningSamples: (raw.runs || []).map((r) => r.reasoning).filter(Boolean),
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
    return {
        id: raw.run_id,
        subjectModelId: raw.target_model,
        subjectModelName: raw.target_model,
        judgeModels: (raw.judge_models || []).map((m) => ({ id: m, name: m })),
        timestamp: raw.executed_at,
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

// ---------------------------------------------------------------------------
// Run — start benchmark (returns SSE URL info for sse.ts)
// ---------------------------------------------------------------------------

export interface RunParams {
    targetModel: string;
    judgeModels: string[];
    selectedTaskIds: string[];
    judgeRuns: number;
    subjectTemp: number;
}

export function buildRunRequestBody(params: RunParams): string {
    return JSON.stringify({
        target_model: params.targetModel,
        judge_models: params.judgeModels,
        selected_task_ids: params.selectedTaskIds,
        judge_runs: params.judgeRuns,
        subject_temp: params.subjectTemp,
    });
}

export async function cancelRun(runId: string): Promise<void> {
    await apiFetch<{ status: string }>(`/run/cancel?run_id=${encodeURIComponent(runId)}`, {
        method: 'POST',
    });
}
