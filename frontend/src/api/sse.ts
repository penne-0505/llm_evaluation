/**
 * SSE クライアント — POST /api/run の SSE ストリームを処理
 *
 * server.py のイベント種別:
 *   { type: "run_id",    run_id }
 *   { type: "progress",  message, current, total, task_index, task_id, judge_model,
 *                        completed_task_count, active_task_count, queued_task_count,
 *                        completed_tasks, active_tasks, queued_tasks }
 *   { type: "complete",  result, saved_path }
 *   { type: "cancelled", completed_tasks, total_tasks, reason }
 *   { type: "error",     message, traceback }
 */

import { buildRunRequestBody, convertBenchmarkResult, type RunParams } from './client';
import { useRunStore } from '../store/runStore';
import { useHistoryStore } from '../store/historyStore';
import type { ActiveRunTask } from '../types';

export interface SSEConnection {
    abort: () => void;
}

/**
 * ベンチマーク実行を開始し SSE ストリームを購読する。
 * runStore / historyStore への dispatch はここで行う。
 */
export function startBenchmarkSSE(params: RunParams): SSEConnection {
    const controller = new AbortController();
    const startTime = Date.now();

    // 非同期で SSE を読む
    (async () => {
        try {
            const res = await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: buildRunRequestBody(params),
                signal: controller.signal,
            });

            if (!res.ok) {
                const text = await res.text();
                useRunStore.getState().setError(`API ${res.status}: ${text}`);
                return;
            }

            const reader = res.body?.getReader();
            if (!reader) {
                useRunStore.getState().setError('レスポンス本文がありません');
                return;
            }

            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                // 最後の不完全行をバッファに残す
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    const jsonStr = line.slice(6).trim();
                    if (!jsonStr) continue;

                    try {
                        const event = JSON.parse(jsonStr);
                        handleSSEEvent(event, startTime);
                    } catch {
                        // JSON パースエラーはスキップ
                    }
                }
            }

            // ストリーム終了時にまだ running なら完了扱いにはしない（サーバー側で complete/error/cancelled が送られるはず）
        } catch (err: unknown) {
            if (err instanceof DOMException && err.name === 'AbortError') {
                // ユーザーキャンセル — runStore.cancelRun() は呼び出し元で処理済み
                return;
            }
            useRunStore.getState().setError(
                err instanceof Error ? err.message : 'SSE 接続に失敗しました',
            );
        }
    })();

    return { abort: () => controller.abort() };
}

// ---------------------------------------------------------------------------
// Event handlers
// ---------------------------------------------------------------------------

function handleSSEEvent(
    event: Record<string, unknown>,
    startTime: number,
): void {
    const store = useRunStore.getState();

    switch (event.type) {
        case 'run_id':
            store.setRunId(event.run_id as string);
            break;

        case 'progress':
            store.updateProgress({
                currentStep: event.current as number,
                totalSteps: event.total as number,
                currentTaskIndex: event.task_index as number,
                currentTaskId: (event.task_id as string) || '',
                currentJudgeModel: (event.judge_model as string) || '',
                elapsedMs: Date.now() - startTime,
                completedTaskCount: (event.completed_task_count as number) || 0,
                activeTaskCount: (event.active_task_count as number) || 0,
                queuedTaskCount: (event.queued_task_count as number) || 0,
                completedTasks: normalizeActiveTasks(event.completed_tasks),
                activeTasks: normalizeActiveTasks(event.active_tasks),
                queuedTasks: normalizeActiveTasks(event.queued_tasks),
            });
            break;

        case 'complete': {
            const rawResult = event.result as Record<string, unknown>;
            const savedPath = event.saved_path as string;
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const evalRun = convertBenchmarkResult(rawResult as any);
            store.completeRun(evalRun, savedPath);
            useHistoryStore.getState().upsertRun(evalRun);
            break;
        }

        case 'cancelled':
            store.cancelRun();
            break;

        case 'error':
            store.setError(event.message as string);
            break;
    }
}

function normalizeActiveTasks(raw: unknown): ActiveRunTask[] {
    if (!Array.isArray(raw)) {
        return [];
    }

    return raw.map((task) => {
        const item = (task ?? {}) as Record<string, unknown>;
        return {
            taskId: (item.task_id as string) || '',
            taskIndex: (item.task_index as number) || 0,
            phase: (item.phase as ActiveRunTask['phase']) || 'queued',
            message: (item.message as string) || '',
            subjectDone: Boolean(item.subject_done),
            judgeStates: (item.judge_states as Record<string, ActiveRunTask['judgeStates'][string]>) || {},
            judgeCompletedCount: (item.judge_completed_count as number) || 0,
            judgeErrorCount: (item.judge_error_count as number) || 0,
            judgeTotalCount: (item.judge_total_count as number) || 0,
            activeJudges: (item.active_judges as string[]) || [],
        };
    });
}
