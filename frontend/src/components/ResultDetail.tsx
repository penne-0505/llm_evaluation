import type { EvaluationRun, JudgeEvaluation, TaskType } from '../types';
import { format } from 'date-fns';
import {
    AlertTriangle,
    AlertCircle,
    ChevronDown,
    ChevronUp,
    FileText,
    Wrench,
    CheckCircle,
    XCircle,
    DollarSign,
    Coins,
    TrendingUp,
    Clock,
    Layers,
    Cpu,
    Gavel,
    Timer,
} from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import { TASK_TYPE_LABELS, TASK_TYPE_STYLE } from '../lib/taskTypeStyles';
import { CONFIDENCE_META } from '../lib/confidence';
import { formatTaskTimingBreakdown } from '../lib/taskTiming';
import {
    computeTimeRoi,
    resolveTimeRoiDenominator,
    resolveTimingSummary,
} from '../lib/timeRoi';
import {
    computeJudgeSummaries,
    computeReviewFlags,
    formatHeroScore,
    formatReliabilityReason,
    HIGH_VARIANCE_STD_THRESHOLD,
    isHeroScoreAvailable,
} from '../lib/judgeReliability';
import Button from './Button';

function scoreColor(score: number | null | undefined): string {
    if (!isHeroScoreAvailable(score)) return 'text-text-tertiary';
    if (score >= 80) return 'text-score-high';
    if (score >= 60) return 'text-score-mid';
    return 'text-score-low';
}

function scoreBg(score: number | null | undefined): string {
    if (!isHeroScoreAvailable(score)) return 'bg-border';
    if (score >= 80) return 'bg-score-high';
    if (score >= 60) return 'bg-score-mid';
    return 'bg-score-low';
}

function scoreGlow(score: number | null | undefined): string {
    if (!isHeroScoreAvailable(score)) return '';
    if (score >= 80) return 'glow-high';
    if (score >= 60) return 'glow-mid';
    return 'glow-low';
}

const TASK_TYPE_AXIS_MAX: Record<TaskType, { logicAndFact: number; constraintAdherence: number; helpfulness: number }> = {
    fact: { logicAndFact: 60, constraintAdherence: 30, helpfulness: 10 },
    creative: { logicAndFact: 30, constraintAdherence: 30, helpfulness: 40 },
    speculative: { logicAndFact: 40, constraintAdherence: 20, helpfulness: 40 },
    holistic: { logicAndFact: 40, constraintAdherence: 30, helpfulness: 30 },
};

function normalizeScore(score: number, maxScore: number): number {
    if (maxScore <= 0) return 0;
    return Math.max(0, Math.min(100, (score / maxScore) * 100));
}

function normalizedScoreColor(score: number, maxScore: number): string {
    return scoreColor(normalizeScore(score, maxScore));
}

function normalizedScoreBg(score: number, maxScore: number): string {
    return scoreBg(normalizeScore(score, maxScore));
}

function isHighTrialVariance(sd: number): boolean {
    return sd > HIGH_VARIANCE_STD_THRESHOLD;
}

function formatTrialSd(sd: number): string {
    return Number.isInteger(sd) ? String(sd) : sd.toFixed(1);
}

