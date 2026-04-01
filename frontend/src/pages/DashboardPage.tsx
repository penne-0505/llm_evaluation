import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useHistoryStore } from '../store/historyStore';
import type { EvaluationRun } from '../types';
import { formatDistanceToNow, format } from 'date-fns';
import { ja } from 'date-fns/locale';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
    ScatterChart, Scatter, ZAxis,
} from 'recharts';
import {
    ChevronLeft, ChevronRight, AlertCircle, ArrowRight,
} from 'lucide-react';
import { buildResultDetailPath } from '../lib/resultRoutes';
import { mean, stddev } from '../lib/stats';

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

function formatUsd(value: number | undefined): string {
    if (value === undefined || value === null || Number.isNaN(value)) {
        return 'N/A';
    }
    if (value === 0) {
        return '$0.00';
    }
    if (value < 0.01) {
        return `$${value.toFixed(4)}`;
    }
    return `$${value.toFixed(2)}`;
}

function formatRelativeTime(value: string): string {
    return formatDistanceToNow(new Date(value), { addSuffix: true, locale: ja });
}

function formatDateTime(value: string): string {
    return format(new Date(value), 'yyyy/MM/dd HH:mm');
}

function formatDateOnly(value: string): string {
    return format(new Date(value), 'yyyy/MM/dd');
}

type ModelAggregate = {
    id: string;
    name: string;
    shortName: string;
    avgScore: number;
    bestScore: number;
    variability: number;
    runCount: number;
    latest: string;
    avgCostPer1m?: number;
};

type StrictModeProfile = {
    profileId: string;
    profileLabel: string;
    leaderboard: ModelAggregate[];
    runCount: number;
    modelCount: number;
    latest: string;
};

function buildModelAggregates(runs: EvaluationRun[]): ModelAggregate[] {
    const map = new Map<string, {
        name: string;
        scores: number[];
        best: number;
        latest: string;
        costPer1m: number[];
    }>();

    runs.forEach((run) => {
        const entry = map.get(run.subjectModelId) || {
            name: run.subjectModelName,
            scores: [],
            best: 0,
            latest: '',
            costPer1m: [],
        };
        entry.scores.push(run.averageScore);
        entry.best = Math.max(entry.best, run.bestScore);
        if (!entry.latest || run.timestamp > entry.latest) {
            entry.latest = run.timestamp;
        }
        if (typeof run.subjectCostPer1mTokensUsd === 'number') {
            entry.costPer1m.push(run.subjectCostPer1mTokensUsd);
        }
        map.set(run.subjectModelId, entry);
    });

    return Array.from(map.entries())
        .map(([id, entry]) => ({
            id,
            name: entry.name,
            shortName: entry.name.length > 16 ? `${entry.name.slice(0, 14)}…` : entry.name,
            avgScore: Math.round(mean(entry.scores) * 10) / 10,
            bestScore: entry.best,
            variability: Math.round(stddev(entry.scores) * 10) / 10,
            runCount: entry.scores.length,
            latest: entry.latest,
            avgCostPer1m: entry.costPer1m.length > 0 ? Number(mean(entry.costPer1m).toFixed(6)) : undefined,
        }))
        .sort((a, b) => b.avgScore - a.avgScore);
}

function buildStrictModeProfiles(runs: EvaluationRun[]): StrictModeProfile[] {
    const grouped = new Map<string, { label: string; runs: EvaluationRun[] }>();

    runs.forEach((run) => {
        const strictMode = run.strictMode;
        if (!strictMode?.enforced || !strictMode.profileId) {
            return;
        }
        const entry = grouped.get(strictMode.profileId) || {
            label: strictMode.profileLabel || strictMode.presetLabel || strictMode.profileId,
            runs: [],
        };
        entry.runs.push(run);
        grouped.set(strictMode.profileId, entry);
    });

    return Array.from(grouped.entries())
        .map(([profileId, entry]) => ({
            profileId,
            profileLabel: entry.label,
            leaderboard: buildModelAggregates(entry.runs),
            runCount: entry.runs.length,
            modelCount: new Set(entry.runs.map((run) => run.subjectModelId)).size,
            latest: entry.runs.reduce(
                (latest, run) => (latest && latest > run.timestamp ? latest : run.timestamp),
                '',
            ),
        }))
        .sort((a, b) => {
            if (b.runCount !== a.runCount) return b.runCount - a.runCount;
            return b.latest.localeCompare(a.latest);
        });
}

