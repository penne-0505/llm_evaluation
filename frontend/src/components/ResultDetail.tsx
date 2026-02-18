import type { EvaluationRun, JudgeEvaluation, ReviewFlag, JudgeSummary } from '../types';
import { format } from 'date-fns';
import {
    AlertTriangle,
    AlertCircle,
    ChevronDown,
    ChevronUp,
} from 'lucide-react';
import { useState, useEffect, useRef } from 'react';

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
            if (je.totalScore.sd > 5) reasons.push(`High variance (SD ${je.totalScore.sd})`);
            if (je.criticalFail.detected) reasons.push('Critical failure detected');
            if (je.confidenceDistribution.low > 0) reasons.push(`${je.confidenceDistribution.low} low-confidence scores`);
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
                        <div>
                            <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-0.5">Subject</p>
                            <p className="text-[13px] font-medium text-text-primary">{run.subjectModelName}</p>
                        </div>
                        <div>
                            <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-0.5">Timestamp</p>
                            <p className="text-[13px] text-text-primary">
                                {format(new Date(run.timestamp), 'MMM d, yyyy HH:mm')}
                            </p>
                        </div>
                        <div>
                            <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-0.5">Best Score</p>
                            <p className={`data-display text-lg ${scoreColor(run.bestScore)}`}>{run.bestScore > 0 ? run.bestScore.toFixed(1) : '\u2014'}</p>
                        </div>
                        <div>
                            <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-0.5">Tasks</p>
                            <p className="data-display text-lg text-text-primary">{run.taskCount}</p>
                        </div>
                        <div className="col-span-2">
                            <p className="text-[9px] text-text-tertiary uppercase tracking-wider mb-1">Judges</p>
                            <div className="flex flex-wrap gap-1">
                                {run.judgeModels.length > 0 ? (
                                    run.judgeModels.map((j) => (
                                        <span key={j.id} className="px-1.5 py-0.5 bg-surface-hover rounded text-[11px] text-text-secondary">
                                            {j.name}
                                        </span>
                                    ))
                                ) : run.judgeCount ? (
                                    <span className="text-[11px] text-text-tertiary">{run.judgeCount} judge{run.judgeCount > 1 ? 's' : ''}</span>
                                ) : null}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Per-Task Results */}
            <section className="space-y-2">
                <h2 className="section-label">Per-Task Results</h2>
                {run.taskResults.map((tr, i) => (
                    <TaskResultCard key={tr.taskId} tr={tr} delay={i * 30} />
                ))}
            </section>

            {/* Cross-Task Summary */}
            <section className="space-y-3">
                <h2 className="section-label">Cross-Task Summary</h2>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                    {summaries.map((s) => (
                        <div key={s.judgeModelId} className={`card p-4 accent-bar-ice ${scoreGlow(s.averageScore)}`}>
                            <p className="text-[12px] text-text-secondary mb-2">{s.judgeModelName}</p>
                            <div className="flex items-end justify-between">
                                <p className={`data-display text-lg ${scoreColor(s.averageScore)}`}>{s.averageScore}</p>
                                <p className="text-[11px] text-text-tertiary">{s.tasksEvaluated} tasks</p>
                            </div>
                            <GaugeBar value={s.averageScore} className="mt-2" />
                        </div>
                    ))}
                </div>

                {flags.length > 0 && (
                    <div className="space-y-1.5">
                        <h3 className="text-[12px] font-medium text-text-secondary flex items-center gap-1.5">
                            <AlertTriangle size={13} className="text-score-mid" />
                            {flags.length} flagged {flags.length === 1 ? 'evaluation' : 'evaluations'}
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
function GaugeBar({ value, className = '' }: { value: number; className?: string }) {
    return (
        <div className={`h-1.5 bg-border/60 rounded-full overflow-hidden ${className}`}>
            <div
                className={`h-full ${scoreBg(value)} rounded-full`}
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
                    <span className="px-1.5 py-0 rounded text-[10px] font-medium bg-amber-dim text-amber">
                        {tr.taskType}
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
                        <p className="text-[9px] text-text-tertiary uppercase tracking-wider">Subject Response</p>
                        <div className="bg-bg rounded p-3 text-[12px] text-text-secondary leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
                            {tr.subjectResponse}
                        </div>
                    </div>

                    <div className="space-y-2">
                        {tr.judgeEvaluations.map((je) => (
                            <JudgeEvaluationCard key={je.judgeModelId} je={je} />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

/* ======= Judge Evaluation Card ======= */
function JudgeEvaluationCard({ je }: { je: JudgeEvaluation }) {
    const [showReasoning, setShowReasoning] = useState(false);

    return (
        <div className="bg-bg border border-border rounded-md p-4 space-y-3 accent-bar-ice">
            <div className="flex items-center justify-between">
                <span className="text-[12px] font-medium text-text-secondary">{je.judgeModelName}</span>
                <span className={`data-display text-[15px] ${scoreColor(je.totalScore.mean)}`}>{je.totalScore.mean}</span>
            </div>

            {/* Gauge Bars */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <ScoreBar label="Logic & Fact" score={je.logicAndFact} />
                <ScoreBar label="Constraint" score={je.constraintAdherence} />
                <ScoreBar label="Helpfulness" score={je.helpfulness} />
                <ScoreBar label="Total" score={je.totalScore} />
            </div>

            <div className="flex flex-wrap items-center gap-3 text-[10px]">
                <span className="text-text-tertiary">Confidence:</span>
                <span className="px-1.5 py-0.5 bg-score-high/10 text-score-high rounded">{je.confidenceDistribution.high} high</span>
                <span className="px-1.5 py-0.5 bg-score-mid/10 text-score-mid rounded">{je.confidenceDistribution.medium} med</span>
                <span className="px-1.5 py-0.5 bg-score-low/10 text-score-low rounded">{je.confidenceDistribution.low} low</span>

                {je.criticalFail.detected && (
                    <span className="flex items-center gap-1 px-1.5 py-0.5 bg-danger/10 text-score-low rounded">
                        <AlertCircle size={9} /> {je.criticalFail.reason}
                    </span>
                )}
            </div>

            {je.reasoningSamples.length > 0 && (
                <div>
                    <button
                        onClick={() => setShowReasoning(!showReasoning)}
                        className="text-[11px] text-ice hover:text-amber transition-colors flex items-center gap-1"
                    >
                        {showReasoning ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                        {showReasoning ? 'Hide' : 'Show'} reasoning ({je.reasoningSamples.length})
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
function ScoreBar({ label, score }: { label: string; score: { mean: number; sd: number } }) {
    return (
        <div className="space-y-1 group/bar">
            <div className="flex items-center justify-between">
                <span className="text-[10px] text-text-tertiary">{label}</span>
                <span className={`data-display text-[11px] ${scoreColor(score.mean)}`}>
                    {score.mean}
                </span>
            </div>
            <GaugeBar value={score.mean} />
        </div>
    );
}
