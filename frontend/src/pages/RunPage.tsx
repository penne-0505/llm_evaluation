import { useRef, useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSettingsStore } from '../store/settingsStore';
import { useRunStore } from '../store/runStore';
import { getStrictModeIssues } from '../lib/strictMode';
import { startBenchmarkSSE, type SSEConnection } from '../api/sse';
import {
    cancelRun as apiCancelRun,
    fetchOpenRouterCredits,
} from '../api/client';
import {
    Play,
    Square,
    CheckCircle2,
    XCircle,
    ArrowRight,
    Loader2,
    AlertCircle,
} from 'lucide-react';

function formatTime(ms: number): string {
    const s = Math.floor(ms / 1000);
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
}

function scoreColor(score: number): string {
    if (score >= 80) return 'text-score-high';
    if (score >= 60) return 'text-score-mid';
    return 'text-score-low';
}

function scoreGlow(score: number): string {
    if (score >= 80) return 'glow-high';
    if (score >= 60) return 'glow-mid';
    return 'glow-low';
}

export default function RunPage() {
    const navigate = useNavigate();
    const {
        evaluationMode, strictPreset,
        availableModels, subjectModelId, judgeModelIds, freeTextSubject,
        freeTextJudges, selectedTaskIds, tasks, evalParams,
    } = useSettingsStore();
    const {
        status, progress, result, resultFilePath, cancelRequested, errorMessage, runId,
        startRun, requestCancel, reset, setResult,
    } = useRunStore();

    const sseRef = useRef<SSEConnection | null>(null);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const cancelRequestRunIdRef = useRef<string | null>(null);
    const [, setTick] = useState(0); // timer re-render用
    const [creditsConfigured, setCreditsConfigured] = useState(false);
    const [remainingCredits, setRemainingCredits] = useState<number | null>(null);
    const [creditsLoading, setCreditsLoading] = useState(true);
    const [creditFetchFailed, setCreditFetchFailed] = useState(false);

    const subjectModel = availableModels.find((m) => m.id === subjectModelId);
    const judgeModels = availableModels.filter((m) => judgeModelIds.includes(m.id));
    const effectiveSubjectName = subjectModel?.name || freeTextSubject || '未選択';
    const effectiveJudgeNames = judgeModels.length > 0 ? judgeModels.map((m) => m.name) : freeTextJudges;
    const effectiveJudgeIds = judgeModels.length > 0 ? judgeModels.map((m) => m.id) : freeTextJudges;
    const selectedTasks = tasks.filter((t) => selectedTaskIds.includes(t.id));
    const totalSteps = selectedTasks.length * Math.max(effectiveJudgeNames.length, 1) * evalParams.judgeRunCount;
    const isStrict = evaluationMode === 'strict';
    const strictIssues = getStrictModeIssues({
        strictPreset,
        availableModels,
        tasks,
        selectedTaskIds,
        judgeModelIds,
        judgeRunCount: evalParams.judgeRunCount,
        subjectTemperature: evalParams.subjectTemperature,
    });
    const strictReady = !isStrict || strictIssues.length === 0;
    const canStart = (subjectModelId || freeTextSubject) && effectiveJudgeNames.length > 0 && selectedTasks.length > 0 && strictReady;
    const liveElapsedMs = status === 'running' && progress?.startedAtMs
        ? Date.now() - progress.startedAtMs
        : progress?.elapsedMs ?? 0;

    const cleanup = useCallback(() => {
        if (timerRef.current) clearInterval(timerRef.current);
        timerRef.current = null;
        sseRef.current = null;
        cancelRequestRunIdRef.current = null;
    }, []);

    const loadCredits = useCallback(async () => {
        try {
            const snapshot = await fetchOpenRouterCredits();
            setCreditsConfigured(snapshot.configured);
            setRemainingCredits(
                typeof snapshot.remainingCredits === 'number' ? snapshot.remainingCredits : null,
            );
            setCreditFetchFailed(false);
        } catch {
            setCreditFetchFailed(true);
        } finally {
            setCreditsLoading(false);
        }
    }, []);

    useEffect(() => cleanup, [cleanup]);

    useEffect(() => {
        void loadCredits();
    }, [loadCredits]);

    useEffect(() => {
        if (status !== 'running' || !creditsConfigured) {
            return;
        }

        const intervalId = setInterval(() => {
            void loadCredits();
        }, 60_000);

        return () => clearInterval(intervalId);
    }, [status, creditsConfigured, loadCredits]);

    const handleStart = () => {
        startRun(totalSteps);
        cancelRequestRunIdRef.current = null;

        // SSE タイマー — 経過時間の更新
        timerRef.current = setInterval(() => {
            setTick((t) => t + 1);
        }, 200);

        // SSE ストリーム開始
        const targetModel = subjectModel?.id || freeTextSubject;
        sseRef.current = startBenchmarkSSE({
            targetModel,
            judgeModels: effectiveJudgeIds,
            selectedTaskIds,
            judgeRuns: evalParams.judgeRunCount,
            subjectTemp: evalParams.subjectTemperature,
            strictMode: isStrict,
            strictPresetId: strictPreset?.id ?? null,
        });
    };

    const handleCancel = async () => {
        requestCancel();
    };

    useEffect(() => {
        if (!cancelRequested || !runId) {
            return;
        }
        if (cancelRequestRunIdRef.current === runId) {
            return;
        }

        cancelRequestRunIdRef.current = runId;
        void apiCancelRun(runId).catch(() => {
            cancelRequestRunIdRef.current = null;
        });
    }, [cancelRequested, runId]);

    const handleReset = () => {
        cleanup();
        reset();
    };

    return (
        <div className="space-y-8 animate-fade-up">
            {/* Hero */}
            <div className="hero-glow relative py-2">
                <div className="relative z-10 flex items-start justify-between gap-4">
                    <div>
                        <p className="section-label mb-2">実行管理</p>
                        <div className="flex items-center gap-2">
                            <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">
                                評価実行
                            </h1>
                            {isStrict && (
                                <span className="rounded-full border border-score-high/25 bg-score-high/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-score-high">
                                    strict
                                </span>
                            )}
                        </div>
                        <p className="text-text-secondary mt-1 text-[13px]">現在の設定でベンチマークを実行します</p>
                    </div>
                    <RunCreditBadge
                        configured={creditsConfigured}
                        loading={creditsLoading}
                        remainingCredits={remainingCredits}
                        fetchFailed={creditFetchFailed}
                    />
                </div>
            </div>

            {/* ===== IDLE ===== */}
            {status === 'idle' && (
                <div className="space-y-4 animate-fade-up stagger-2">
                    {/* Checklist */}
                    <div className="card p-5">
                        <p className="section-label mb-3">実行前チェック</p>
                        <div className="space-y-2">
                            <ChecklistItem
                                label="被験モデル"
                                value={effectiveSubjectName}
                                ok={!!(subjectModelId || freeTextSubject)}
                            />
                            <ChecklistItem
                                label="評価モデル"
                                value={`${effectiveJudgeNames.length}件選択`}
                                ok={effectiveJudgeNames.length > 0}
                                items={effectiveJudgeNames}
                            />
                            <ChecklistItem
                                label="タスク"
                                value={`${selectedTasks.length}件読み込み済み`}
                                ok={selectedTasks.length > 0}
                                items={selectedTasks.map((t) => t.id)}
                            />
                        </div>
                    </div>

                    {/* Stats */}
                    <div className="card p-4">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <Stat label="総ステップ" value={String(totalSteps)} highlight />
                            <Stat label="評価回数" value={String(evalParams.judgeRunCount)} />
                            <Stat label="Subject Temperature" value={evalParams.subjectTemperature.toFixed(2)} />
                            <Stat label="Judge Temperature" value="0.00" muted />
                        </div>
                    </div>

                    {!canStart && (
                        <div className="flex items-center gap-2 p-3 bg-score-low/8 border border-score-low/15 rounded-md text-[12px] text-score-low">
                            <XCircle size={14} />
                            {isStrict && strictIssues.length > 0
                                ? `Strict Mode 条件を満たしていません: ${strictIssues[0]}`
                                : '実行前に、被験モデル、評価モデルを1つ以上、タスクを1つ以上設定してください。'}
                        </div>
                    )}

                    <button
                        onClick={handleStart}
                        disabled={!canStart}
                        className="w-full py-3.5 bg-amber text-bg rounded-md text-[13px] font-display font-bold flex items-center justify-center gap-2 hover:bg-amber-hover disabled:bg-surface disabled:text-text-tertiary disabled:border disabled:border-border disabled:cursor-not-allowed transition-all duration-200 hover:shadow-[0_0_24px_rgba(226,168,75,0.15)]"
                    >
                        <Play size={16} />
                        評価を開始
                    </button>
                </div>
            )}

            {/* ===== RUNNING ===== */}
            {status === 'running' && progress && (
                <div className="space-y-4 animate-fade-in">
                    <div className="card p-6 space-y-6">
                        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
                            <span className="section-label text-[9px]">進行ボード</span>
                            <div className="flex items-center gap-3">
                                <button
                                    onClick={handleCancel}
                                    disabled={cancelRequested}
                                    className="inline-flex items-center gap-1.5 rounded border border-score-low/30 bg-score-low/10 px-3 py-1.5 text-[12px] text-score-low transition-colors duration-150 hover:border-score-low/50 hover:bg-score-low/15 disabled:opacity-40"
                                >
                                    <Square size={13} />
                                    {cancelRequested ? 'キャンセル中...' : 'キャンセル'}
                                </button>
                                <span className="text-[11px] text-text-tertiary">
                                    {progress.completedTaskCount} / {selectedTasks.length} タスク完了
                                </span>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <RunSummaryStat label="完了" value={String(progress.completedTaskCount)} />
                            <RunSummaryStat label="実行中" value={String(progress.activeTaskCount)} highlight />
                            <RunSummaryStat label="待機中" value={String(progress.queuedTaskCount)} />
                            <RunSummaryStat label="経過時間" value={formatTime(liveElapsedMs)} />
                        </div>

                        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3 items-stretch">
                            <TaskLane
                                title="待機中"
                                count={progress.queuedTaskCount}
                                tasks={progress.queuedTasks}
                                emptyMessage="待機中のタスクはありません。"
                            />
                            <TaskLane
                                title="実行中"
                                count={progress.activeTaskCount}
                                tasks={progress.activeTasks}
                                emptyMessage="現在実行中のタスクはありません。"
                                emphasize
                            />
                            <TaskLane
                                title="完了"
                                count={progress.completedTaskCount}
                                tasks={progress.completedTasks}
                                emptyMessage="完了したタスクはここに表示されます。"
                            />
                        </div>
                    </div>

                </div>
            )}

            {/* ===== COMPLETED ===== */}
            {status === 'completed' && result && (
                <div className="space-y-4 animate-fade-up">
                    <div className={`card p-8 text-center space-y-4 ${scoreGlow(result.averageScore)}`}>
                        <CheckCircle2 size={32} className="text-score-high mx-auto" />
                        <h2 className="text-[15px] font-display font-bold text-text-primary">評価完了</h2>
                        <p className="text-[12px] text-text-secondary">
                            {result.taskResults.length}タスク · {result.judgeModels.length}評価モデル
                        </p>

                        {/* Big Score */}
                        <div className="py-3">
                            <CountUpScore value={result.averageScore} />
                        </div>

                        {resultFilePath && (
                            <p className="data-display text-[11px] text-text-tertiary">{resultFilePath}</p>
                        )}
                    </div>

                    <div className="grid grid-cols-3 gap-2">
                        <Stat label="平均点" value={String(result.averageScore)} color={scoreColor(result.averageScore)} />
                        <Stat label="最高点" value={String(result.bestScore)} color={scoreColor(result.bestScore)} />
                        <Stat label="タスク数" value={String(result.taskResults.length)} />
                    </div>

                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        <button
                            onClick={() => { setResult(result); navigate('/results'); }}
                            className="flex-1 py-2.5 bg-amber text-bg rounded-md text-[13px] font-display font-semibold flex items-center justify-center gap-2 hover:bg-amber-hover transition-all duration-200 hover:shadow-[0_0_24px_rgba(226,168,75,0.15)]"
                        >
                            <ArrowRight size={14} />
                            結果を見る
                        </button>
                        <button
                            onClick={handleReset}
                            className="py-2.5 px-4 rounded-md border border-amber/30 bg-amber-dim/40 text-[13px] font-medium text-text-primary flex items-center justify-center gap-2 hover:border-amber/45 hover:bg-amber-dim/60 transition-colors duration-150"
                        >
                            <Play size={14} />
                            新しく実行
                        </button>
                    </div>
                </div>
            )}

            {/* ===== CANCELLED ===== */}
            {status === 'cancelled' && (
                <div className="space-y-4 animate-fade-up">
                    <div className="card p-8 text-center space-y-3">
                        <XCircle size={32} className="text-score-mid mx-auto" />
                        <h2 className="text-[15px] font-display font-bold text-text-primary">評価をキャンセルしました</h2>
                        <p className="text-[12px] text-text-secondary">
                            {progress?.currentStep || 0} / {progress?.totalSteps || totalSteps} ステップ完了
                        </p>
                    </div>
                    <button
                        onClick={handleReset}
                        className="w-full py-2.5 border border-border rounded-md text-[12px] text-text-secondary hover:text-text-primary hover:border-border-focus flex items-center justify-center gap-2 transition-colors duration-150"
                    >
                        <Play size={13} /> 最初からやり直す
                    </button>
                </div>
            )}

            {/* ===== ERROR ===== */}
            {status === 'error' && (
                <div className="space-y-4 animate-fade-up">
                    <div className="card p-8 text-center space-y-3 accent-bar-low">
                        <AlertCircle size={32} className="text-score-low mx-auto" />
                        <h2 className="text-[15px] font-display font-bold text-text-primary">評価に失敗しました</h2>
                        <p className="text-[12px] text-text-secondary">{errorMessage}</p>
                    </div>
                    <button
                        onClick={handleReset}
                        className="w-full py-2.5 border border-border rounded-md text-[12px] text-text-secondary hover:text-text-primary hover:border-border-focus flex items-center justify-center gap-2 transition-colors duration-150"
                    >
                        <Play size={13} /> 最初からやり直す
                    </button>
                </div>
            )}
        </div>
    );
}

