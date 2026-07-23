import { useEffect, useMemo, useState } from 'react';
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
import { formatTimeRoi, runProcessingDurationMs } from '../lib/timeRoi';
import { formatHeroScore, isHeroScoreAvailable } from '../lib/judgeReliability';
import Button from '../components/Button';

const PAGE_SIZE = 4;

/** Runs without strictMode.presetId land here so old history is never dropped from filters. */
const UNCLASSIFIED_PRESET_ID = '__unclassified__';
const UNCLASSIFIED_PRESET_LABEL = '未分類';

/**
 * Preset filter source (UI-Enhance-47): use recorded strictMode.presetId / presetLabel.
 * settingsStore.executionPresets are pre-run config only and are NOT persisted on EvaluationRun;
 * scoping to strict-preset metadata avoids a backend schema change while satisfying AC.
 */
type StrictScope = 'non-strict' | 'strict';

type PresetOption = {
    id: string;
    label: string;
    count: number;
};

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
    avgExecutionTimeMs?: number;
    /** Dominant preset among this model's runs (for color when filter is OFF). */
    dominantPresetId: string;
};

type StrictModeProfile = {
    profileId: string;
    profileLabel: string;
    presetId: string;
    leaderboard: ModelAggregate[];
    runCount: number;
    modelCount: number;
    latest: string;
};

const PRESET_PALETTE = [
    '#6b8cae',
    '#9b7bb8',
    '#5a9e8f',
    '#c4785a',
    '#7a8f9e',
    '#b89a6b',
    '#8a6b9e',
    '#6b9e7a',
];

function scoreBarColor(score: number): string {
    if (score >= 80) return '#7cc474';
    if (score >= 60) return '#d4a84b';
    return '#c45c5c';
}

function scoreTextColor(score: number | null | undefined): string {
    if (!isHeroScoreAvailable(score)) return 'text-text-tertiary';
    if (score >= 80) return 'text-score-high';
    if (score >= 60) return 'text-score-mid';
    return 'text-score-low';
}