export default function DashboardPage() {
    const { runs, isLoaded, loadError, initialize } = useHistoryStore();

    useEffect(() => {
        void initialize();
    }, [initialize]);

    if (loadError) return <ErrorState message={loadError} />;
    if (!isLoaded) return <div className="flex items-center justify-center h-64"><div className="w-5 h-5 border-2 border-amber border-t-transparent rounded-full animate-spin" /></div>;
    if (runs.length === 0) return <FirstUseGuide />;

    const aggregates = buildModelAggregates(runs);
    const strictProfiles = buildStrictModeProfiles(runs);

    return (
        <div className="space-y-10 animate-fade-up">
            <div className="hero-glow relative py-2">
                <div className="relative z-10">
                    <p className="section-label mb-2">観測所</p>
                    <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">ダッシュボード</h1>
                    <p className="text-text-secondary mt-1 text-[13px]">集計済みの評価データを表示します</p>
                </div>
            </div>

            <ModelScoreChart data={aggregates} />
            <CostEfficiencyChart data={aggregates} />
            <StrictModeLeaderboard profiles={strictProfiles} />
            <RecentRuns runs={runs} />
            <EvaluationHistory runs={runs} />
            <SideBySideComparison runs={runs} />
            <AggregationTable data={aggregates} />
        </div>
    );
}

function ModelScoreChart({ data }: { data: ModelAggregate[] }) {
    const chartData = data.slice(0, 20);

    return (
        <section className="space-y-3 animate-fade-up stagger-2">
            <h2 className="section-label">モデル性能</h2>
            <div className="card p-5">
                <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 24, left: 8 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                        <XAxis dataKey="shortName" tick={{ fill: '#858580', fontSize: 10, fontFamily: 'UDEV Gothic 35NFLG, Arial, sans-serif' }} angle={-20} textAnchor="end" height={50} />
                        <YAxis domain={[0, 100]} tick={{ fill: '#858580', fontSize: 10, fontFamily: 'UDEV Gothic 35NFLG, Arial, sans-serif' }} />
                        <Tooltip
                            contentStyle={{
                                background: '#14161c',
                                border: '1px solid rgba(255,255,255,0.06)',
                                borderRadius: '6px',
                                fontSize: 12,
                                fontFamily: 'UDEV Gothic 35NFLG, Arial, sans-serif',
                                color: '#e8e6e3',
                                boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                            }}
                            formatter={(_v, _n, props) => {
                                const payload = props.payload as ModelAggregate;
                                return [`平均 ${payload.avgScore} ±${payload.variability} ・ ${payload.runCount}回 ・ 最高 ${payload.bestScore}`, payload.name];
                            }}
                        />
                        <Bar dataKey="avgScore" radius={[3, 3, 0, 0]}>
                            {chartData.map((entry, index) => <Cell key={index} fill={scoreBarColor(entry.avgScore)} />)}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </section>
    );
}

