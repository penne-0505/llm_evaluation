import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useHistoryStore } from '../store/historyStore';
import type { EvaluationRun } from '../types';
import { formatDistanceToNow, format } from 'date-fns';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import {
    ChevronLeft, ChevronRight, AlertCircle, ArrowRight,
} from 'lucide-react';

const PAGE_SIZE = 4;

function scoreBarColor(score: number): string {
    if (score >= 80) return '#7cc474';
    if (score >= 60) return '#d4a84b';
    return '#c45c5c';
}

function scoreTextColor(score: number): string {
    if (score >= 80) return 'text-score-high';
    if (score >= 60) return 'text-score-mid';
    return 'text-score-low';
}

function scoreGlow(score: number): string {
    if (score >= 80) return 'glow-high';
    if (score >= 60) return 'glow-mid';
    return 'glow-low';
}

export default function DashboardPage() {
    const { runs, isLoaded, loadError } = useHistoryStore();

    if (loadError) return <ErrorState message={loadError} />;
    if (!isLoaded) return <div className="flex items-center justify-center h-64"><div className="w-5 h-5 border-2 border-amber border-t-transparent rounded-full animate-spin" /></div>;
    if (runs.length === 0) return <FirstUseGuide />;

    return (
        <div className="space-y-10 animate-fade-up">
            {/* Hero */}
            <div className="hero-glow relative py-2">
                <div className="relative z-10">
                    <p className="section-label mb-2">Observatory</p>
                    <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">Dashboard</h1>
                    <p className="text-text-secondary mt-1 text-[13px]">Aggregated evaluation data</p>
                </div>
            </div>

            <ModelScoreChart runs={runs} />
            <RecentRuns runs={runs} />
            <EvaluationHistory runs={runs} />
            <SideBySideComparison runs={runs} />
            <AggregationTable runs={runs} />
        </div>
    );
}

/* ===================== MODEL SCORE CHART ===================== */
function ModelScoreChart({ runs }: { runs: EvaluationRun[] }) {
    const chartData = useMemo(() => {
        const map = new Map<string, { scores: number[]; best: number; count: number; name: string }>();
        runs.forEach((r) => {
            const e = map.get(r.subjectModelId) || { scores: [], best: 0, count: 0, name: r.subjectModelName };
            e.scores.push(r.averageScore); e.best = Math.max(e.best, r.bestScore); e.count++;
            map.set(r.subjectModelId, e);
        });
        return Array.from(map.entries())
            .map(([id, d]) => ({
                id, name: d.name.length > 16 ? d.name.slice(0, 14) + '\u2026' : d.name, fullName: d.name,
                avgScore: Math.round((d.scores.reduce((a, b) => a + b, 0) / d.scores.length) * 10) / 10,
                bestScore: d.best, runCount: d.count,
            }))
            .sort((a, b) => b.avgScore - a.avgScore).slice(0, 20);
    }, [runs]);

    return (
        <section className="space-y-3 animate-fade-up stagger-2">
            <h2 className="section-label">Model Performance</h2>
            <div className="card p-5">
                <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 24, left: 8 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                        <XAxis dataKey="name" tick={{ fill: '#858580', fontSize: 10, fontFamily: 'Instrument Sans' }} angle={-20} textAnchor="end" height={50} />
                        <YAxis domain={[0, 100]} tick={{ fill: '#858580', fontSize: 10, fontFamily: 'Victor Mono' }} />
                        <Tooltip
                            contentStyle={{
                                background: '#14161c',
                                border: '1px solid rgba(255,255,255,0.06)',
                                borderRadius: '6px',
                                fontSize: 12,
                                fontFamily: 'Instrument Sans',
                                color: '#e8e6e3',
                                boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                            }}
                            formatter={(_v, _n, props) => {
                                const p = props.payload as { fullName: string; avgScore: number; runCount: number; bestScore: number };
                                return [`${p.avgScore} avg \u00b7 ${p.runCount} runs \u00b7 best ${p.bestScore}`, p.fullName];
                            }}
                        />
                        <Bar dataKey="avgScore" radius={[3, 3, 0, 0]}>
                            {chartData.map((e, i) => <Cell key={i} fill={scoreBarColor(e.avgScore)} />)}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </section>
    );
}