/* ======= Checklist Item ======= */
function ChecklistItem({ label, value, ok, items }: { label: string; value: string; ok: boolean; items?: string[] }) {
    return (
        <div className="flex items-start gap-3 py-1.5">
            <div className={`w-4 h-4 mt-0.5 rounded-full flex items-center justify-center ${ok ? 'bg-score-high/15 text-score-high' : 'bg-score-low/15 text-score-low'}`}>
                {ok ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
            </div>
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <span className="text-[12px] text-text-secondary">{label}</span>
                    <span className="text-[12px] font-medium text-text-primary">{value}</span>
                </div>
                {items && items.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                        {items.map((item) => (
                            <span key={item} className="px-1.5 py-0.5 bg-surface-hover rounded text-[10px] text-text-tertiary">{item}</span>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

function TaskLane({
    title,
    count,
    tasks,
    emptyMessage,
    emphasize = false,
}: {
    title: string;
    count: number;
    tasks: NonNullable<ReturnType<typeof useRunStore.getState>['progress']>['activeTasks'];
    emptyMessage: string;
    emphasize?: boolean;
}) {
    return (
        <section className={`rounded-lg border ${emphasize ? 'border-amber/20 bg-amber-glow' : 'border-border bg-bg/70'} p-4 space-y-4 lg:h-[560px] flex flex-col`}>
            <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                    <p className="text-[11px] font-display font-semibold uppercase tracking-[0.18em] text-text-primary">
                        {title}
                    </p>
                    {emphasize && <Loader2 size={12} className="text-amber animate-spin" />}
                </div>
                <span className={`min-w-8 rounded-full px-2 py-1 text-center text-[10px] font-medium ${emphasize ? 'bg-amber-dim text-amber' : 'bg-surface-hover text-text-secondary'}`}>
                    {count}
                </span>
            </div>

            {tasks.length > 0 ? (
                <div className="min-h-0 flex-1 overflow-y-auto pr-1 space-y-3">
                    {tasks.map((task) => (
                        <ActiveTaskCard key={`${title}-${task.taskId}`} task={task} />
                    ))}
                </div>
            ) : (
                <div className="min-h-0 flex-1 rounded-md border border-dashed border-border px-4 py-5 text-[12px] text-text-tertiary">
                    {emptyMessage}
                </div>
            )}
        </section>
    );
}

function ActiveTaskCard({ task }: { task: NonNullable<ReturnType<typeof useRunStore.getState>['progress']>['activeTasks'][number] }) {
    const judgeEntries = Object.entries(task.judgeStates || {});
    const activeJudges = task.activeJudges || [];
    const phaseMeta = getTaskPhaseMeta(task.phase);
    const settledCount = task.judgeCompletedCount + task.judgeErrorCount;
    const subjectBarClass = task.phase === 'queued'
        ? 'bg-border'
        : task.phase === 'completed'
            ? 'bg-score-high'
            : task.phase === 'failed'
                ? 'bg-score-low'
                : task.subjectDone
                    ? 'bg-score-high'
                    : 'bg-amber animate-pulse-amber';
    const detailText = task.phase === 'queued'
        ? 'ワーカー割り当て待ち'
        : task.phase === 'completed'
            ? `${settledCount} / ${task.judgeTotalCount} 評価が確定`
            : activeJudges.length > 0
                ? `${activeJudges.length} 件の評価ワーカーが稼働中`
                : task.phase === 'running_subject'
                    ? '被験モデルの回答を生成中'
                    : '次の評価更新を待機中';

    return (
        <div className={`rounded-md border px-4 py-3 space-y-3 ${phaseMeta.cardClass}`}>
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <div className="flex items-center gap-2">
                        <span className="rounded bg-surface-hover px-1.5 py-0.5 text-[10px] text-text-tertiary">
                            #{task.taskIndex + 1}
                        </span>
                        <p className="data-display truncate text-[13px] text-text-primary">{task.taskId}</p>
                    </div>
                    <p className="text-[11px] text-text-tertiary mt-0.5">{task.message}</p>
                </div>
                <span className={`px-2 py-0.5 rounded text-[10px] uppercase tracking-wider ${phaseMeta.badgeClass}`}>
                    {phaseMeta.label}
                </span>
            </div>

            <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[10px] text-text-tertiary uppercase tracking-wider">
                    <span>パイプライン</span>
                    <span>{settledCount} / {task.judgeTotalCount} 評価確定</span>
                </div>
                <div className="flex gap-1">
                    <div className={`h-2 rounded-sm flex-1 ${subjectBarClass}`} />
                    {judgeEntries.map(([judgeModel, phase]) => (
                        <div
                            key={judgeModel}
                            className={`h-2 rounded-sm flex-1 ${phase === 'completed'
                                ? 'bg-score-high'
                                : phase === 'error'
                                    ? 'bg-score-low'
                                    : phase === 'running'
                                        ? 'bg-amber animate-pulse-amber'
                                        : 'bg-border'
                                }`}
                        />
                    ))}
                </div>
            </div>

            <div className="space-y-2">
                <p className="text-[10px] uppercase tracking-wider text-text-tertiary">{detailText}</p>
                <div className="flex flex-wrap gap-1.5">
                    {activeJudges.map((judge) => (
                        <span key={judge} className="px-1.5 py-0.5 rounded bg-amber-dim text-[10px] text-amber">
                            {judge}
                        </span>
                    ))}
                    {task.phase === 'completed' && task.judgeErrorCount > 0 && (
                        <span className="px-1.5 py-0.5 rounded bg-score-low/10 text-[10px] text-score-low">
                            エラー {task.judgeErrorCount} 件
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
}

function getTaskPhaseMeta(phase: NonNullable<ReturnType<typeof useRunStore.getState>['progress']>['activeTasks'][number]['phase']) {
    switch (phase) {
        case 'running_subject':
            return {
                label: '回答生成',
                cardClass: 'border-amber/20 bg-bg',
                badgeClass: 'bg-amber-dim text-amber',
            };
        case 'running_judges':
            return {
                label: '評価中',
                cardClass: 'border-amber/20 bg-bg',
                badgeClass: 'bg-amber-dim text-amber',
            };
        case 'completed':
            return {
                label: '完了',
                cardClass: 'border-score-high/20 bg-bg',
                badgeClass: 'bg-score-high/10 text-score-high',
            };
        case 'failed':
            return {
                label: '失敗',
                cardClass: 'border-score-low/20 bg-bg',
                badgeClass: 'bg-score-low/10 text-score-low',
            };
        default:
            return {
                label: '待機中',
                cardClass: 'border-border bg-bg',
                badgeClass: 'bg-surface-hover text-text-secondary',
            };
    }
}

/* ======= Count-Up Score ======= */
function CountUpScore({ value }: { value: number }) {
    const [display, setDisplay] = useState(0);
    const ref = useRef<number | null>(null);

    useEffect(() => {
        const start = Date.now();
        const duration = 800;
        const tick = () => {
            const elapsed = Date.now() - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setDisplay(Math.round(eased * value * 10) / 10);
            if (progress < 1) ref.current = requestAnimationFrame(tick);
        };
        ref.current = requestAnimationFrame(tick);
        return () => { if (ref.current) cancelAnimationFrame(ref.current); };
    }, [value]);

    return (
        <span className={`data-display text-4xl ${scoreColor(value)}`}>
            {display.toFixed(1)}
        </span>
    );
}

/* ======= Stat ======= */
function Stat({ label, value, color, highlight, muted }: { label: string; value: string; color?: string; highlight?: boolean; muted?: boolean }) {
    return (
        <div className="text-center">
            <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-0.5">{label}</p>
            <p className={`data-display text-lg ${muted ? 'text-text-tertiary' : color || (highlight ? 'text-amber' : 'text-text-primary')}`}>
                {value}
            </p>
        </div>
    );
}

function RunSummaryStat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
    return (
        <div className="text-center">
            <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-0.5">{label}</p>
            <p className={`data-display text-lg ${highlight ? 'text-amber' : 'text-text-primary'}`}>{value}</p>
        </div>
    );
}

function RunCreditBadge({
    configured,
    loading,
    remainingCredits,
    fetchFailed,
}: {
    configured: boolean;
    loading: boolean;
    remainingCredits: number | null;
    fetchFailed: boolean;
}) {
    if (!configured && !loading) {
        return null;
    }

    return (
        <div className="shrink-0 rounded-md border border-amber/20 bg-amber-glow px-3.5 py-2.5 text-right shadow-[0_10px_28px_rgba(0,0,0,0.16)]">
            <p className="text-[9px] uppercase tracking-[0.18em] text-text-secondary">OpenRouter Credits</p>
            <p className="mt-1 data-display text-[16px] text-text-primary">
                {loading
                    ? '...'
                    : fetchFailed
                        ? 'ERR'
                        : typeof remainingCredits === 'number'
                            ? remainingCredits.toFixed(4)
                            : '---'}
            </p>
        </div>
    );
}
