import { useRef, useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSettingsStore } from '../store/settingsStore';
import { useRunStore } from '../store/runStore';
import { startBenchmarkSSE, type SSEConnection } from '../api/sse';
import { cancelRun as apiCancelRun } from '../api/client';
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
        availableModels, subjectModelId, judgeModelIds, freeTextSubject,
        freeTextJudges, selectedTaskIds, tasks, evalParams,
    } = useSettingsStore();
    const {
        status, progress, result, resultFilePath, cancelRequested, errorMessage, runId,
        startRun, requestCancel, reset, setResult,
    } = useRunStore();

    const sseRef = useRef<SSEConnection | null>(null);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const [, setTick] = useState(0); // timer re-render用

    const subjectModel = availableModels.find((m) => m.id === subjectModelId);
    const judgeModels = availableModels.filter((m) => judgeModelIds.includes(m.id));
    const effectiveSubjectName = subjectModel?.name || freeTextSubject || 'Not selected';
    const effectiveJudgeNames = judgeModels.length > 0 ? judgeModels.map((m) => m.name) : freeTextJudges;
    const effectiveJudgeIds = judgeModels.length > 0 ? judgeModels.map((m) => m.id) : freeTextJudges;
    const selectedTasks = tasks.filter((t) => selectedTaskIds.includes(t.id));
    const totalSteps = selectedTasks.length * Math.max(effectiveJudgeNames.length, 1) * evalParams.judgeRunCount;
    const canStart = (subjectModelId || freeTextSubject) && effectiveJudgeNames.length > 0 && selectedTasks.length > 0;

    const cleanup = useCallback(() => {
        if (timerRef.current) clearInterval(timerRef.current);
        timerRef.current = null;
        sseRef.current = null;
    }, []);

    useEffect(() => cleanup, [cleanup]);

    const handleStart = () => {
        startRun(totalSteps);

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
        });
    };

    const handleCancel = async () => {
        requestCancel();
        if (runId) {
            try {
                await apiCancelRun(runId);
            } catch {
                // ignore
            }
        }
    };

    const handleReset = () => {
        cleanup();
        reset();
    };

    return (
        <div className="space-y-8 animate-fade-up">
            {/* Hero */}
            <div className="hero-glow relative py-2">
                <div className="relative z-10">
                    <p className="section-label mb-2">Mission Control</p>
                    <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">
                        Run Evaluation
                    </h1>
                    <p className="text-text-secondary mt-1 text-[13px]">Execute benchmark with current configuration</p>
                </div>
            </div>

            {/* ===== IDLE ===== */}
            {status === 'idle' && (
                <div className="space-y-4 animate-fade-up stagger-2">
                    {/* Checklist */}
                    <div className="card p-5">
                        <p className="section-label mb-3">Pre-flight Check</p>
                        <div className="space-y-2">
                            <ChecklistItem
                                label="Subject Model"
                                value={effectiveSubjectName}
                                ok={!!(subjectModelId || freeTextSubject)}
                            />
                            <ChecklistItem
                                label="Judge Models"
                                value={`${effectiveJudgeNames.length} selected`}
                                ok={effectiveJudgeNames.length > 0}
                                items={effectiveJudgeNames}
                            />
                            <ChecklistItem
                                label="Tasks"
                                value={`${selectedTasks.length} loaded`}
                                ok={selectedTasks.length > 0}
                                items={selectedTasks.map((t) => t.id)}
                            />
                        </div>
                    </div>

                    {/* Stats */}
                    <div className="card p-4">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <Stat label="Total steps" value={String(totalSteps)} highlight />
                            <Stat label="Judge runs" value={String(evalParams.judgeRunCount)} />
                            <Stat label="Subject temp" value={evalParams.subjectTemperature.toFixed(2)} />
                            <Stat label="Judge temp" value="0.00" muted />
                        </div>
                    </div>

                    {!canStart && (
                        <div className="flex items-center gap-2 p-3 bg-score-low/8 border border-score-low/15 rounded-md text-[12px] text-score-low">
                            <XCircle size={14} />
                            Configure a subject model, at least 1 judge, and at least 1 task before running.
                        </div>
                    )}

                    <button
                        onClick={handleStart}
                        disabled={!canStart}
                        className="w-full py-3.5 bg-amber text-bg rounded-md text-[13px] font-display font-bold flex items-center justify-center gap-2 hover:bg-amber-hover disabled:bg-surface disabled:text-text-tertiary disabled:border disabled:border-border disabled:cursor-not-allowed transition-all duration-200 hover:shadow-[0_0_24px_rgba(226,168,75,0.15)]"
                    >
                        <Play size={16} />
                        Start Evaluation
                    </button>
                </div>
            )}

            {/* ===== RUNNING ===== */}
            {status === 'running' && progress && (
                <div className="space-y-4 animate-fade-in">
                    <div className="card p-6 space-y-5">
                        {/* Segment Progress Bar */}
                        <div className="space-y-2">
                            <div className="flex items-center justify-between text-[11px]">
                                <span className="section-label text-[9px]">Progress</span>
                                <span className="data-display text-text-primary">{progress.currentStep} / {progress.totalSteps}</span>
                            </div>
                            <SegmentProgressBar
                                total={selectedTasks.length}
                                currentTaskIndex={progress.currentTaskIndex}
                                completed={progress.currentStep >= progress.totalSteps}
                            />
                        </div>

                        {/* Status Grid */}
                        <div className="grid grid-cols-3 gap-4">
                            <div className="flex items-center gap-2">
                                <Loader2 size={13} className="text-amber animate-spin" />
                                <div>
                                    <p className="text-[9px] text-text-tertiary uppercase tracking-wider">Task</p>
                                    <p className="data-display text-[12px] text-text-primary">{progress.currentTaskId}</p>
                                </div>
                            </div>
                            <div>
                                <p className="text-[9px] text-text-tertiary uppercase tracking-wider">Judge</p>
                                <p className="data-display text-[12px] text-text-primary">{progress.currentJudgeModel}</p>
                            </div>
                            <div>
                                <p className="text-[9px] text-text-tertiary uppercase tracking-wider">Elapsed</p>
                                <p className="data-display text-[12px] text-text-primary">{formatTime(progress.elapsedMs)}</p>
                            </div>
                        </div>
                    </div>

                    <button
                        onClick={handleCancel}
                        disabled={cancelRequested}
                        className="w-full py-2.5 border border-border rounded-md text-[12px] text-text-secondary hover:text-score-low hover:border-score-low/30 transition-colors duration-150"
                    >
                        <span className="flex items-center justify-center gap-2">
                            <Square size={13} />
                            {cancelRequested ? 'Cancelling...' : 'Cancel'}
                        </span>
                    </button>
                </div>
            )}

            {/* ===== COMPLETED ===== */}
            {status === 'completed' && result && (
                <div className="space-y-4 animate-fade-up">
                    <div className={`card p-8 text-center space-y-4 ${scoreGlow(result.averageScore)}`}>
                        <CheckCircle2 size={32} className="text-score-high mx-auto" />
                        <h2 className="text-[15px] font-display font-bold text-text-primary">Evaluation Complete</h2>
                        <p className="text-[12px] text-text-secondary">
                            {result.taskResults.length} tasks · {result.judgeModels.length} judges
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
                        <Stat label="Avg score" value={String(result.averageScore)} color={scoreColor(result.averageScore)} />
                        <Stat label="Best score" value={String(result.bestScore)} color={scoreColor(result.bestScore)} />
                        <Stat label="Tasks" value={String(result.taskResults.length)} />
                    </div>

                    <div className="flex gap-2">
                        <button
                            onClick={() => { setResult(result); navigate('/results'); }}
                            className="flex-1 py-2.5 bg-amber text-bg rounded-md text-[13px] font-display font-semibold flex items-center justify-center gap-2 hover:bg-amber-hover transition-all duration-200 hover:shadow-[0_0_24px_rgba(226,168,75,0.15)]"
                        >
                            <ArrowRight size={14} />
                            View Results
                        </button>
                        <button onClick={handleReset} className="px-4 py-2.5 border border-border rounded-md text-[12px] text-text-secondary hover:text-text-primary hover:border-border-focus transition-colors duration-150">
                            New Run
                        </button>
                    </div>
                </div>
            )}

            {/* ===== CANCELLED ===== */}
            {status === 'cancelled' && (
                <div className="space-y-4 animate-fade-up">
                    <div className="card p-8 text-center space-y-3">
                        <XCircle size={32} className="text-score-mid mx-auto" />
                        <h2 className="text-[15px] font-display font-bold text-text-primary">Evaluation Cancelled</h2>
                        <p className="text-[12px] text-text-secondary">
                            {progress?.currentStep || 0} / {progress?.totalSteps || totalSteps} steps completed
                        </p>
                    </div>
                    <button
                        onClick={handleReset}
                        className="w-full py-2.5 border border-border rounded-md text-[12px] text-text-secondary hover:text-text-primary hover:border-border-focus flex items-center justify-center gap-2 transition-colors duration-150"
                    >
                        <Play size={13} /> Start Over
                    </button>
                </div>
            )}

            {/* ===== ERROR ===== */}
            {status === 'error' && (
                <div className="space-y-4 animate-fade-up">
                    <div className="card p-8 text-center space-y-3 accent-bar-low">
                        <AlertCircle size={32} className="text-score-low mx-auto" />
                        <h2 className="text-[15px] font-display font-bold text-text-primary">Evaluation Failed</h2>
                        <p className="text-[12px] text-text-secondary">{errorMessage}</p>
                    </div>
                    <button
                        onClick={handleReset}
                        className="w-full py-2.5 border border-border rounded-md text-[12px] text-text-secondary hover:text-text-primary hover:border-border-focus flex items-center justify-center gap-2 transition-colors duration-150"
                    >
                        <Play size={13} /> Start Over
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

/* ======= Segment Progress Bar ======= */
function SegmentProgressBar({ total, currentTaskIndex, completed }: { total: number; currentTaskIndex: number; completed: boolean }) {
    const segments = Array.from({ length: total }, (_, i) => {
        if (completed) return 'done';
        if (i < currentTaskIndex) return 'done';
        if (i === currentTaskIndex) return 'active';
        return 'pending';
    });

    return (
        <div className="flex gap-1">
            {segments.map((state, i) => (
                <div
                    key={i}
                    className={`h-2 flex-1 rounded-sm transition-all duration-300 ${state === 'done'
                        ? 'bg-amber'
                        : state === 'active'
                            ? 'bg-amber animate-pulse-amber'
                            : 'bg-border'
                        }`}
                    style={state === 'active' ? { boxShadow: '0 0 8px rgba(226, 168, 75, 0.3)' } : undefined}
                />
            ))}
        </div>
    );
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