/* ===================== RECENT RUNS ===================== */
function RecentRuns({ runs }: { runs: EvaluationRun[] }) {
    const navigate = useNavigate();
    return (
        <section className="space-y-3 animate-fade-up stagger-4">
            <h2 className="section-label">Recent Runs</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                {runs.slice(0, 5).map((r, i) => (
                    <button
                        key={r.id}
                        onClick={() => navigate(`/results/${r.id}`)}
                        className={`card p-3 text-left group transition-all duration-150 hover:border-amber/20 ${scoreGlow(r.averageScore)}`}
                        style={{ animationDelay: `${i * 30}ms` }}
                    >
                        <p className="text-[12px] font-medium text-text-primary truncate group-hover:text-amber transition-colors">{r.subjectModelName}</p>
                        <p className={`data-display text-lg mt-1 ${scoreTextColor(r.averageScore)}`}>{r.averageScore.toFixed(1)}</p>
                        {/* Gauge bar */}
                        <div className="h-1 bg-border/40 rounded-full overflow-hidden mt-2">
                            <div
                                className={`h-full rounded-full ${r.averageScore >= 80 ? 'bg-score-high' : r.averageScore >= 60 ? 'bg-score-mid' : 'bg-score-low'}`}
                                style={{ width: `${r.averageScore}%` }}
                            />
                        </div>
                        <div className="flex items-center justify-between mt-1.5 text-[9px] text-text-tertiary">
                            <span>{formatDistanceToNow(new Date(r.timestamp), { addSuffix: true })}</span>
                            <span>{r.taskCount}T · {r.judgeModels.length || r.judgeCount || 0}J</span>
                        </div>
                    </button>
                ))}
            </div>
        </section>
    );
}

/* ===================== EVALUATION HISTORY ===================== */
function EvaluationHistory({ runs }: { runs: EvaluationRun[] }) {
    const navigate = useNavigate();
    const [page, setPage] = useState(0);
    const totalPages = Math.ceil(runs.length / PAGE_SIZE);
    const pageRuns = runs.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

    return (
        <section className="space-y-3 animate-fade-up stagger-6">
            <h2 className="section-label">History</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {pageRuns.map((r) => (
                    <button
                        key={r.id} onClick={() => navigate(`/results/${r.id}`)}
                        className="card p-4 text-left group transition-all duration-150 hover:border-amber/20 accent-bar-ice"
                    >
                        <div className="flex items-center justify-between mb-1.5">
                            <p className="text-[13px] font-medium text-text-primary group-hover:text-amber transition-colors">{r.subjectModelName}</p>
                            <span className={`data-display text-[13px] ${scoreTextColor(r.averageScore)}`}>{r.averageScore.toFixed(1)}</span>
                        </div>
                        <div className="flex items-center gap-2 text-[11px] text-text-tertiary">
                            <span>{formatDistanceToNow(new Date(r.timestamp), { addSuffix: true })}</span>
                            <span>\u00b7</span>
                            <span>{r.taskCount} tasks</span>
                            <span>\u00b7</span>
                            <span>{r.judgeModels.length || r.judgeCount || 0} judges</span>
                        </div>
                    </button>
                ))}
            </div>
            {totalPages > 1 && (
                <div className="flex items-center justify-center gap-3">
                    <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0}
                        className="flex items-center gap-1 px-2.5 py-1 border border-border rounded text-[11px] text-text-secondary disabled:opacity-30 hover:border-amber/30 hover:text-amber transition-colors">
                        <ChevronLeft size={12} /> Prev
                    </button>
                    <span className="text-[11px] text-text-tertiary data-display">{page + 1} / {totalPages}</span>
                    <button onClick={() => setPage(Math.min(totalPages - 1, page + 1))} disabled={page === totalPages - 1}
                        className="flex items-center gap-1 px-2.5 py-1 border border-border rounded text-[11px] text-text-secondary disabled:opacity-30 hover:border-amber/30 hover:text-amber transition-colors">
                        Next <ChevronRight size={12} />
                    </button>
                </div>
            )}
        </section>
    );
}

