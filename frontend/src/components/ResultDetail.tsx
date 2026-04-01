import type { EvaluationRun, JudgeEvaluation, ReviewFlag, JudgeSummary, TaskType } from '../types';
import { format } from 'date-fns';
import {
    AlertTriangle,
    AlertCircle,
    ChevronDown,
    ChevronUp,
} from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import { TASK_TYPE_LABELS, TASK_TYPE_STYLE } from '../lib/taskTypeStyles';
import { CONFIDENCE_META } from '../lib/confidence';

function scoreColor(score: number): string {
    if (score >= 80) return 'text-score-high';
    if (score >= 60) return 'text-score-mid';
    return 'text-score-low';
}

function scoreBg(score: number): string {
    if (score >= 80) return 'bg-score-high';
    if (score >= 60) return 'bg-score-mid';
    return 'bg-score-low';
}

function scoreGlow(score: number): string {
    if (score >= 80) return 'glow-high';
    if (score >= 60) return 'glow-mid';
    return 'glow-low';
}

const TASK_TYPE_AXIS_MAX: Record<TaskType, { logicAndFact: number; constraintAdherence: number; helpfulness: number }> = {
    fact: { logicAndFact: 60, constraintAdherence: 30, helpfulness: 10 },
    creative: { logicAndFact: 30, constraintAdherence: 30, helpfulness: 40 },
    speculative: { logicAndFact: 40, constraintAdherence: 20, helpfulness: 40 },
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

function computeJudgeSummaries(run: EvaluationRun): JudgeSummary[] {
    const map = new Map<string, { scores: number[]; name: string }>();
    run.taskResults.forEach((tr) => {
        tr.judgeEvaluations.forEach((je) => {
            const existing = map.get(je.judgeModelId) || { scores: [], name: je.judgeModelName };
            existing.scores.push(je.totalScore.mean);
            map.set(je.judgeModelId, existing);
        });
    });
    return Array.from(map.entries()).map(([id, data]) => ({
        judgeModelId: id,
        judgeModelName: data.name,
        averageScore: Math.round((data.scores.reduce((a, b) => a + b, 0) / data.scores.length) * 10) / 10,
        tasksEvaluated: data.scores.length,
    }));
}

function computeReviewFlags(run: EvaluationRun): ReviewFlag[] {
    const flags: ReviewFlag[] = [];
    run.taskResults.forEach((tr) => {
        tr.judgeEvaluations.forEach((je) => {
            const reasons: string[] = [];
            if (je.totalScore.sd > 5) reasons.push(`ばらつき大（SD ${je.totalScore.sd}）`);
            if (je.criticalFail.detected) reasons.push('重大な失敗を検出');
            if (je.confidenceDistribution.low > 0) reasons.push(`低信頼レビュー ${je.confidenceDistribution.low} 件`);
            if (reasons.length > 0) {
                flags.push({ taskId: tr.taskId, judgeModelName: je.judgeModelName, reasons });
            }
        });
    });
    return flags;
}

export default function ResultDetail({ run }: { run: EvaluationRun }) {
    const summaries = computeJudgeSummaries(run);
    const flags = computeReviewFlags(run);

    return (
        <div className="space-y-8 animate-fade-up">
            {/* Hero — Asymmetric Score Display */}
            <div className={`card p-6 hero-glow ${scoreGlow(run.averageScore)}`}>
                <div className="relative z-10 flex flex-col md:flex-row md:items-center gap-6">
                    {/* Left: Big Score */}
                    <div className="flex flex-col items-center md:items-start md:w-1/3">
                        <AnimatedScore value={run.averageScore} />
                        <GaugeBar value={run.averageScore} className="w-full mt-3" />
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
                            <p className={`data-display text-lg ${scoreColor(run.bestScore)}`}>{run.bestScore > 0 ? run.bestScore.toFixed(1) : '\u2014'}</p>
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
                    </div>
                </div>
            </div>

            <ConfidenceGuide />

            {/* Per-Task Results */}
            <section className="space-y-2">
                <h2 className="section-label">タスク別結果</h2>
                {run.taskResults.map((tr, i) => (
                    <TaskResultCard key={tr.taskId} tr={tr} delay={i * 30} />
                ))}
            </section>

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

/* ======= Animated Score ======= */
function AnimatedScore({ value }: { value: number }) {
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

    return (
        <div
            className="card overflow-hidden animate-fade-up"
            style={{ animationDelay: `${delay}ms` }}
        >
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-surface-hover transition-colors duration-150 group"
            >
                <div className="flex items-center gap-2">
                    <span className="data-display text-[13px] text-text-primary">{tr.taskId}</span>
                    <span className={`px-1.5 py-0 rounded text-[10px] font-medium ${TASK_TYPE_STYLE[tr.taskType]}`}>
                        {TASK_TYPE_LABELS[tr.taskType] || tr.taskType}
                    </span>
                </div>
                <div className="flex items-center gap-3">
                    {/* Mini scores preview */}
                    {!expanded && tr.judgeEvaluations.length > 0 && (
                        <div className="flex items-center gap-2">
                            {tr.judgeEvaluations.slice(0, 3).map((je) => (
                                <span key={je.judgeModelId} className={`data-display text-[11px] ${scoreColor(je.totalScore.mean)}`}>
                                    {je.totalScore.mean}
                                </span>
                            ))}
                        </div>
                    )}
                    {expanded ? <ChevronUp size={14} className="text-text-tertiary" /> : <ChevronDown size={14} className="text-text-tertiary" />}
                </div>
            </button>

            {expanded && (
                <div className="px-4 pb-4 space-y-4 border-t border-border animate-fade-in">
                    <div className="pt-3 space-y-1.5">
                        <p className="text-[9px] text-text-tertiary uppercase tracking-wider">被験モデルの回答</p>
                        <div className="bg-bg rounded p-3 text-[12px] text-text-secondary leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
                            {tr.subjectResponse}
                        </div>
                    </div>

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

/* ======= Judge Evaluation Card ======= */
function JudgeEvaluationCard({ je, taskType }: { je: JudgeEvaluation; taskType: TaskType }) {
    const [showReasoning, setShowReasoning] = useState(false);
    const axisMax = TASK_TYPE_AXIS_MAX[taskType] || TASK_TYPE_AXIS_MAX.fact;
    const totalConfidenceVotes = je.confidenceDistribution.high + je.confidenceDistribution.medium + je.confidenceDistribution.low;

    return (
        <div className="bg-bg border border-border rounded-md p-4 space-y-3 accent-bar-ice">
            <div className="flex items-center justify-between">
                <span className="text-[12px] font-medium text-text-secondary">{je.judgeModelName}</span>
                <span className={`data-display text-[15px] ${scoreColor(je.totalScore.mean)}`}>{je.totalScore.mean}</span>
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
                    <span className="text-text-tertiary">信頼度:</span>
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
                    信頼度は、各実行に対する judge 自身の確信度です。低信頼は自動失敗ではなく、手動確認の優先度が高いことを示します。
                    {totalConfidenceVotes > 0 ? ` ${je.confidenceDistribution.low}/${totalConfidenceVotes} 件が低信頼でした。` : ''}
                </p>
            </div>

            {je.reasoningSamples.length > 0 && (
                <div>
                    <button
                        onClick={() => setShowReasoning(!showReasoning)}
                        className="text-[11px] text-ice hover:text-amber transition-colors flex items-center gap-1"
                    >
                        {showReasoning ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                        {showReasoning ? '理由を隠す' : '理由を表示'} ({je.reasoningSamples.length})
                    </button>
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
        </div>
    );
}

/* ======= Score Bar ======= */
function ScoreBar({ label, score, maxScore }: { label: string; score: { mean: number; sd: number }; maxScore: number }) {
    return (
        <div className="space-y-1 group/bar">
            <div className="flex items-center justify-between">
                <span className="text-[10px] text-text-tertiary">{label}</span>
                <span className={`data-display text-[11px] ${normalizedScoreColor(score.mean, maxScore)}`}>
                    {score.mean} / {maxScore}
                </span>
            </div>
            <GaugeBar value={normalizeScore(score.mean, maxScore)} barClassName={normalizedScoreBg(score.mean, maxScore)} />
            <p className="text-[10px] text-text-tertiary">標準偏差 {score.sd}</p>
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