export default function ResultDetail({ run }: { run: EvaluationRun }) {
    // 詳細データが未ロードの場合（リロード後など）は案内を表示
    if (run.taskResults.length === 0 && run.holisticTaskResults.length === 0) {
        return (
            <div className="card p-8 text-center space-y-3 animate-fade-up">
                <p className="text-[14px] font-medium text-text-secondary">
                    結果の詳細データが読み込まれていません
                </p>
                <p className="text-[12px] text-text-tertiary">
                    ダッシュボード（結果一覧）から選択し直してください。
                </p>
            </div>
        );
    }

    const summaries = computeJudgeSummaries(run);
    const flags = computeReviewFlags(run);
    const aggregation = run.scoreAggregation;
    const excludeOn = Boolean(run.excludeUnreliableJudges);
    const allExcluded = Boolean(aggregation?.allExcluded);
    const heroAvailable = isHeroScoreAvailable(run.averageScore);

    return (
        <div className="space-y-8 animate-fade-up">
            {/* Hero — Asymmetric Score Display */}
            <div className={`card p-6 hero-glow ${scoreGlow(run.averageScore)}`}>
                <div className="relative z-10 flex flex-col md:flex-row md:items-center gap-6">
                    {/* Left: Big Score */}
                    <div className="flex flex-col items-center md:items-start md:w-1/3">
                        <AnimatedScore value={run.averageScore} />
                        {heroAvailable ? (
                            <GaugeBar value={run.averageScore as number} className="w-full mt-3" />
                        ) : (
                            <p className="mt-3 text-[12px] text-score-low">
                                {allExcluded
                                    ? '全評価モデル除外のため総合点は N/A'
                                    : '総合点データなし'}
                            </p>
                        )}
                    </div>

                    {/* Right: Metadata */}
                    <div className="flex-1 grid grid-cols-2 gap-4">
                        <div className="col-span-2 flex flex-wrap gap-2">
                            {run.strictMode?.enforced && (
                                <span className="rounded-full border border-score-high/25 bg-score-high/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-score-high">
                                    strict run
                                </span>
                            )}
                            {run.strictMode?.requested && !run.strictMode?.enforced && (
                                <span className="rounded-full border border-score-low/25 bg-score-low/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-score-low">
                                    strict rejected
                                </span>
                            )}
                            {excludeOn && (
                                <span className="rounded-full border border-amber/25 bg-amber/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-amber">
                                    unreliable judges excluded
                                </span>
                            )}
                        </div>
                        <div>
                            <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-0.5">被験モデル</p>
                            <p className="text-[13px] font-medium text-text-primary">{run.subjectModelName}</p>
                        </div>
                        <div>
                            <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-0.5">実行日時</p>
                            <p className="text-[13px] text-text-primary">
                                {format(new Date(run.timestamp), 'yyyy/MM/dd HH:mm')}
                            </p>
                        </div>
                        <div>
                            <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-0.5">最高点</p>
                            <p className={`data-display text-lg ${scoreColor(run.bestScore)}`}>
                                {formatHeroScore(run.bestScore)}
                            </p>
                        </div>
                        <div>
                            <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-0.5">タスク数</p>
                            <p className="data-display text-lg text-text-primary">{run.taskCount}</p>
                        </div>
                        <div className="col-span-2">
                            <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-1">評価モデル</p>
                            <div className="flex flex-wrap gap-1">
                                {run.judgeModels.length > 0 ? (
                                    run.judgeModels.map((j) => (
                                        <span key={j.id} className="px-1.5 py-0.5 bg-surface-hover rounded text-[11px] text-text-secondary">
                                            {j.name}
                                        </span>
                                    ))
                                ) : run.judgeCount ? (
                                    <span className="text-[11px] text-text-tertiary">{run.judgeCount} 件</span>
                                ) : null}
                            </div>
                        </div>
                        {(run.holisticJudgeModels?.length ?? 0) > 0 && (
                            <div className="col-span-2">
                                <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-1">包括評価モデル</p>
                                <div className="flex flex-wrap gap-1">
                                    {run.holisticJudgeModels!.map((j) => (
                                        <span key={j.id} className="px-1.5 py-0.5 bg-surface-hover rounded text-[11px] text-text-secondary">
                                            {j.name}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {excludeOn && aggregation && (
                <ExclusionSummaryCard aggregation={aggregation} />
            )}

            <ConfidenceGuide />

            <CostSection run={run} />

            {/* Per-Task Results */}
            <section className="space-y-2">
                <h2 className="section-label">タスク別結果</h2>
                {run.taskResults.map((tr, i) => (
                    <TaskResultCard key={tr.taskId} tr={tr} delay={i * 30} />
                ))}
            </section>

            {/* Holistic Evaluation Results */}
            {run.holisticTaskResults.length > 0 && (
                <section className="space-y-2">
                    <div className="flex items-center gap-2 flex-wrap">
                        <h2 className="section-label">包括評価</h2>
                        <span className="text-[10px] text-text-tertiary">全出力を横断した文体・言語運用評価</span>
                        {(run.holisticJudgeModels?.length ?? 0) > 0 && (
                            <span className="text-[10px] text-text-tertiary">
                                · judge: {run.holisticJudgeModels!.map((j) => j.name).join(', ')}
                            </span>
                        )}
                    </div>
                    {run.holisticTaskResults.map((tr, i) => (
                        <TaskResultCard key={tr.taskId} tr={tr} delay={i * 30} />
                    ))}
                </section>
            )}

            {/* Cross-Task Summary */}
            <section className="space-y-3">
                <h2 className="section-label">横断サマリー</h2>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                    {summaries.map((s) => (
                        <div key={s.judgeModelId} className={`card p-4 accent-bar-ice ${scoreGlow(s.averageScore)}`}>
                            <p className="text-[12px] text-text-secondary mb-2">{s.judgeModelName}</p>
                            <div className="flex items-end justify-between">
                                <p className={`data-display text-lg ${scoreColor(s.averageScore)}`}>{s.averageScore}</p>
                                <p className="text-[11px] text-text-tertiary">{s.tasksEvaluated} タスク</p>
                            </div>
                            <GaugeBar value={s.averageScore} className="mt-2" />
                        </div>
                    ))}
                </div>
                {summaries.length === 0 && (
                    <p className="text-[12px] text-text-tertiary">
                        {excludeOn
                            ? '信頼性フィルタにより、横断サマリーに残る評価モデルがありません'
                            : '横断サマリー用の評価結果がありません'}
                    </p>
                )}

                {flags.length > 0 && (
                    <div className="space-y-1.5">
                        <h3 className="text-[12px] font-medium text-text-secondary flex items-center gap-1.5">
                            <AlertTriangle size={13} className="text-score-mid" />
                            要確認 {flags.length} 件
                        </h3>
                        {flags.map((f, i) => (
                            <div key={i} className="card p-3 flex items-start gap-3 accent-bar-mid">
                                <AlertTriangle size={13} className="text-score-mid shrink-0 mt-0.5" />
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-1.5 mb-1">
                                        <span className="data-display text-[12px] text-text-primary">{f.taskId}</span>
                                        <span className="text-text-tertiary">·</span>
                                        <span className="text-[12px] text-text-secondary">{f.judgeModelName}</span>
                                    </div>
                                    <div className="flex flex-wrap gap-1">
                                        {f.reasons.map((r, j) => (
                                            <span key={j} className="px-1.5 py-0.5 bg-score-mid/10 rounded text-[10px] text-score-mid">{r}</span>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </section>
        </div>
    );
}

/* ======= Exclusion summary (AC-003 / AC-004) ======= */
function ExclusionSummaryCard({
    aggregation,
}: {
    aggregation: NonNullable<EvaluationRun['scoreAggregation']>;
}) {
    return (
        <section className="card p-4 space-y-3 accent-bar-ice">
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                    <h2 className="section-label mb-1">信頼性フィルタ</h2>
                    <p className="text-[12px] text-text-secondary">
                        除外前後の総合点と、除外された評価モデル系統
                    </p>
                </div>
                {aggregation.allExcluded && (
                    <span className="inline-flex items-center gap-1 rounded-md border border-score-low/20 bg-score-low/8 px-2 py-1 text-[11px] text-score-low">
                        <AlertTriangle size={12} />
                        全系統除外 · 総合点 N/A
                    </span>
                )}
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                    <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-0.5">除外前 平均</p>
                    <p className="data-display text-[15px] text-text-primary">
                        {formatHeroScore(aggregation.averageScoreBefore)}
                    </p>
                </div>
                <div>
                    <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-0.5">除外後 平均</p>
                    <p className={`data-display text-[15px] ${scoreColor(aggregation.averageScoreAfter)}`}>
                        {formatHeroScore(aggregation.averageScoreAfter)}
                    </p>
                </div>
                <div>
                    <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-0.5">除外前 最高</p>
                    <p className="data-display text-[15px] text-text-primary">
                        {formatHeroScore(aggregation.bestScoreBefore)}
                    </p>
                </div>
                <div>
                    <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-0.5">除外後 最高</p>
                    <p className={`data-display text-[15px] ${scoreColor(aggregation.bestScoreAfter)}`}>
                        {formatHeroScore(aggregation.bestScoreAfter)}
                    </p>
                </div>
            </div>

            {aggregation.excludedJudges.length > 0 ? (
                <ul className="space-y-2">
                    {aggregation.excludedJudges.map((entry) => (
                        <li
                            key={entry.judgeId}
                            className="rounded-md border border-border/70 bg-surface-hover/40 px-3 py-2"
                        >
                            <p className="text-[12px] font-medium text-text-primary">{entry.judgeId}</p>
                            <p className="text-[11px] text-text-secondary mt-0.5">
                                {entry.reasons.map(formatReliabilityReason).join(' · ')}
                            </p>
                        </li>
                    ))}
                </ul>
            ) : (
                <p className="text-[12px] text-text-tertiary">除外対象の評価モデルはありませんでした</p>
            )}
        </section>
    );
}

/* ======= Animated Score ======= */
function AnimatedScore({ value }: { value: number | null }) {
    const [display, setDisplay] = useState(0);
    const ref = useRef<number | null>(null);
    const available = isHeroScoreAvailable(value);

    useEffect(() => {
        if (!available) return;
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
    }, [value, available]);

    if (!available) {
        return <span className="data-display text-5xl text-text-tertiary">N/A</span>;
    }

    return (
        <span className={`data-display text-5xl ${scoreColor(value)}`}>
            {display.toFixed(1)}
        </span>
    );
}

/* ======= Gauge Bar ======= */
function GaugeBar({ value, className = '', barClassName }: { value: number; className?: string; barClassName?: string }) {
    return (
        <div className={`h-1.5 bg-border/60 rounded-full overflow-hidden ${className}`}>
            <div
                className={`h-full ${barClassName || scoreBg(value)} rounded-full`}
                style={{
                    width: `${value}%`,
                    animation: 'countup-bar 0.6s cubic-bezier(0.16, 1, 0.3, 1) both',
                }}
            />
        </div>
    );
}

/* ======= Task Result Card ======= */
function TaskResultCard({ tr, delay }: { tr: EvaluationRun['taskResults'][0]; delay: number }) {
    const [expanded, setExpanded] = useState(false);
    const showToolUi = tr.hasSubjectTools || tr.toolTrace.length > 0;
    const timingLabel = formatTaskTimingBreakdown(tr.taskTiming);

    return (
        <div
            className="card overflow-hidden animate-fade-up"
            style={{ animationDelay: `${delay}ms` }}
        >
            <Button
                onClick={() => setExpanded(!expanded)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-surface-hover transition-colors duration-150 group"
            >
                <div className="flex items-center gap-2 min-w-0">
                    <span className="data-display text-[13px] text-text-primary">{tr.taskId}</span>
                    <span className={`px-1.5 py-0 rounded text-[10px] font-medium ${TASK_TYPE_STYLE[tr.taskType]}`}>
                        {TASK_TYPE_LABELS[tr.taskType] || tr.taskType}
                    </span>
                    {showToolUi && <ToolStatusBadge toolTrace={tr.toolTrace} hasSubjectTools={tr.hasSubjectTools} />}
                    {timingLabel && (
                        <span className="hidden sm:inline text-[10px] text-text-tertiary tabular-nums">
                            {timingLabel}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-3">
                    {/* Mini scores + trial variance preview */}
                    {!expanded && tr.judgeEvaluations.length > 0 && (
                        <div className="flex max-w-[min(55vw,32rem)] flex-wrap items-center justify-end gap-x-2.5 gap-y-1">
                            {tr.judgeEvaluations.map((je) => {
                                const highVariance = isHighTrialVariance(je.totalScore.sd);
                                return (
                                    <span
                                        key={je.judgeModelId}
                                        className="inline-flex items-baseline gap-1 shrink-0"
                                        title={`${je.judgeModelName}: 試行間 SD ${formatTrialSd(je.totalScore.sd)}${highVariance ? `（閾値 ${HIGH_VARIANCE_STD_THRESHOLD} 超過）` : ''}`}
                                    >
                                        <span className={`data-display text-[11px] ${scoreColor(je.totalScore.mean)}`}>
                                            {je.totalScore.mean}
                                        </span>
                                        <span className={`text-[9px] tabular-nums ${highVariance ? 'text-score-mid' : 'text-text-tertiary'}`}>
                                            試行間 SD {formatTrialSd(je.totalScore.sd)}
                                        </span>
                                        {highVariance && (
                                            <AlertTriangle size={10} className="text-score-mid shrink-0 self-center" aria-label="ばらつき大" />
                                        )}
                                    </span>
                                );
                            })}
                        </div>
                    )}
                    {expanded ? <ChevronUp size={14} className="text-text-tertiary" /> : <ChevronDown size={14} className="text-text-tertiary" />}
                </div>
            </Button>

            {expanded && (
                <div className="px-4 pb-4 space-y-4 border-t border-border animate-fade-in">
                    {timingLabel && (
                        <div className="pt-3 flex items-center gap-1.5 text-[11px] text-text-secondary">
                            <Timer size={12} className="text-text-tertiary" />
                            <span>所要時間（usage 実測）: {timingLabel}</span>
                        </div>
                    )}
                    <div className={`space-y-1.5 ${timingLabel ? '' : 'pt-3'}`}>
                        <p className="text-[9px] text-text-tertiary uppercase tracking-wider">被験モデルの回答</p>
                        <SubjectResponseSection tr={tr} />
                    </div>

                    <InputPromptSection inputPrompt={tr.inputPrompt} subjectPrompt={tr.subjectPrompt} />
                    <ToolTraceSection toolTrace={tr.toolTrace} hasSubjectTools={tr.hasSubjectTools} />

                    <div className="space-y-2">
                        {tr.judgeEvaluations.map((je) => (
                            <JudgeEvaluationCard key={je.judgeModelId} je={je} taskType={tr.taskType} />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

/* ======= Subject multi-run responses ======= */
function SubjectResponseSection({ tr }: { tr: EvaluationRun['taskResults'][0] }) {
    const runs = tr.subjectRuns?.length ? tr.subjectRuns : null;
    const [activeRun, setActiveRun] = useState(0);

    if (!runs || runs.length <= 1) {
        return (
            <div className="h-48 min-h-24 max-h-[70vh] resize-y overflow-y-auto rounded bg-bg p-3 text-[12px] leading-relaxed text-text-secondary whitespace-pre-wrap">
                {tr.subjectResponse}
            </div>
        );
    }

    const selected = runs[Math.min(activeRun, runs.length - 1)];
    return (
        <div className="space-y-2">
            <div className="flex flex-wrap gap-1.5">
                {runs.map((run, index) => (
                    <Button
                        key={run.runIndex}
                        onClick={() => setActiveRun(index)}
                        className={`px-2 py-0.5 rounded text-[10px] border transition-colors ${
                            index === activeRun
                                ? 'border-amber/40 bg-amber-dim text-amber'
                                : 'border-border text-text-tertiary hover:border-border-focus'
                        }`}
                    >
                        試行 #{run.runIndex}
                        {run.error ? ' · ERROR' : ''}
                    </Button>
                ))}
                <span className="self-center text-[10px] text-text-tertiary">
                    {tr.subjectRunCount || runs.length} 回（judge へ list-eval 束ね）
                </span>
            </div>
            {selected.error && (
                <p className="text-[11px] text-score-low">エラー: {selected.error}</p>
            )}
            <div className="h-48 min-h-24 max-h-[70vh] resize-y overflow-y-auto rounded bg-bg p-3 text-[12px] leading-relaxed text-text-secondary whitespace-pre-wrap">
                {selected.response}
            </div>
            {selected.subjectUsage && (
                <p className="text-[10px] text-text-tertiary tabular-nums">
                    tokens in/out: {selected.subjectUsage.inputTokens}/{selected.subjectUsage.outputTokens}
                    {' · '}total {selected.subjectUsage.totalTokens}
                </p>
            )}
        </div>
    );
}

function ToolStatusBadge({ toolTrace, hasSubjectTools }: { toolTrace: import('../types').ToolTraceStep[]; hasSubjectTools: boolean }) {
    if (!hasSubjectTools && toolTrace.length === 0) return null;

    if (toolTrace.length === 0) {
        return (
            <span className="inline-flex items-center gap-1 px-1.5 py-0 rounded text-[10px] font-medium bg-surface-hover text-text-tertiary">
                <Wrench size={9} />
                tool 未使用
            </span>
        );
    }

    const failCount = toolTrace.filter((s) => !s.ok).length;
    return (
        <span className={`inline-flex items-center gap-1 px-1.5 py-0 rounded text-[10px] font-medium ${failCount > 0 ? 'bg-score-mid/10 text-score-mid' : 'bg-ice/10 text-ice'}`}>
            <Wrench size={9} />
            tool {toolTrace.length}
            {failCount > 0 ? ` · 失敗 ${failCount}` : ''}
        </span>
    );
}

/* ======= Input Prompt Section ======= */
function InputPromptSection({ inputPrompt, subjectPrompt }: { inputPrompt: string; subjectPrompt: string }) {
    const [show, setShow] = useState(false);
    const [showOriginal, setShowOriginal] = useState(false);
    const effectivePrompt = subjectPrompt || inputPrompt;
    const hasBoth = subjectPrompt && subjectPrompt !== inputPrompt;

    if (!effectivePrompt) return null;

    return (
        <div className="space-y-2">
            <Button
                onClick={() => setShow(!show)}
                className="text-[11px] text-ice hover:text-amber transition-colors flex items-center gap-1.5"
            >
                {show ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                <FileText size={11} />
                {show ? 'プロンプトを隠す' : 'プロンプトを表示'}
            </Button>
            {show && (
                <div className="space-y-2 animate-fade-in">
                    <div className="bg-bg rounded p-3 text-[11px] text-text-secondary leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto border border-border">
                        {effectivePrompt}
                    </div>
                    {hasBoth && (
                        <div>
                            <Button
                                onClick={() => setShowOriginal(!showOriginal)}
                                className="text-[10px] text-text-tertiary hover:text-text-secondary transition-colors flex items-center gap-1"
                            >
                                {showOriginal ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                                {showOriginal ? '元のプロンプトを隠す' : '元のプロンプトを表示'}
                            </Button>
                            {showOriginal && (
                                <div className="mt-1 bg-bg rounded p-3 text-[11px] text-text-tertiary leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto border border-border animate-fade-in">
                                    {inputPrompt}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

/* ======= Tool Trace Section ======= */
function ToolTraceSection({
    toolTrace,
    hasSubjectTools,
}: {
    toolTrace: import('../types').ToolTraceStep[];
    hasSubjectTools: boolean;
}) {
    const [show, setShow] = useState(false);
    // Show when tools were defined (incl. unused) or when a legacy result has a non-empty trace.
    if (!hasSubjectTools && toolTrace.length === 0) return null;

    if (toolTrace.length === 0) {
        return (
            <div className="flex items-center gap-2 rounded border border-border bg-bg px-3 py-2">
                <Wrench size={11} className="text-text-tertiary shrink-0" />
                <div className="min-w-0">
                    <p className="text-[11px] text-text-secondary">tool 定義あり・未使用</p>
                    <p className="text-[10px] text-text-tertiary">
                        このタスクには subject tools が定義されていましたが、被験モデルは呼び出しませんでした。
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-2">
            <Button
                onClick={() => setShow(!show)}
                className="text-[11px] text-ice hover:text-amber transition-colors flex items-center gap-1.5"
            >
                {show ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                <Wrench size={11} />
                {show ? 'ツール呼び出しを隠す' : 'ツール呼び出しを表示'} ({toolTrace.length})
            </Button>
            {show && (
                <div className="space-y-2 animate-fade-in">
                    {toolTrace.map((step, i) => (
                        <ToolTraceStepCard key={i} step={step} />
                    ))}
                </div>
            )}
        </div>
    );
}

/* ======= Tool Trace Step Card ======= */
function ToolTraceStepCard({ step }: { step: import('../types').ToolTraceStep }) {
    const [showDetail, setShowDetail] = useState(false);
    const hasDetail = step.resultDetail && step.resultDetail.length > 0;
    const detailJson = (() => {
        if (!hasDetail) return null;
        try {
            const parsed = JSON.parse(step.resultDetail);
            return JSON.stringify(parsed, null, 2);
        } catch {
            return step.resultDetail;
        }
    })();

    return (
        <div className="bg-bg border border-border rounded-md p-3 space-y-2">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className="data-display text-[11px] text-text-primary">Step {step.stepIndex}</span>
                    <span className="px-1.5 py-0 rounded text-[10px] font-medium bg-surface-hover text-text-secondary">
                        {step.toolName}
                    </span>
                </div>
                {step.ok ? (
                    <span className="flex items-center gap-1 text-[10px] text-score-high">
                        <CheckCircle size={10} /> 成功
                    </span>
                ) : (
                    <span className="flex items-center gap-1 text-[10px] text-score-low">
                        <XCircle size={10} /> 失敗
                    </span>
                )}
            </div>
            <div className="space-y-1">
                <p className="text-[9px] text-text-tertiary uppercase tracking-wider">引数</p>
                <pre className="bg-surface rounded p-2 text-[10px] text-text-secondary leading-relaxed whitespace-pre-wrap overflow-x-auto">
                    {JSON.stringify(step.arguments, null, 2)}
                </pre>
            </div>
            <div className="space-y-1">
                <p className="text-[9px] text-text-tertiary uppercase tracking-wider">結果</p>
                <div className="bg-surface rounded p-2 text-[10px] text-text-secondary leading-relaxed whitespace-pre-wrap">
                    {step.resultSummary}
                </div>
            </div>
            {hasDetail && (
                <div>
                    <Button
                        onClick={() => setShowDetail(!showDetail)}
                        className="text-[10px] text-text-tertiary hover:text-text-secondary transition-colors flex items-center gap-1"
                    >
                        {showDetail ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                        {showDetail ? '詳細を隠す' : '詳細を表示'}
                    </Button>
                    {showDetail && detailJson && (
                        <pre className="mt-1 bg-surface rounded p-2 text-[10px] text-text-secondary leading-relaxed whitespace-pre-wrap overflow-x-auto animate-fade-in">
                            {detailJson}
                        </pre>
                    )}
                </div>
            )}
        </div>
    );
}

/* ======= Judge Evaluation Card ======= */
function JudgeEvaluationCard({ je, taskType }: { je: JudgeEvaluation; taskType: TaskType }) {
    const [showReasoning, setShowReasoning] = useState(false);
    const [showApiReasoning, setShowApiReasoning] = useState(false);
    const axisMax = TASK_TYPE_AXIS_MAX[taskType] || TASK_TYPE_AXIS_MAX.fact;
    const totalConfidenceVotes = je.confidenceDistribution.high + je.confidenceDistribution.medium + je.confidenceDistribution.low;
    const highVariance = isHighTrialVariance(je.totalScore.sd);

    return (
        <div className="bg-bg border border-border rounded-md p-4 space-y-3 accent-bar-ice">
            <div className="flex items-center justify-between gap-3">
                <span className="text-[12px] font-medium text-text-secondary">{je.judgeModelName}</span>
                <div className="flex items-baseline gap-2">
                    <span className={`data-display text-[15px] ${scoreColor(je.totalScore.mean)}`}>{je.totalScore.mean}</span>
                    <span className={`inline-flex items-center gap-1 text-[10px] tabular-nums ${highVariance ? 'text-score-mid' : 'text-text-tertiary'}`}>
                        試行間 SD {formatTrialSd(je.totalScore.sd)}
                        {highVariance && <AlertTriangle size={10} className="text-score-mid" aria-label="ばらつき大" />}
                    </span>
                </div>
            </div>

            {/* Gauge Bars */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <ScoreBar label="論理・事実" score={je.logicAndFact} maxScore={axisMax.logicAndFact} />
                <ScoreBar label="制約遵守" score={je.constraintAdherence} maxScore={axisMax.constraintAdherence} />
                <ScoreBar label="有用性" score={je.helpfulness} maxScore={axisMax.helpfulness} />
                <ScoreBar label="合計" score={je.totalScore} maxScore={100} />
            </div>

            <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-3 text-[10px]">
                    <span className="text-text-tertiary">信頼度（judge 自己申告）:</span>
                    <span className={`px-1.5 py-0.5 rounded ${CONFIDENCE_META.high.chipClass}`}>{je.confidenceDistribution.high} {CONFIDENCE_META.high.shortLabel}</span>
                    <span className={`px-1.5 py-0.5 rounded ${CONFIDENCE_META.medium.chipClass}`}>{je.confidenceDistribution.medium} {CONFIDENCE_META.medium.shortLabel}</span>
                    <span className={`px-1.5 py-0.5 rounded ${CONFIDENCE_META.low.chipClass}`}>{je.confidenceDistribution.low} {CONFIDENCE_META.low.shortLabel}</span>

                    {je.criticalFail.detected && (
                        <span className="flex items-center gap-1 px-1.5 py-0.5 bg-danger/10 text-score-low rounded">
                            <AlertCircle size={9} /> {je.criticalFail.reason}
                        </span>
                    )}
                </div>
                <p className="text-[10px] leading-5 text-text-tertiary">
                    試行間 SD は同一 judge の複数試行スコアのばらつきです（閾値 {HIGH_VARIANCE_STD_THRESHOLD}）。信頼度チップ（高/中/低）は judge 自己申告であり別指標です。
                    {totalConfidenceVotes > 0 ? ` 低信頼 ${je.confidenceDistribution.low}/${totalConfidenceVotes} 件。` : ''}
                </p>
            </div>

            {je.reasoningSamples.length > 0 && (
                <div>
                    <Button
                        onClick={() => setShowReasoning(!showReasoning)}
                        className="text-[11px] text-ice hover:text-amber transition-colors flex items-center gap-1"
                    >
                        {showReasoning ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                        {showReasoning ? '採点根拠を隠す' : '採点根拠を表示'} ({je.reasoningSamples.length})
                    </Button>
                    {showReasoning && (
                        <div className="mt-2 space-y-1 animate-fade-in">
                            {je.reasoningSamples.map((r, i) => (
                                <div key={i} className="bg-surface rounded p-2.5 text-[11px] text-text-secondary leading-relaxed">
                                    {r}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {je.apiReasoningSamples.length > 0 && (
                <div>
                    <Button
                        onClick={() => setShowApiReasoning(!showApiReasoning)}
                        className="text-[11px] text-text-tertiary hover:text-ice transition-colors flex items-center gap-1"
                    >
                        {showApiReasoning ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                        {showApiReasoning
                            ? 'API thinking を隠す'
                            : 'API thinking（モデル内部推論）'} ({je.apiReasoningSamples.length})
                    </Button>
                    {showApiReasoning && (
                        <div className="mt-2 space-y-1 animate-fade-in">
                            <p className="text-[10px] text-text-tertiary leading-relaxed">
                                採点根拠とは別です。モデルが API 経由で返した内部推論であり、個人情報が含まれる可能性があります。
                            </p>
                            {je.apiReasoningSamples.map((r, i) => (
                                <div key={i} className="bg-surface rounded p-2.5 text-[11px] text-text-secondary leading-relaxed whitespace-pre-wrap">
                                    {r}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

/* ======= Score Bar ======= */
function ScoreBar({ label, score, maxScore }: { label: string; score: { mean: number; sd: number }; maxScore: number }) {
    const highVariance = label === '合計' && isHighTrialVariance(score.sd);
    return (
        <div className="space-y-1 group/bar">
            <div className="flex items-center justify-between">
                <span className="text-[10px] text-text-tertiary">{label}</span>
                <span className={`data-display text-[11px] ${normalizedScoreColor(score.mean, maxScore)}`}>
                    {score.mean} / {maxScore}
                </span>
            </div>
            <GaugeBar value={normalizeScore(score.mean, maxScore)} barClassName={normalizedScoreBg(score.mean, maxScore)} />
            <p className={`text-[10px] tabular-nums ${highVariance ? 'text-score-mid' : 'text-text-tertiary'}`}>
                試行間 SD {formatTrialSd(score.sd)}
                {highVariance ? ' · 要確認' : ''}
            </p>
        </div>
    );
}

/* ======= Cost Section ======= */
type CostTab = 'total' | 'subject' | 'judge';

function CostSection({ run }: { run: EvaluationRun }) {
    const [activeTab, setActiveTab] = useState<CostTab>('total');

    const hasSubjectSummary = !!run.usageSummarySubject;
    const hasJudgeSummary = !!run.usageSummaryJudge;
    const hasBreakdown = hasSubjectSummary || hasJudgeSummary;

    // 表示対象のサマリーを選択
    let us = run.usageSummary;
    let tabLabel = 'Run全体';
    if (hasBreakdown) {
        if (activeTab === 'subject') {
            us = run.usageSummarySubject;
            tabLabel = '被検モデル';
        } else if (activeTab === 'judge') {
            us = run.usageSummaryJudge;
            tabLabel = 'Judgeモデル';
        }
    }

    if (!us) return null;

    const totalCost = us.totals.estimatedCostUsd;

    // ROI はアクティブなタブのコストで計算
    const subjectCost = run.usageSummarySubject?.totals.estimatedCostUsd;
    const judgeCost = run.usageSummaryJudge?.totals.estimatedCostUsd;
    const hasSubjectCost = subjectCost !== null && subjectCost !== undefined && subjectCost > 0;
    const hasJudgeCost = judgeCost !== null && judgeCost !== undefined && judgeCost > 0;

    let roiCost: number | undefined;
    let roiLabel: string;
    let canCalculateRoi = false;

    if (activeTab === 'subject') {
        roiCost = hasSubjectCost ? subjectCost : undefined;
        roiLabel = '被検コスト';
        canCalculateRoi = hasSubjectCost;
    } else if (activeTab === 'judge') {
        roiCost = hasJudgeCost ? judgeCost : undefined;
        roiLabel = 'Judgeコスト';
        canCalculateRoi = hasJudgeCost;
    } else {
        // Run全体: subject と judge の両方が揃っている場合のみ計算
        roiCost = (hasSubjectCost && hasJudgeCost) ? (subjectCost as number) + (judgeCost as number) : undefined;
        roiLabel = '総コスト';
        canCalculateRoi = hasSubjectCost && hasJudgeCost;
    }

    const roi = canCalculateRoi
        && roiCost !== undefined
        && roiCost > 0
        && isHeroScoreAvailable(run.averageScore)
        && run.averageScore > 0
        ? Number((run.averageScore / roiCost).toFixed(1))
        : undefined;

    const roiSub = roi
        ? `平均点 / ${roiLabel}`
        : canCalculateRoi
            ? '平均点が取得できません'
            : activeTab === 'total'
                ? '被検/Judgeいずれかの価格未設定'
                : `${roiLabel}の価格未設定`;

    // 時間的ROI（タブごと）— task_timing 合算のみ（DEC-001/003）
    const timingSummary = resolveTimingSummary(run);
    const {
        ms: timeRoiMs,
        label: timeRoiLabel,
        available: canCalculateTimeRoi,
    } = resolveTimeRoiDenominator(timingSummary, activeTab);

    const timeRoi = canCalculateTimeRoi
        ? computeTimeRoi(run.averageScore, timeRoiMs)
        : undefined;

    const timeRoiSub = timeRoi
        ? `平均点 / ${timeRoiLabel}`
        : canCalculateTimeRoi
            ? '平均点が取得できません'
            : `${timeRoiLabel}が記録されていません`;

    // 実行時間表示（処理時間合算。欠落時は N/A — wall-clock へ落とさない）
    const displayDurationMs = timeRoiMs;

    return (
        <section className="card p-4 space-y-3">
            <div className="flex items-center justify-between gap-3">
                <h2 className="section-label">コスト・トークン内訳</h2>
                <span className="text-[10px] text-text-tertiary">
                    {us.totals.pricingStatus === 'available' ? '実測' : us.totals.pricingStatus === 'partial' ? '一部推定' : '推定不可'}
                </span>
            </div>

            {/* Category tabs */}
            {hasBreakdown && (
                <div className="border-b border-border">
                    <div className="flex">
                        <CostTabButton
                            active={activeTab === 'total'}
                            onClick={() => setActiveTab('total')}
                            icon={<Layers size={13} />}
                            label="Run全体"
                        />
                        <CostTabButton
                            active={activeTab === 'subject'}
                            onClick={() => setActiveTab('subject')}
                            icon={<Cpu size={13} />}
                            label="被検モデル"
                        />
                        <CostTabButton
                            active={activeTab === 'judge'}
                            onClick={() => setActiveTab('judge')}
                            icon={<Gavel size={13} />}
                            label="Judgeモデル"
                        />
                    </div>
                </div>
            )}

            {!hasBreakdown && (
                <p className="text-[10px] text-text-tertiary">
                    ※旧フォーマットの結果のため、カテゴリ別内訳は表示できません
                </p>
            )}

            {/* Summary cards */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                <CostCard
                    icon={<DollarSign size={12} />}
                    label="推定コスト"
                    value={totalCost !== null && totalCost !== undefined ? `$${totalCost.toFixed(4)}` : '—'}
                    sub={`${us.totals.pricedCallCount}/${us.totals.callCount} 通算`}
                />
                <CostCard
                    icon={<Coins size={12} />}
                    label="総トークン"
                    value={us.totals.totalTokens.toLocaleString()}
                    sub={`入${us.totals.inputTokens.toLocaleString()} / 出${us.totals.outputTokens.toLocaleString()}`}
                />
                <CostCard
                    icon={<TrendingUp size={12} />}
                    label="コストROI"
                    value={roi ? `${roi} 点/$` : '—'}
                    sub={roiSub}
                />
                <CostCard
                    icon={<Timer size={12} />}
                    label="時間ROI"
                    value={timeRoi ? `${timeRoi} 点/秒` : '—'}
                    sub={timeRoiSub}
                />
                <CostCard
                    icon={<Clock size={12} />}
                    label="実行時間"
                    value={typeof displayDurationMs === 'number' && displayDurationMs > 0 ? `${(displayDurationMs / 1000).toFixed(1)}s` : '—'}
                    sub={timingSummary ? timeRoiLabel : '処理時間未記録'}
                />
            </div>

            {/* Per-model breakdown */}
            {us.calls.length > 0 && (
                <div className="space-y-1.5">
                    <p className="text-[9px] text-text-tertiary uppercase tracking-wider">
                        {tabLabel} モデル別内訳
                    </p>
                    <div className="space-y-1.5">
                        {us.calls.map((call, i) => (
                            <div key={i} className="bg-bg rounded border border-border p-2.5 space-y-1.5">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-1.5">
                                        <span className="data-display text-[11px] text-text-primary">{call.model}</span>
                                        <span className="px-1.5 py-0 rounded text-[9px] font-medium bg-surface-hover text-text-secondary">{call.provider}</span>
                                    </div>
                                    <span className="data-display text-[11px] text-text-secondary">
                                        {call.estimatedCostUsd !== null ? `$${call.estimatedCostUsd.toFixed(4)}` : '—'}
                                    </span>
                                </div>
                                <div className="grid grid-cols-3 gap-2 text-[10px] text-text-tertiary">
                                    <span>呼出 {call.callCount} 回</span>
                                    <span>入 {call.inputTokens.toLocaleString()} tk</span>
                                    <span>出 {call.outputTokens.toLocaleString()} tk</span>
                                </div>
                                {call.unpricedCallCount > 0 && (
                                    <p className="text-[9px] text-score-mid">{call.unpricedCallCount} 回は価格未設定のため推定不能</p>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {us.totals.unpricedModels.length > 0 && (
                <p className="text-[10px] text-score-mid">
                    価格未設定モデル: {us.totals.unpricedModels.join(', ')}
                </p>
            )}
        </section>
    );
}

function CostTabButton({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
    return (
        <button
            onClick={onClick}
            className={`relative flex items-center gap-1.5 px-4 py-2.5 text-[11px] font-medium transition-colors select-none ${
                active
                    ? 'text-primary'
                    : 'text-text-tertiary hover:text-text-secondary'
            }`}
        >
            {icon}
            {label}
            {active && (
                <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-primary rounded-t-sm" />
            )}
        </button>
    );
}

function CostCard({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub: string }) {
    return (
        <div className="bg-bg rounded border border-border p-3 space-y-1">
            <div className="flex items-center gap-1 text-text-tertiary">
                {icon}
                <span className="text-[9px] uppercase tracking-wider">{label}</span>
            </div>
            <p className="data-display text-[13px] text-text-primary">{value}</p>
            {sub && <p className="text-[9px] text-text-tertiary">{sub}</p>}
        </div>
    );
}

function ConfidenceGuide() {
    return (
        <section className="card p-4 space-y-3">
            <div className="flex items-center justify-between gap-3">
                <h2 className="section-label">信頼度ガイド</h2>
                <span className="text-[10px] text-text-tertiary">judge の自己申告</span>
            </div>
            <div className="grid gap-2 md:grid-cols-3">
                {Object.entries(CONFIDENCE_META).map(([key, meta]) => (
                    <div key={key} className="rounded-md border border-border bg-bg/80 p-3 space-y-1.5">
                        <span className={`inline-flex rounded px-1.5 py-0.5 text-[10px] ${meta.chipClass}`}>{meta.label}</span>
                        <p className="text-[11px] leading-5 text-text-secondary">{meta.description}</p>
                    </div>
                ))}
            </div>
            <p className="text-[11px] leading-5 text-text-tertiary">
                信頼度は、どの程度手動確認が必要かを見るために使います。低信頼は曖昧さや根拠不足を示し、重大失敗フラグの方がより強い警告です。
            </p>
        </section>
    );
}