/* ===================== SIDE-BY-SIDE COMPARISON ===================== */
function SideBySideComparison({ runs }: { runs: EvaluationRun[] }) {
    const [leftId, setLeftId] = useState<string>(runs[0]?.id || '');
    const [rightId, setRightId] = useState<string>(runs[1]?.id || '');
    const [show, setShow] = useState(false);
    const leftRun = runs.find((r) => r.id === leftId);
    const rightRun = runs.find((r) => r.id === rightId);
    if (runs.length < 2) return null;

    return (
        <section className="space-y-3 animate-fade-up stagger-8">
            <h2 className="section-label">Compare</h2>
            <div className="grid grid-cols-2 gap-2">
                {[{ label: 'Left', value: leftId, onChange: setLeftId }, { label: 'Right', value: rightId, onChange: setRightId }].map(({ label, value, onChange }) => (
                    <div key={label} className="space-y-1">
                        <label className="text-[9px] text-text-tertiary uppercase tracking-wider">{label}</label>
                        <select value={value} onChange={(e) => onChange(e.target.value)}
                            className="w-full bg-surface border border-border rounded px-3 py-2 text-[12px] text-text-primary focus:outline-none focus:border-amber/40 transition-colors">
                            {runs.map((r) => <option key={r.id} value={r.id}>{r.subjectModelName} \u2014 {format(new Date(r.timestamp), 'MMM d HH:mm')} ({r.averageScore.toFixed(1)})</option>)}
                        </select>
                    </div>
                ))}
            </div>
            <button onClick={() => setShow(!show)}
                className="px-3 py-1.5 bg-amber text-bg rounded text-[11px] font-display font-semibold hover:bg-amber-hover transition-all duration-200 hover:shadow-[0_0_16px_rgba(226,168,75,0.12)]">
                {show ? 'Hide' : 'Compare'}
            </button>
            {show && leftRun && rightRun && (
                <div className="space-y-3 animate-fade-in">
                    <div className="grid grid-cols-2 gap-2">
                        <CompSummary run={leftRun} />
                        <CompSummary run={rightRun} />
                    </div>
                    {getAllTaskIds(leftRun, rightRun).map((tid) => (
                        <CompRow key={tid} taskId={tid} left={leftRun.taskResults.find((t) => t.taskId === tid)} right={rightRun.taskResults.find((t) => t.taskId === tid)} />
                    ))}
                </div>
            )}
        </section>
    );
}

function CompSummary({ run }: { run: EvaluationRun }) {
    return (
        <div className={`card p-4 ${scoreGlow(run.averageScore)}`}>
            <p className="text-[12px] font-medium text-text-primary mb-2">{run.subjectModelName}</p>
            <div className="grid grid-cols-2 gap-2 text-center">
                <div>
                    <p className="text-[9px] text-text-tertiary uppercase tracking-wider">Avg</p>
                    <p className={`data-display text-lg ${scoreTextColor(run.averageScore)}`}>{run.averageScore.toFixed(1)}</p>
                </div>
                <div>
                    <p className="text-[9px] text-text-tertiary uppercase tracking-wider">Tasks</p>
                    <p className="data-display text-lg text-text-primary">{run.taskCount}</p>
                </div>
            </div>
        </div>
    );
}

function CompRow({ taskId, left, right }: { taskId: string; left?: EvaluationRun['taskResults'][0]; right?: EvaluationRun['taskResults'][0] }) {
    return (
        <div className="card overflow-hidden">
            <div className="px-4 py-2 border-b border-border"><span className="data-display text-[12px] text-text-secondary">{taskId}</span></div>
            <div className="grid grid-cols-2 divide-x divide-border">
                <CompSide task={left} />
                <CompSide task={right} />
            </div>
        </div>
    );
}

function CompSide({ task }: { task?: EvaluationRun['taskResults'][0] }) {
    if (!task) return <div className="p-3 text-center text-[10px] text-text-tertiary italic">Not evaluated</div>;
    return (
        <div className="p-3 space-y-1.5">
            <p className="text-[10px] text-text-tertiary line-clamp-2">{task.subjectResponse.slice(0, 120)}\u2026</p>
            {task.judgeEvaluations.map((je) => (
                <div key={je.judgeModelId} className="flex items-center justify-between text-[10px]">
                    <span className="text-text-tertiary truncate max-w-[100px]">{je.judgeModelName}</span>
                    <span className={`data-display ${scoreTextColor(je.totalScore.mean)}`}>{je.totalScore.mean}</span>
                </div>
            ))}
        </div>
    );
}

function getAllTaskIds(a: EvaluationRun, b: EvaluationRun): string[] {
    const ids = new Set<string>();
    a.taskResults.forEach((t) => ids.add(t.taskId));
    b.taskResults.forEach((t) => ids.add(t.taskId));
    return Array.from(ids).sort();
}