function CostEfficiencyChart({ data }: { data: ModelAggregate[] }) {
    const roiData = data
        .filter((entry) => typeof entry.avgCostPer1m === 'number')
        .map((entry) => ({
            ...entry,
            y: entry.avgCostPer1m as number,
            z: Math.max(entry.runCount, 1),
        }))
        .sort((a, b) => (a.y - b.y));

    return (
        <section className="space-y-3 animate-fade-up stagger-3">
            <h2 className="section-label">コスト効率</h2>
            <div className="card p-5">
                {roiData.length > 0 ? (
                    <ResponsiveContainer width="100%" height={280}>
                        <ScatterChart margin={{ top: 12, right: 12, bottom: 12, left: 12 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                            <XAxis
                                type="number"
                                dataKey="avgScore"
                                domain={[0, 100]}
                                name="平均点"
                                tick={{ fill: '#858580', fontSize: 10, fontFamily: 'UDEV Gothic 35NFLG, Arial, sans-serif' }}
                            />
                            <YAxis
                                type="number"
                                dataKey="y"
                                name="100万tokenあたりUSD"
                                tick={{ fill: '#858580', fontSize: 10, fontFamily: 'UDEV Gothic 35NFLG, Arial, sans-serif' }}
                                width={72}
                            />
                            <ZAxis type="number" dataKey="z" range={[80, 220]} />
                            <Tooltip
                                cursor={{ strokeDasharray: '4 4', stroke: 'rgba(226,168,75,0.25)' }}
                                contentStyle={{
                                    background: '#14161c',
                                    border: '1px solid rgba(255,255,255,0.06)',
                                    borderRadius: '6px',
                                    fontSize: 12,
                                    fontFamily: 'UDEV Gothic 35NFLG, Arial, sans-serif',
                                    color: '#e8e6e3',
                                    boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                                }}
                                formatter={(_v, _n, props) => {
                                    const payload = props.payload as ModelAggregate & { y: number };
                                    return [`平均 ${payload.avgScore} ±${payload.variability} ・ ${formatUsd(payload.y)}/1M`, payload.name];
                                }}
                            />
                            <Scatter data={roiData} fill="#e2a84b" />
                        </ScatterChart>
                    </ResponsiveContainer>
                ) : (
                    <div className="rounded-md border border-dashed border-border px-4 py-8 text-[12px] text-text-tertiary">
                        ROI 散布図を表示するには、被験モデル側の token 使用量と価格情報を持つ run が必要です。
                    </div>
                )}
            </div>
        </section>
    );
}

function StrictModeLeaderboard({ profiles }: { profiles: StrictModeProfile[] }) {
    return (
        <section className="space-y-3 animate-fade-up stagger-4">
            <div className="flex items-end justify-between gap-3">
                <div>
                    <h2 className="section-label">Strict Mode ランキング</h2>
                    <p className="mt-1 text-[12px] text-text-tertiary">
                        同一タスク、同一評価モデル、同一評価回数、bundled resource 条件を満たす run だけを集計しています。
                    </p>
                </div>
                <span className="text-[10px] uppercase tracking-[0.22em] text-text-tertiary">
                    {profiles.length} プロファイル
                </span>
            </div>

            {profiles.length === 0 ? (
                <div className="card border-dashed border-border/80 px-4 py-8 text-[12px] text-text-tertiary">
                    Strict Mode 対象の実行が 1 件以上記録されると、ここにランキングが表示されます。
                </div>
            ) : (
                <div className="space-y-3">
                    {profiles.map((profile) => (
                        <div key={profile.profileId} className="card overflow-hidden">
                            <div className="border-b border-border px-4 py-3">
                                <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <h3 className="text-[14px] font-display font-semibold text-text-primary">
                                                {profile.profileLabel}
                                            </h3>
                                            <span className="rounded-full border border-score-high/30 bg-score-high/10 px-2 py-0.5 text-[9px] uppercase tracking-[0.2em] text-score-high">
                                                strict
                                            </span>
                                        </div>
                                        <p className="mt-1 text-[11px] text-text-tertiary">
                                            {profile.runCount}回 ・ {profile.modelCount}モデル
                                        </p>
                                    </div>
                                    <div className="text-right text-[10px] text-text-tertiary">
                                        <div>{profile.profileId}</div>
                                        <div>{formatDateTime(profile.latest)}</div>
                                    </div>
                                </div>
                            </div>

                            <div className="overflow-x-auto">
                                <table className="w-full min-w-[680px] text-[12px]">
                                    <thead>
                                        <tr className="border-b border-border/70">
                                            {['順位', 'モデル', '実行数', '平均', '最高', '単価/1M'].map((heading) => (
                                                <th
                                                    key={heading}
                                                    className={`px-4 py-2.5 text-[9px] font-display font-bold uppercase tracking-wider text-text-tertiary ${
                                                        heading === 'モデル' ? 'text-left' : 'text-center'
                                                    }`}
                                                >
                                                    {heading}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {profile.leaderboard.map((row, index) => (
                                            <tr key={`${profile.profileId}-${row.id}`} className="border-b border-border/30 last:border-b-0">
                                                <td className="px-4 py-3 text-center data-display text-text-secondary">
                                                    {index + 1}
                                                </td>
                                                <td className="px-4 py-3">
                                                    <div className="font-medium text-text-primary">{row.name}</div>
                                                    <div className="mt-0.5 text-[10px] text-text-tertiary">
                                                        最新: {formatRelativeTime(row.latest)}
                                                    </div>
                                                </td>
                                                <td className="px-4 py-3 text-center text-text-secondary">
                                                    {row.runCount}
                                                </td>
                                                <td className="px-4 py-3 text-center">
                                                    <div className="flex flex-col items-center leading-tight">
                                                        <span className={`data-display ${scoreTextColor(row.avgScore)}`}>
                                                            {row.avgScore.toFixed(1)}
                                                        </span>
                                                        <span className="text-[10px] text-text-tertiary">
                                                            ±{row.variability.toFixed(1)}
                                                        </span>
                                                    </div>
                                                </td>
                                                <td className="px-4 py-3 text-center">
                                                    <span className={`data-display ${scoreTextColor(row.bestScore)}`}>
                                                        {row.bestScore.toFixed(1)}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-3 text-center text-text-secondary">
                                                    {formatUsd(row.avgCostPer1m)}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </section>
    );
}

function RecentRuns({ runs }: { runs: EvaluationRun[] }) {
    const navigate = useNavigate();

    return (
        <section className="space-y-3 animate-fade-up stagger-4">
            <h2 className="section-label">最近の実行</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                {runs.slice(0, 5).map((run, index) => (
                    <button
                        key={run.id}
                        onClick={() => navigate(buildResultDetailPath(run.id))}
                        className={`card p-3 text-left group transition-all duration-150 hover:border-amber/20 ${scoreGlow(run.averageScore)}`}
                        style={{ animationDelay: `${index * 30}ms` }}
                    >
                        <p className="text-[12px] font-medium text-text-primary truncate group-hover:text-amber transition-colors">{run.subjectModelName}</p>
                        <div className="mt-1 flex items-end justify-between gap-3">
                            <p className={`data-display text-lg ${scoreTextColor(run.averageScore)}`}>{run.averageScore.toFixed(1)}</p>
                            {typeof run.subjectCostPer1mTokensUsd === 'number' && (
                                <span className="text-[10px] text-text-tertiary">{formatUsd(run.subjectCostPer1mTokensUsd)}/1M</span>
                            )}
                        </div>
                        <div className="h-1 bg-border/40 rounded-full overflow-hidden mt-2">
                            <div
                                className={`h-full rounded-full ${run.averageScore >= 80 ? 'bg-score-high' : run.averageScore >= 60 ? 'bg-score-mid' : 'bg-score-low'}`}
                                style={{ width: `${run.averageScore}%` }}
                            />
                        </div>
                        <div className="flex items-center justify-between mt-1.5 text-[9px] text-text-tertiary">
                            <span>{formatRelativeTime(run.timestamp)}</span>
                            <span>{run.taskCount}タスク · {run.judgeModels.length || run.judgeCount || 0}評価</span>
                        </div>
                    </button>
                ))}
            </div>
        </section>
    );
}

function EvaluationHistory({ runs }: { runs: EvaluationRun[] }) {
    const navigate = useNavigate();
    const [page, setPage] = useState(0);
    const totalPages = Math.ceil(runs.length / PAGE_SIZE);
    const pageRuns = runs.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

    return (
        <section className="space-y-3 animate-fade-up stagger-6">
            <h2 className="section-label">履歴</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {pageRuns.map((run) => (
                    <button
                        key={run.id}
                        onClick={() => navigate(buildResultDetailPath(run.id))}
                        className="card p-4 text-left group transition-all duration-150 hover:border-amber/20 accent-bar-ice"
                    >
                        <div className="flex items-center justify-between gap-3 mb-1.5">
                            <p className="text-[13px] font-medium text-text-primary group-hover:text-amber transition-colors">{run.subjectModelName}</p>
                            <div className="text-right">
                                <span className={`data-display text-[13px] ${scoreTextColor(run.averageScore)}`}>{run.averageScore.toFixed(1)}</span>
                                {typeof run.subjectCostPer1mTokensUsd === 'number' && (
                                    <p className="text-[10px] text-text-tertiary">{formatUsd(run.subjectCostPer1mTokensUsd)}/1M</p>
                                )}
                            </div>
                        </div>
                        <div className="flex items-center gap-2 text-[11px] text-text-tertiary">
                            <span>{formatRelativeTime(run.timestamp)}</span>
                            <span>·</span>
                            <span>{run.taskCount} タスク</span>
                            <span>·</span>
                            <span>{run.judgeModels.length || run.judgeCount || 0} 評価モデル</span>
                        </div>
                    </button>
                ))}
            </div>
            {totalPages > 1 && (
                <div className="flex items-center justify-center gap-3">
                    <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0}
                        className="flex items-center gap-1 px-2.5 py-1 border border-border rounded text-[11px] text-text-secondary disabled:opacity-30 hover:border-amber/30 hover:text-amber transition-colors">
                        <ChevronLeft size={12} /> 前へ
                    </button>
                    <span className="text-[11px] text-text-tertiary data-display">{page + 1} / {totalPages}</span>
                    <button onClick={() => setPage(Math.min(totalPages - 1, page + 1))} disabled={page === totalPages - 1}
                        className="flex items-center gap-1 px-2.5 py-1 border border-border rounded text-[11px] text-text-secondary disabled:opacity-30 hover:border-amber/30 hover:text-amber transition-colors">
                        次へ <ChevronRight size={12} />
                    </button>
                </div>
            )}
        </section>
    );
}

function SideBySideComparison({ runs }: { runs: EvaluationRun[] }) {
    const [leftId, setLeftId] = useState<string>(runs[0]?.id || '');
    const [rightId, setRightId] = useState<string>(runs[1]?.id || '');
    const [show, setShow] = useState(false);
    const leftRun = runs.find((run) => run.id === leftId);
    const rightRun = runs.find((run) => run.id === rightId);
    if (runs.length < 2) return null;

    return (
        <section className="space-y-3 animate-fade-up stagger-8">
            <h2 className="section-label">比較</h2>
            <div className="grid grid-cols-2 gap-2">
                {[{ label: '左', value: leftId, onChange: setLeftId }, { label: '右', value: rightId, onChange: setRightId }].map(({ label, value, onChange }) => (
                    <div key={label} className="space-y-1">
                        <label className="text-[9px] text-text-tertiary uppercase tracking-wider">{label}</label>
                        <select value={value} onChange={(event) => onChange(event.target.value)}
                            className="w-full bg-surface border border-border rounded px-3 py-2 text-[12px] text-text-primary focus:outline-none focus:border-amber/40 transition-colors">
                            {runs.map((run) => <option key={run.id} value={run.id}>{run.subjectModelName} — {formatDateTime(run.timestamp)} ({run.averageScore.toFixed(1)})</option>)}
                        </select>
                    </div>
                ))}
            </div>
            <button onClick={() => setShow(!show)}
                className="px-3 py-1.5 bg-amber text-bg rounded text-[11px] font-display font-semibold hover:bg-amber-hover transition-all duration-200 hover:shadow-[0_0_16px_rgba(226,168,75,0.12)]">
                {show ? '非表示' : '比較する'}
            </button>
            {show && leftRun && rightRun && (
                <div className="space-y-3 animate-fade-in">
                    <div className="grid grid-cols-2 gap-2">
                        <CompSummary run={leftRun} />
                        <CompSummary run={rightRun} />
                    </div>
                    {getAllTaskIds(leftRun, rightRun).map((taskId) => (
                        <CompRow key={taskId} taskId={taskId} left={leftRun.taskResults.find((task) => task.taskId === taskId)} right={rightRun.taskResults.find((task) => task.taskId === taskId)} />
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
                    <p className="text-[9px] text-text-tertiary uppercase tracking-wider">平均</p>
                    <p className={`data-display text-lg ${scoreTextColor(run.averageScore)}`}>{run.averageScore.toFixed(1)}</p>
                </div>
                <div>
                    <p className="text-[9px] text-text-tertiary uppercase tracking-wider">タスク</p>
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
    if (!task) return <div className="p-3 text-center text-[10px] text-text-tertiary italic">未評価</div>;
    return (
        <div className="p-3 space-y-1.5">
            <p className="text-[10px] text-text-tertiary line-clamp-2">{task.subjectResponse.slice(0, 120)}…</p>
            {task.judgeEvaluations.map((judgeEvaluation) => (
                <div key={judgeEvaluation.judgeModelId} className="flex items-center justify-between text-[10px]">
                    <span className="text-text-tertiary truncate max-w-[100px]">{judgeEvaluation.judgeModelName}</span>
                    <span className={`data-display ${scoreTextColor(judgeEvaluation.totalScore.mean)}`}>{judgeEvaluation.totalScore.mean}</span>
                </div>
            ))}
        </div>
    );
}

function getAllTaskIds(left: EvaluationRun, right: EvaluationRun): string[] {
    const ids = new Set<string>();
    left.taskResults.forEach((task) => ids.add(task.taskId));
    right.taskResults.forEach((task) => ids.add(task.taskId));
    return Array.from(ids).sort();
}

function AggregationTable({ data }: { data: ModelAggregate[] }) {
    return (
        <section className="space-y-3 animate-fade-up stagger-10">
            <h2 className="section-label">集計表</h2>
            <div className="card overflow-hidden">
                <table className="w-full text-[12px]">
                    <thead>
                        <tr className="border-b border-border">
                            {['モデル', '実行数', '平均', '最高', '単価/1M', '最新'].map((heading) => (
                                <th key={heading} className={`px-4 py-2.5 text-[9px] font-display font-bold text-text-tertiary uppercase tracking-wider ${heading === 'モデル' || heading === '最新' ? 'text-left' : 'text-center'} ${heading === '最新' ? 'text-right' : ''}`}>{heading}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {data.map((row) => (
                            <tr key={row.name} className="border-b border-border/30 hover:bg-surface-hover transition-colors group">
                                <td className="px-4 py-2.5 font-medium text-text-primary group-hover:text-amber transition-colors">{row.name}</td>
                                <td className="px-4 py-2.5 text-center text-text-secondary">{row.runCount}</td>
                                <td className="px-4 py-2.5 text-center">
                                    <div className="flex flex-col items-center leading-tight">
                                        <span className={`data-display ${scoreTextColor(row.avgScore)}`}>{row.avgScore.toFixed(1)}</span>
                                        <span className="text-[10px] text-text-tertiary">±{row.variability.toFixed(1)}</span>
                                    </div>
                                </td>
                                <td className="px-4 py-2.5 text-center"><span className={`data-display ${scoreTextColor(row.bestScore)}`}>{row.bestScore.toFixed(1)}</span></td>
                                <td className="px-4 py-2.5 text-center text-text-secondary">{formatUsd(row.avgCostPer1m)}</td>
                                <td className="px-4 py-2.5 text-right text-text-secondary">{formatDateOnly(row.latest)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
    );
}

function FirstUseGuide() {
    const navigate = useNavigate();
    return (
        <div className="space-y-8 animate-fade-up">
            <div className="hero-glow relative py-2">
                <div className="relative z-10">
                    <p className="section-label mb-2">観測所</p>
                    <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">ダッシュボード</h1>
                    <p className="text-text-secondary mt-1 text-[13px]">集計済みの評価データを表示します</p>
                </div>
            </div>
            <div className="card p-10 text-center space-y-5">
                <h2 className="text-[15px] font-display font-bold text-text-primary">まだ評価結果がありません</h2>
                <p className="text-[12px] text-text-tertiary max-w-md mx-auto">
                    まず設定画面で API キーとモデルを設定し、最初の評価を実行してください。
                </p>
                <div className="flex items-center justify-center gap-3">
                    <button onClick={() => navigate('/settings')} className="px-4 py-2 bg-amber text-bg rounded text-[12px] font-display font-semibold hover:bg-amber-hover transition-all duration-200 hover:shadow-[0_0_16px_rgba(226,168,75,0.12)] flex items-center gap-1.5">
                        設定を始める <ArrowRight size={13} />
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
                    <p className="section-label mb-2">観測所</p>
                    <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">ダッシュボード</h1>
                    <p className="text-text-secondary mt-1 text-[13px]">集計済みの評価データを表示します</p>
                </div>
            </div>
            <div className="card p-8 text-center space-y-3 accent-bar-low">
                <AlertCircle size={28} className="text-score-low mx-auto" />
                <h2 className="text-[14px] font-display font-semibold text-text-secondary">データの読み込みに失敗しました</h2>
                <p className="text-[12px] text-text-tertiary">{message}</p>
            </div>
        </div>
    );
}