function scoreBarClass(score: number | null | undefined): string {
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

function getRunPresetId(run: EvaluationRun): string {
    return run.strictMode?.presetId || UNCLASSIFIED_PRESET_ID;
}

function getRunPresetLabel(run: EvaluationRun): string {
    if (!run.strictMode?.presetId) {
        return UNCLASSIFIED_PRESET_LABEL;
    }
    return run.strictMode.presetLabel || run.strictMode.presetId;
}

function isStrictRun(run: EvaluationRun): boolean {
    return Boolean(run.strictMode?.enforced);
}

function presetColor(presetId: string, colorById: Map<string, string>): string {
    return colorById.get(presetId) || PRESET_PALETTE[0];
}

function buildPresetColorMap(presetIds: string[]): Map<string, string> {
    const map = new Map<string, string>();
    const ordered = [...presetIds].sort((a, b) => {
        if (a === UNCLASSIFIED_PRESET_ID) return 1;
        if (b === UNCLASSIFIED_PRESET_ID) return -1;
        return a.localeCompare(b);
    });
    ordered.forEach((id, index) => {
        map.set(id, PRESET_PALETTE[index % PRESET_PALETTE.length]);
    });
    return map;
}

function buildPresetOptions(runs: EvaluationRun[]): PresetOption[] {
    const grouped = new Map<string, { label: string; count: number }>();
    runs.forEach((run) => {
        const id = getRunPresetId(run);
        const entry = grouped.get(id) || { label: getRunPresetLabel(run), count: 0 };
        entry.count += 1;
        if (id !== UNCLASSIFIED_PRESET_ID && run.strictMode?.presetLabel) {
            entry.label = run.strictMode.presetLabel;
        }
        grouped.set(id, entry);
    });
    return Array.from(grouped.entries())
        .map(([id, entry]) => ({ id, label: entry.label, count: entry.count }))
        .sort((a, b) => {
            if (a.id === UNCLASSIFIED_PRESET_ID) return 1;
            if (b.id === UNCLASSIFIED_PRESET_ID) return -1;
            return b.count - a.count;
        });
}

function filterByStrictScope(runs: EvaluationRun[], scope: StrictScope): EvaluationRun[] {
    return runs.filter((run) => (scope === 'strict' ? isStrictRun(run) : !isStrictRun(run)));
}

function filterByPreset(runs: EvaluationRun[], presetFilter: string): EvaluationRun[] {
    if (presetFilter === 'all') {
        return runs;
    }
    return runs.filter((run) => getRunPresetId(run) === presetFilter);
}

function dominantPresetId(runs: EvaluationRun[]): string {
    const counts = new Map<string, number>();
    runs.forEach((run) => {
        const id = getRunPresetId(run);
        counts.set(id, (counts.get(id) || 0) + 1);
    });
    let best = UNCLASSIFIED_PRESET_ID;
    let bestCount = -1;
    counts.forEach((count, id) => {
        if (count > bestCount) {
            best = id;
            bestCount = count;
        }
    });
    return best;
}

function buildModelAggregates(runs: EvaluationRun[]): ModelAggregate[] {
    const map = new Map<string, {
        name: string;
        scores: number[];
        best: number;
        latest: string;
        costPer1m: number[];
        executionTimes: number[];
        runs: EvaluationRun[];
    }>();

    runs.forEach((run) => {
        const entry = map.get(run.subjectModelId) || {
            name: run.subjectModelName,
            scores: [],
            best: 0,
            latest: '',
            costPer1m: [],
            executionTimes: [],
            runs: [],
        };
        if (isHeroScoreAvailable(run.averageScore)) {
            entry.scores.push(run.averageScore);
        }
        if (isHeroScoreAvailable(run.bestScore)) {
            entry.best = Math.max(entry.best, run.bestScore);
        }
        if (!entry.latest || run.timestamp > entry.latest) {
            entry.latest = run.timestamp;
        }
        if (typeof run.subjectCostPer1mTokensUsd === 'number') {
            entry.costPer1m.push(run.subjectCostPer1mTokensUsd);
        }
        // intent: DEC-004 (Core/time-roi-task-timing) — wall-clock ではなく処理時間合算
        const processingMs = runProcessingDurationMs(run);
        if (typeof processingMs === 'number' && processingMs > 0) {
            entry.executionTimes.push(processingMs);
        }
        entry.runs.push(run);
        map.set(run.subjectModelId, entry);
    });

    return Array.from(map.entries())
        .map(([id, entry]) => ({
            id,
            name: entry.name,
            shortName: entry.name.length > 16 ? `${entry.name.slice(0, 14)}…` : entry.name,
            avgScore: entry.scores.length > 0 ? Math.round(mean(entry.scores) * 10) / 10 : 0,
            bestScore: entry.best,
            variability: entry.scores.length > 1 ? Math.round(stddev(entry.scores) * 10) / 10 : 0,
            runCount: entry.runs.length,
            latest: entry.latest,
            avgCostPer1m: entry.costPer1m.length > 0 ? Number(mean(entry.costPer1m).toFixed(6)) : undefined,
            avgExecutionTimeMs: entry.executionTimes.length > 0 ? Number(mean(entry.executionTimes).toFixed(0)) : undefined,
            dominantPresetId: dominantPresetId(entry.runs),
        }))
        .sort((a, b) => b.avgScore - a.avgScore);
}

function buildStrictModeProfiles(runs: EvaluationRun[]): StrictModeProfile[] {
    const grouped = new Map<string, { label: string; presetId: string; runs: EvaluationRun[] }>();

    runs.forEach((run) => {
        const strictMode = run.strictMode;
        if (!strictMode?.enforced || !strictMode.profileId) {
            return;
        }
        const entry = grouped.get(strictMode.profileId) || {
            label: strictMode.profileLabel || strictMode.presetLabel || strictMode.profileId,
            presetId: getRunPresetId(run),
            runs: [],
        };
        entry.runs.push(run);
        grouped.set(strictMode.profileId, entry);
    });

    return Array.from(grouped.entries())
        .map(([profileId, entry]) => ({
            profileId,
            profileLabel: entry.label,
            presetId: entry.presetId,
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
    const [strictScope, setStrictScope] = useState<StrictScope>('non-strict');
    // 'all' = filter OFF (overall view). Otherwise strictMode.presetId or UNCLASSIFIED_PRESET_ID.
    const [presetFilter, setPresetFilter] = useState<string>('all');

    useEffect(() => {
        void initialize();
    }, [initialize]);

    const scopedRuns = useMemo(
        () => filterByStrictScope(runs, strictScope),
        [runs, strictScope],
    );
    const presetOptions = useMemo(() => buildPresetOptions(runs), [runs]);
    const colorByPreset = useMemo(
        () => buildPresetColorMap(presetOptions.map((option) => option.id)),
        [presetOptions],
    );

    const aggregateRuns = useMemo(
        () => filterByPreset(scopedRuns, presetFilter),
        [scopedRuns, presetFilter],
    );
    const displayRuns = useMemo(
        () => filterByPreset(runs, presetFilter),
        [runs, presetFilter],
    );

    const aggregates = useMemo(
        () => buildModelAggregates(aggregateRuns),
        [aggregateRuns],
    );
    const strictProfiles = useMemo(
        () => buildStrictModeProfiles(filterByPreset(runs, presetFilter)),
        [runs, presetFilter],
    );

    const strictCount = useMemo(() => runs.filter(isStrictRun).length, [runs]);
    const nonStrictCount = runs.length - strictCount;

    if (loadError) return <ErrorState message={loadError} />;
    if (!isLoaded) return <div className="flex items-center justify-center h-64"><div className="w-5 h-5 border-2 border-amber border-t-transparent rounded-full animate-spin" /></div>;
    if (runs.length === 0) return <FirstUseGuide />;

    const scopeLabel = strictScope === 'strict' ? 'Strict 全体' : '非 Strict';
    const emptyScopeMessage = strictScope === 'strict'
        ? 'Strict Mode で enforced された実行がまだありません。非 Strict に切り替えるか、Strict 実行を記録してください。'
        : '非 Strict の実行がありません。Strict に切り替えるか、通常実行を記録してください。';

    return (
        <div className="space-y-10 animate-fade-up">
            <div className="hero-glow relative py-2">
                <div className="relative z-10">
                    <p className="section-label mb-2">観測所</p>
                    <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">ダッシュボード</h1>
                    <p className="text-text-secondary mt-1 text-[13px]">集計済みの評価データを表示します</p>
                </div>
            </div>

            <DashboardFilters
                strictScope={strictScope}
                onStrictScopeChange={setStrictScope}
                strictCount={strictCount}
                nonStrictCount={nonStrictCount}
                presetFilter={presetFilter}
                onPresetFilterChange={setPresetFilter}
                presetOptions={presetOptions}
                colorByPreset={colorByPreset}
                aggregateCount={aggregateRuns.length}
            />

            {aggregateRuns.length === 0 ? (
                <EmptyAggregateState message={presetFilter !== 'all'
                    ? `${scopeLabel} × 選択プリセットに該当する実行がありません。`
                    : emptyScopeMessage}
                />
            ) : (
                <>
                    <ModelScoreChart data={aggregates} scopeLabel={scopeLabel} />
                    <CostEfficiencyChart
                        data={aggregates}
                        scopeLabel={scopeLabel}
                        colorByPreset={colorByPreset}
                        showPresetColors={presetFilter === 'all' && presetOptions.length > 1}
                        presetOptions={presetOptions}
                    />
                    <AggregationTable data={aggregates} scopeLabel={scopeLabel} />
                </>
            )}

            <StrictModeLeaderboard
                profiles={strictProfiles}
                colorByPreset={colorByPreset}
                showPresetColors={presetFilter === 'all' && presetOptions.length > 1}
            />
            <RecentRuns
                runs={displayRuns}
                colorByPreset={colorByPreset}
                showPresetColors={presetFilter === 'all'}
            />
            <EvaluationHistory
                key={presetFilter}
                runs={displayRuns}
                colorByPreset={colorByPreset}
                showPresetColors={presetFilter === 'all'}
            />
            <SideBySideComparison key={presetFilter} runs={displayRuns} />
        </div>
    );
}

function DashboardFilters({
    strictScope,
    onStrictScopeChange,
    strictCount,
    nonStrictCount,
    presetFilter,
    onPresetFilterChange,
    presetOptions,
    colorByPreset,
    aggregateCount,
}: {
    strictScope: StrictScope;
    onStrictScopeChange: (scope: StrictScope) => void;
    strictCount: number;
    nonStrictCount: number;
    presetFilter: string;
    onPresetFilterChange: (value: string) => void;
    presetOptions: PresetOption[];
    colorByPreset: Map<string, string>;
    aggregateCount: number;
}) {
    return (
        <section className="space-y-3 animate-fade-up stagger-1">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <h2 className="section-label">表示フィルタ</h2>
                    <p className="mt-1 text-[12px] text-text-tertiary">
                        上段グラフ・集計表は Strict / 非 Strict を混ぜません。プリセットは履歴に記録された
                        strictMode.presetId で絞り込みます（未記録は「未分類」）。
                    </p>
                </div>
                <span className="text-[10px] uppercase tracking-[0.22em] text-text-tertiary">
                    集計対象 {aggregateCount} 件
                </span>
            </div>

            <div className="card p-4 space-y-4">
                <div>
                    <p className="mb-2 text-[9px] font-display font-bold uppercase tracking-wider text-text-tertiary">
                        Strict 範囲（全体集計）
                    </p>
                    <div className="inline-flex rounded-lg border border-border/80 bg-bg/80 p-1" role="tablist" aria-label="Strict 範囲">
                        <div className="grid grid-cols-2 gap-1 min-w-[280px]">
                            <Button
                                type="button"
                                role="tab"
                                aria-selected={strictScope === 'non-strict'}
                                onClick={() => onStrictScopeChange('non-strict')}
                                className={`rounded-md px-3 py-1.5 text-left transition-all duration-150 ${
                                    strictScope === 'non-strict'
                                        ? 'bg-surface text-text-primary shadow-[0_6px_18px_rgba(0,0,0,0.16)]'
                                        : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
                                }`}
                            >
                                <p className="text-[12px] font-medium">非 Strict</p>
                                <p className="mt-0.5 text-[10px] leading-4 text-text-tertiary">
                                    {nonStrictCount} 件 · 全体集計
                                </p>
                            </Button>
                            <Button
                                type="button"
                                role="tab"
                                aria-selected={strictScope === 'strict'}
                                onClick={() => onStrictScopeChange('strict')}
                                className={`rounded-md px-3 py-1.5 text-left transition-all duration-150 ${
                                    strictScope === 'strict'
                                        ? 'bg-surface text-text-primary shadow-[0_6px_18px_rgba(0,0,0,0.16)]'
                                        : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
                                }`}
                            >
                                <p className="text-[12px] font-medium">Strict 全体</p>
                                <p className="mt-0.5 text-[10px] leading-4 text-text-tertiary">
                                    {strictCount} 件 · プロファイル横断
                                </p>
                            </Button>
                        </div>
                    </div>
                </div>

                <div>
                    <p className="mb-2 text-[9px] font-display font-bold uppercase tracking-wider text-text-tertiary">
                        Execution / Strict プリセット
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                        <Button
                            type="button"
                            onClick={() => onPresetFilterChange('all')}
                            className={`rounded-md border px-2.5 py-1 text-[11px] transition-colors ${
                                presetFilter === 'all'
                                    ? 'border-amber/40 bg-amber/10 text-amber'
                                    : 'border-border text-text-secondary hover:border-amber/30 hover:text-amber'
                            }`}
                        >
                            すべて
                        </Button>
                        {presetOptions.map((option) => (
                            <Button
                                key={option.id}
                                type="button"
                                onClick={() => onPresetFilterChange(option.id)}
                                className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] transition-colors ${
                                    presetFilter === option.id
                                        ? 'border-amber/40 bg-amber/10 text-amber'
                                        : 'border-border text-text-secondary hover:border-amber/30 hover:text-amber'
                                }`}
                            >
                                <span
                                    className="inline-block h-2 w-2 rounded-full"
                                    style={{ backgroundColor: presetColor(option.id, colorByPreset) }}
                                    aria-hidden
                                />
                                {option.label}
                                <span className="text-text-tertiary">{option.count}</span>
                            </Button>
                        ))}
                    </div>
                </div>
            </div>
        </section>
    );
}

function EmptyAggregateState({ message }: { message: string }) {
    return (
        <div className="card border-dashed border-border/80 px-4 py-10 text-center text-[12px] text-text-tertiary">
            {message}
        </div>
    );
}

function PresetLegend({
    presetOptions,
    colorByPreset,
}: {
    presetOptions: PresetOption[];
    colorByPreset: Map<string, string>;
}) {
    if (presetOptions.length <= 1) return null;
    return (
        <div className="flex flex-wrap gap-x-3 gap-y-1 px-1">
            {presetOptions.map((option) => (
                <span key={option.id} className="inline-flex items-center gap-1.5 text-[10px] text-text-tertiary">
                    <span
                        className="inline-block h-2 w-2 rounded-full"
                        style={{ backgroundColor: presetColor(option.id, colorByPreset) }}
                        aria-hidden
                    />
                    {option.label}
                </span>
            ))}
        </div>
    );
}

function ModelScoreChart({ data, scopeLabel }: { data: ModelAggregate[]; scopeLabel: string }) {
    const chartData = data.slice(0, 20);

    return (
        <section className="space-y-3 animate-fade-up stagger-2">
            <div className="flex items-end justify-between gap-3">
                <div>
                    <h2 className="section-label">モデル性能</h2>
                    <p className="mt-1 text-[11px] text-text-tertiary">{scopeLabel}の平均スコア</p>
                </div>
            </div>
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

function CostEfficiencyChart({
    data,
    scopeLabel,
    colorByPreset,
    showPresetColors,
    presetOptions,
}: {
    data: ModelAggregate[];
    scopeLabel: string;
    colorByPreset: Map<string, string>;
    showPresetColors: boolean;
    presetOptions: PresetOption[];
}) {
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
            <div className="flex items-end justify-between gap-3">
                <div>
                    <h2 className="section-label">コスト効率</h2>
                    <p className="mt-1 text-[11px] text-text-tertiary">{scopeLabel} · 点 vs $/1M token</p>
                </div>
            </div>
            {showPresetColors && (
                <PresetLegend presetOptions={presetOptions} colorByPreset={colorByPreset} />
            )}
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
                            <Scatter data={roiData}>
                                {roiData.map((entry) => (
                                    <Cell
                                        key={entry.id}
                                        fill={showPresetColors
                                            ? presetColor(entry.dominantPresetId, colorByPreset)
                                            : '#e2a84b'}
                                    />
                                ))}
                            </Scatter>
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

function StrictModeLeaderboard({
    profiles,
    colorByPreset,
    showPresetColors,
}: {
    profiles: StrictModeProfile[];
    colorByPreset: Map<string, string>;
    showPresetColors: boolean;
}) {
    return (
        <section className="space-y-3 animate-fade-up stagger-4">
            <div className="flex items-end justify-between gap-3">
                <div>
                    <h2 className="section-label">Strict Mode ランキング</h2>
                    <p className="mt-1 text-[12px] text-text-tertiary">
                        プロファイル別の比較用ランキングです。上の「Strict 全体」グラフ（横断集計）とは別物で、
                        同一タスク・評価モデル・評価回数・bundled resource 条件を満たす run だけをプロファイル単位で並べます。
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
                            <div
                                className="border-b border-border px-4 py-3"
                                style={showPresetColors ? {
                                    borderLeftWidth: 3,
                                    borderLeftColor: presetColor(profile.presetId, colorByPreset),
                                } : undefined}
                            >
                                <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <h3 className="text-[14px] font-display font-semibold text-text-primary">
                                                {profile.profileLabel}
                                            </h3>
                                            <span className="rounded-full border border-score-high/30 bg-score-high/10 px-2 py-0.5 text-[9px] uppercase tracking-[0.2em] text-score-high">
                                                strict · プロファイル
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
                                            {['順位', 'モデル', '実行数', '平均', '最高', '単価/1M', '実行時間', '時間ROI'].map((heading) => (
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
                                                <td className="px-4 py-3 text-center text-text-secondary">
                                                    {formatDuration(row.avgExecutionTimeMs)}
                                                </td>
                                                <td className="px-4 py-3 text-center text-text-secondary">
                                                    {formatTimeRoi(row.avgScore, row.avgExecutionTimeMs)}
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

function RecentRuns({
    runs,
    colorByPreset,
    showPresetColors,
}: {
    runs: EvaluationRun[];
    colorByPreset: Map<string, string>;
    showPresetColors: boolean;
}) {
    const navigate = useNavigate();
    const visible = runs.slice(0, 5);

    return (
        <section className="space-y-3 animate-fade-up stagger-4">
            <h2 className="section-label">最近の実行</h2>
            {visible.length === 0 ? (
                <div className="card border-dashed border-border/80 px-4 py-8 text-[12px] text-text-tertiary">
                    選択中のプリセットに該当する実行がありません。
                </div>
            ) : (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                    {visible.map((run, index) => (
                        <Button
                            key={run.id}
                            onClick={() => navigate(buildResultDetailPath(run.id))}
                            className={`card p-3 text-left group transition-all duration-150 hover:border-amber/20 ${scoreGlow(run.averageScore)}`}
                            style={{
                                animationDelay: `${index * 30}ms`,
                                ...(showPresetColors ? {
                                    borderLeftWidth: 3,
                                    borderLeftColor: presetColor(getRunPresetId(run), colorByPreset),
                                } : {}),
                            }}
                        >
                            <div className="flex items-start justify-between gap-2">
                                <p className="text-[12px] font-medium text-text-primary truncate group-hover:text-amber transition-colors">{run.subjectModelName}</p>
                                {showPresetColors && (
                                    <span className="shrink-0 text-[9px] text-text-tertiary">{getRunPresetLabel(run)}</span>
                                )}
                            </div>
                            <div className="mt-1 flex items-end justify-between gap-3">
                                <p className={`data-display text-lg ${scoreTextColor(run.averageScore)}`}>{formatHeroScore(run.averageScore)}</p>
                                {typeof run.subjectCostPer1mTokensUsd === 'number' && (
                                    <span className="text-[10px] text-text-tertiary">{formatUsd(run.subjectCostPer1mTokensUsd)}/1M</span>
                                )}
                            </div>
                            <div className="h-1 bg-border/40 rounded-full overflow-hidden mt-2">
                                <div
                                    className={`h-full rounded-full ${scoreBarClass(run.averageScore)}`}
                                    style={{
                                        width: `${isHeroScoreAvailable(run.averageScore) ? run.averageScore : 0}%`,
                                    }}
                                />
                            </div>
                            <div className="flex items-center justify-between mt-1.5 text-[9px] text-text-tertiary">
                                <span>{formatRelativeTime(run.timestamp)}</span>
                                <span>{run.taskCount}タスク · {run.judgeModels.length || run.judgeCount || 0}評価</span>
                            </div>
                        </Button>
                    ))}
                </div>
            )}
        </section>
    );
}

function EvaluationHistory({
    runs,
    colorByPreset,
    showPresetColors,
}: {
    runs: EvaluationRun[];
    colorByPreset: Map<string, string>;
    showPresetColors: boolean;
}) {
    const navigate = useNavigate();
    const [page, setPage] = useState(0);
    const totalPages = Math.max(1, Math.ceil(runs.length / PAGE_SIZE));
    const safePage = Math.min(page, totalPages - 1);
    const pageRuns = runs.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE);

    return (
        <section className="space-y-3 animate-fade-up stagger-6">
            <h2 className="section-label">履歴</h2>
            {runs.length === 0 ? (
                <div className="card border-dashed border-border/80 px-4 py-8 text-[12px] text-text-tertiary">
                    選択中のプリセットに該当する実行がありません。
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {pageRuns.map((run) => (
                            <Button
                                key={run.id}
                                onClick={() => navigate(buildResultDetailPath(run.id))}
                                className="card p-4 text-left group transition-all duration-150 hover:border-amber/20 accent-bar-ice"
                                style={showPresetColors ? {
                                    borderLeftWidth: 3,
                                    borderLeftColor: presetColor(getRunPresetId(run), colorByPreset),
                                } : undefined}
                            >
                                <div className="flex items-center justify-between gap-3 mb-1.5">
                                    <p className="text-[13px] font-medium text-text-primary group-hover:text-amber transition-colors">{run.subjectModelName}</p>
                                    <div className="text-right">
                                        <span className={`data-display text-[13px] ${scoreTextColor(run.averageScore)}`}>{formatHeroScore(run.averageScore)}</span>
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
                                    {showPresetColors && (
                                        <>
                                            <span>·</span>
                                            <span>{getRunPresetLabel(run)}</span>
                                        </>
                                    )}
                                </div>
                            </Button>
                        ))}
                    </div>
                    {totalPages > 1 && (
                        <div className="flex items-center justify-center gap-3">
                            <Button onClick={() => setPage(Math.max(0, safePage - 1))} disabled={safePage === 0}
                                className="flex items-center gap-1 px-2.5 py-1 border border-border rounded text-[11px] text-text-secondary disabled:opacity-30 hover:border-amber/30 hover:text-amber transition-colors">
                                <ChevronLeft size={12} /> 前へ
                            </Button>
                            <span className="text-[11px] text-text-tertiary data-display">{safePage + 1} / {totalPages}</span>
                            <Button onClick={() => setPage(Math.min(totalPages - 1, safePage + 1))} disabled={safePage === totalPages - 1}
                                className="flex items-center gap-1 px-2.5 py-1 border border-border rounded text-[11px] text-text-secondary disabled:opacity-30 hover:border-amber/30 hover:text-amber transition-colors">
                                次へ <ChevronRight size={12} />
                            </Button>
                        </div>
                    )}
                </>
            )}
        </section>
    );
}

function SideBySideComparison({ runs }: { runs: EvaluationRun[] }) {
    const [leftId, setLeftId] = useState<string>(runs[0]?.id || '');
    const [rightId, setRightId] = useState<string>(runs[1]?.id || '');
    const [show, setShow] = useState(false);
    const resolvedLeftId = runs.some((run) => run.id === leftId) ? leftId : (runs[0]?.id || '');
    const resolvedRightId = runs.some((run) => run.id === rightId)
        ? rightId
        : (runs[1]?.id || runs[0]?.id || '');
    const leftRun = runs.find((run) => run.id === resolvedLeftId);
    const rightRun = runs.find((run) => run.id === resolvedRightId);

    if (runs.length < 2) return null;

    return (
        <section className="space-y-3 animate-fade-up stagger-8">
            <h2 className="section-label">比較</h2>
            <div className="grid grid-cols-2 gap-2">
                {[{ label: '左', value: resolvedLeftId, onChange: setLeftId }, { label: '右', value: resolvedRightId, onChange: setRightId }].map(({ label, value, onChange }) => (
                    <div key={label} className="space-y-1">
                        <label className="text-[9px] text-text-tertiary uppercase tracking-wider">{label}</label>
                        <select value={value} onChange={(event) => onChange(event.target.value)}
                            className="w-full bg-surface border border-border rounded px-3 py-2 text-[12px] text-text-primary focus:outline-none focus:border-amber/40 transition-colors">
                            {runs.map((run) => <option key={run.id} value={run.id}>{run.subjectModelName} — {formatDateTime(run.timestamp)} ({formatHeroScore(run.averageScore)})</option>)}
                        </select>
                    </div>
                ))}
            </div>
            <Button onClick={() => setShow(!show)}
                className="px-3 py-1.5 bg-amber text-bg rounded text-[11px] font-display font-semibold hover:bg-amber-hover transition-all duration-200 hover:shadow-[0_0_16px_rgba(226,168,75,0.12)]">
                {show ? '非表示' : '比較する'}
            </Button>
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
                    <p className={`data-display text-lg ${scoreTextColor(run.averageScore)}`}>{formatHeroScore(run.averageScore)}</p>
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

function formatDuration(value: number | undefined): string {
    if (value === undefined || value === null || Number.isNaN(value)) return 'N/A';
    if (value < 1000) return `${value}ms`;
    return `${(value / 1000).toFixed(1)}s`;
}

function AggregationTable({ data, scopeLabel }: { data: ModelAggregate[]; scopeLabel: string }) {
    return (
        <section className="space-y-3 animate-fade-up stagger-10">
            <div>
                <h2 className="section-label">集計表</h2>
                <p className="mt-1 text-[11px] text-text-tertiary">{scopeLabel}のモデル別集計</p>
            </div>
            <div className="card overflow-hidden">
                <table className="w-full text-[12px]">
                    <thead>
                        <tr className="border-b border-border">
                            {['モデル', '実行数', '平均', '最高', '単価/1M', '実行時間', '時間ROI', '最新'].map((heading) => (
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
                                <td className="px-4 py-2.5 text-center text-text-secondary">{formatDuration(row.avgExecutionTimeMs)}</td>
                                <td className="px-4 py-2.5 text-center text-text-secondary">{formatTimeRoi(row.avgScore, row.avgExecutionTimeMs)}</td>
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
                    <Button onClick={() => navigate('/settings')} className="px-4 py-2 bg-amber text-bg rounded text-[12px] font-display font-semibold hover:bg-amber-hover transition-all duration-200 hover:shadow-[0_0_16px_rgba(226,168,75,0.12)] flex items-center gap-1.5">
                        設定を始める <ArrowRight size={13} />
                    </Button>
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