/* ===================== AGGREGATION TABLE ===================== */
function AggregationTable({ runs }: { runs: EvaluationRun[] }) {
    const data = useMemo(() => {
        const map = new Map<string, { name: string; scores: number[]; best: number; latest: string }>();
        runs.forEach((r) => {
            const e = map.get(r.subjectModelId) || { name: r.subjectModelName, scores: [], best: 0, latest: '' };
            e.scores.push(r.averageScore); e.best = Math.max(e.best, r.bestScore);
            if (!e.latest || r.timestamp > e.latest) e.latest = r.timestamp;
            map.set(r.subjectModelId, e);
        });
        return Array.from(map.entries())
            .map(([, d]) => ({ name: d.name, runs: d.scores.length, avg: Math.round((d.scores.reduce((a, b) => a + b, 0) / d.scores.length) * 10) / 10, best: d.best, latest: d.latest }))
            .sort((a, b) => b.avg - a.avg);
    }, [runs]);

    return (
        <section className="space-y-3 animate-fade-up stagger-10">
            <h2 className="section-label">Summary</h2>
            <div className="card overflow-hidden">
                <table className="w-full text-[12px]">
                    <thead>
                        <tr className="border-b border-border">
                            {['Model', 'Runs', 'Avg', 'Best', 'Latest'].map((h) => (
                                <th key={h} className={`px-4 py-2.5 text-[9px] font-display font-bold text-text-tertiary uppercase tracking-wider ${h === 'Model' || h === 'Latest' ? 'text-left' : 'text-center'} ${h === 'Latest' ? 'text-right' : ''}`}>{h}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {data.map((row) => (
                            <tr key={row.name} className="border-b border-border/30 hover:bg-surface-hover transition-colors group">
                                <td className="px-4 py-2.5 font-medium text-text-primary group-hover:text-amber transition-colors">{row.name}</td>
                                <td className="px-4 py-2.5 text-center text-text-secondary">{row.runs}</td>
                                <td className="px-4 py-2.5 text-center"><span className={`data-display ${scoreTextColor(row.avg)}`}>{row.avg}</span></td>
                                <td className="px-4 py-2.5 text-center"><span className={`data-display ${scoreTextColor(row.best)}`}>{row.best.toFixed(1)}</span></td>
                                <td className="px-4 py-2.5 text-right text-text-secondary">{format(new Date(row.latest), 'MMM d, yyyy')}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
    );
}

/* ===================== EMPTY & ERROR STATES ===================== */
function FirstUseGuide() {
    const navigate = useNavigate();
    return (
        <div className="space-y-8 animate-fade-up">
            <div className="hero-glow relative py-2">
                <div className="relative z-10">
                    <p className="section-label mb-2">Observatory</p>
                    <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">Dashboard</h1>
                    <p className="text-text-secondary mt-1 text-[13px]">Aggregated evaluation data</p>
                </div>
            </div>
            <div className="card p-10 text-center space-y-5">
                <h2 className="text-[15px] font-display font-bold text-text-primary">No evaluations yet</h2>
                <p className="text-[12px] text-text-tertiary max-w-md mx-auto">
                    Configure your API keys and models in Settings, then run your first evaluation.
                </p>
                <div className="flex items-center justify-center gap-3">
                    <button onClick={() => navigate('/settings')} className="px-4 py-2 bg-amber text-bg rounded text-[12px] font-display font-semibold hover:bg-amber-hover transition-all duration-200 hover:shadow-[0_0_16px_rgba(226,168,75,0.12)] flex items-center gap-1.5">
                        Get Started <ArrowRight size={13} />
                    </button>
                </div>
            </div>
        </div>
    );
}

function ErrorState({ message }: { message: string }) {
    return (
        <div className="space-y-6 animate-fade-up">
            <div className="hero-glow relative py-2">
                <div className="relative z-10">
                    <p className="section-label mb-2">Observatory</p>
                    <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">Dashboard</h1>
                    <p className="text-text-secondary mt-1 text-[13px]">Aggregated evaluation data</p>
                </div>
            </div>
            <div className="card p-8 text-center space-y-3 accent-bar-low">
                <AlertCircle size={28} className="text-score-low mx-auto" />
                <h2 className="text-[14px] font-display font-semibold text-text-secondary">Failed to load data</h2>
                <p className="text-[12px] text-text-tertiary">{message}</p>
            </div>
        </div>
    );
}
