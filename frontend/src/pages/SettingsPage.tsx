import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
    deleteOpenRouterAdminKey,
    fetchOpenRouterAdminStatus,
    fetchOpenRouterCredits,
    saveOpenRouterAdminKey,
} from '../api/client';
import { useSettingsStore } from '../store/settingsStore';
import type { Provider } from '../types';
import { PROVIDER_LABELS } from '../types';
import { getStrictModeIssues } from '../lib/strictMode';
import { TASK_TYPE_LABELS, TASK_TYPE_STYLE } from '../lib/taskTypeStyles';
import {
    Trash2,
    RefreshCw,
    Check,
    AlertCircle,
    AlertTriangle,
    ChevronDown,
    Plus,
    X,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { ja } from 'date-fns/locale';

const PROVIDERS: Provider[] = ['openai', 'anthropic', 'gemini', 'openrouter'];

type ModelPickerProps = {
    availableModels: ReturnType<typeof useSettingsStore.getState>['availableModels'];
    open: boolean;
    onOpenChange: (open: boolean) => void;
    placeholder: string;
    selectedLabel: string;
    onSelect: (id: string) => void;
    isSelected: (id: string) => boolean;
    multi?: boolean;
};

function ModelPicker({
    availableModels,
    open,
    onOpenChange,
    placeholder,
    selectedLabel,
    onSelect,
    isSelected,
    multi = false,
}: ModelPickerProps) {
    const [query, setQuery] = useState('');
    const rootRef = useRef<HTMLDivElement | null>(null);

    const filteredModels = useMemo(() => {
        const normalizedQuery = query.trim().toLowerCase();
        if (!normalizedQuery) return availableModels;
        return availableModels.filter((m) =>
            m.name.toLowerCase().includes(normalizedQuery)
            || m.id.toLowerCase().includes(normalizedQuery)
            || PROVIDER_LABELS[m.provider].toLowerCase().includes(normalizedQuery)
        );
    }, [availableModels, query]);

    const displayValue = open ? query : selectedLabel;

    useEffect(() => {
        if (!open) {
            setQuery('');
        }
    }, [open]);

    useEffect(() => {
        const handlePointerDown = (event: MouseEvent) => {
            if (!rootRef.current?.contains(event.target as Node)) {
                onOpenChange(false);
            }
        };

        document.addEventListener('mousedown', handlePointerDown);
        return () => document.removeEventListener('mousedown', handlePointerDown);
    }, [onOpenChange]);

    return (
        <div ref={rootRef} className="relative">
            <div className={`w-full flex items-center gap-2 bg-bg border rounded px-3 py-2 transition-colors duration-150 ${open ? 'border-amber/40' : 'border-border hover:border-border-focus'}`}>
                <input
                    value={displayValue}
                    onFocus={() => onOpenChange(true)}
                    onChange={(e) => {
                        if (!open) onOpenChange(true);
                        setQuery(e.target.value);
                    }}
                    onKeyDown={(e) => {
                        if (e.key === 'Escape') {
                            onOpenChange(false);
                        }
                    }}
                    placeholder={open ? 'モデルを検索...' : placeholder}
                    className="flex-1 bg-transparent text-[13px] text-text-primary placeholder-text-tertiary focus:outline-none"
                />
                <button
                    type="button"
                    onClick={() => onOpenChange(!open)}
                    className="shrink-0 text-text-tertiary hover:text-text-primary transition-colors duration-150"
                    aria-label={open ? 'モデル一覧を閉じる' : 'モデル一覧を開く'}
                >
                    <ChevronDown size={14} className={`transition-transform duration-150 ${open ? 'rotate-180' : ''}`} />
                </button>
            </div>
            {open && (
                <div className="absolute z-20 mt-1 w-full bg-surface border border-border rounded-md shadow-xl max-h-56 overflow-y-auto">
                    {filteredModels.length === 0 && (
                        <div className="px-3 py-2 text-[12px] text-text-tertiary">
                            モデルが見つかりません
                        </div>
                    )}
                    {filteredModels.map((m) => {
                        const selected = isSelected(m.id);
                        return (
                            <button
                                key={m.id}
                                type="button"
                                onMouseDown={(e) => e.preventDefault()}
                                onClick={() => onSelect(m.id)}
                                className={`w-full text-left px-3 py-2 text-[13px] hover:bg-surface-hover transition-colors flex items-center gap-2.5 ${selected ? 'text-amber' : 'text-text-primary'}`}
                            >
                                {multi ? (
                                    <div className={`shrink-0 w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${selected ? 'bg-amber border-amber' : 'border-border-focus'}`}>
                                        {selected && <Check size={9} className="text-bg" />}
                                    </div>
                                ) : null}
                                <span className="flex-1 min-w-0 truncate">{m.name}</span>
                                <span className="shrink-0 text-[11px] text-text-tertiary">{PROVIDER_LABELS[m.provider]}</span>
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

export default function SettingsPage() {
    return (
        <div className="space-y-10 animate-fade-up">
            {/* Hero - Asymmetric */}
            <div className="hero-glow relative flex items-end justify-between py-2">
                <div className="relative z-10">
                    <p className="section-label mb-2">設定調整</p>
                    <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">
                        設定
                    </h1>
                    <p className="text-text-secondary mt-1 text-[13px]">
                        API Key、モデル、パラメータ、タスクを設定します
                    </p>
                </div>
            </div>

            <EvaluationModeSection />
            <ApiKeySection />
            <OpenRouterAdminSection />
            <ModelSelectionSection />
            <EvalParamsSection />
            <TaskSelectionSection />
            <RunLinkSection />
        </div>
    );
}

function EvaluationModeSection() {
    const {
        evaluationMode,
        setEvaluationMode,
        strictPreset,
        strictPresetLoading,
        availableModels,
        tasks,
        selectedTaskIds,
        judgeModelIds,
        evalParams,
    } = useSettingsStore();

    const strictIssues = getStrictModeIssues({
        strictPreset,
        availableModels,
        tasks,
        selectedTaskIds,
        judgeModelIds,
        judgeRunCount: evalParams.judgeRunCount,
        subjectTemperature: evalParams.subjectTemperature,
    });

    return (
        <section className="space-y-3 animate-fade-up stagger-1">
            <div className="flex items-center justify-between">
                <h2 className="section-label">Evaluation Mode</h2>
            </div>

            <div className="flex justify-center">
                <div className="inline-flex rounded-lg border border-border/80 bg-bg/80 p-1" role="tablist" aria-label="Evaluation Mode">
                    <div className="grid grid-cols-2 gap-1 min-w-[280px]">
                    <button
                        type="button"
                        role="tab"
                        aria-selected={evaluationMode === 'standard'}
                        onClick={() => setEvaluationMode('standard')}
                        className={`rounded-md px-3 py-1.5 text-left transition-all duration-150 ${evaluationMode === 'standard'
                            ? 'bg-surface text-text-primary shadow-[0_6px_18px_rgba(0,0,0,0.16)]'
                            : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
                        }`}
                    >
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <p className="text-[12px] font-medium">Standard</p>
                                <p className="mt-0.5 text-[10px] leading-4 text-text-tertiary">
                                    自由に構成
                                </p>
                            </div>
                            {evaluationMode === 'standard' && <Check size={14} className="text-amber" />}
                        </div>
                    </button>

                    <button
                        type="button"
                        role="tab"
                        aria-selected={evaluationMode === 'strict'}
                        onClick={() => setEvaluationMode('strict')}
                        className={`rounded-md px-3 py-1.5 text-left transition-all duration-150 ${evaluationMode === 'strict'
                            ? 'bg-surface text-text-primary shadow-[0_6px_18px_rgba(0,0,0,0.16)]'
                            : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
                        }`}
                    >
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <p className="text-[12px] font-medium">Strict</p>
                                <p className="mt-0.5 text-[10px] leading-4 text-text-tertiary">
                                    比較条件を固定
                                </p>
                            </div>
                            {evaluationMode === 'strict' && <Check size={14} className="text-score-high" />}
                        </div>
                    </button>
                </div>
                </div>
            </div>

            {evaluationMode === 'standard' && (
                <div className="card p-4 space-y-1 border-border bg-bg/90">
                    <p className="text-[13px] font-medium text-text-primary">Standard</p>
                    <p className="text-[11px] leading-5 text-text-tertiary">
                        judge set、task set、parameter を自由に調整する通常モードです。
                    </p>
                </div>
            )}

            {evaluationMode === 'strict' && (
                <div className="card p-4 space-y-3 border-score-high/20 bg-bg/90">
                    {strictPresetLoading && !strictPreset ? (
                        <p className="text-[12px] text-text-tertiary">Strict preset を読み込んでいます...</p>
                    ) : strictPreset ? (
                        <>
                            <div className="space-y-1">
                                <p className="text-[13px] font-medium text-text-primary">{strictPreset.label}</p>
                                <p className="text-[11px] leading-5 text-text-tertiary">
                                    official preset に合わせて比較条件を固定する leaderboard 向けモードです。
                                </p>
                                <p className="text-[11px] leading-5 text-text-tertiary">{strictPreset.description}</p>
                            </div>
                            <div className="grid gap-2 md:grid-cols-4">
                                <StrictSpec label="Task Set" value={`${strictPreset.taskIds.length} tasks`} />
                                <StrictSpec label="Judge Set" value={`${strictPreset.judgeModels.length} judge`} />
                                <StrictSpec label="Judge Runs" value={String(strictPreset.judgeRuns)} />
                                <StrictSpec label="Subject Temperature" value={strictPreset.subjectTemperature.toFixed(2)} />
                            </div>
                            <div className="space-y-2">
                                <p className="text-[11px] font-medium text-text-secondary">Fixed judges</p>
                                <div className="flex flex-wrap gap-1.5">
                                    {strictPreset.judgeModels.map((judge) => (
                                        <span key={judge.id} className="rounded bg-surface-hover px-2 py-1 text-[11px] text-text-secondary">
                                            {judge.label}
                                        </span>
                                    ))}
                                </div>
                            </div>
                            {strictIssues.length > 0 ? (
                                <div className="rounded-md border border-score-low/20 bg-score-low/8 p-3 text-[11px] text-score-low">
                                    <div className="flex items-center gap-1.5">
                                        <AlertCircle size={12} />
                                        <span>Strict Mode の開始条件を満たしていません</span>
                                    </div>
                                    <div className="mt-2 space-y-1">
                                        {strictIssues.map((issue) => (
                                            <p key={issue}>{issue}</p>
                                        ))}
                                    </div>
                                </div>
                            ) : (
                                <div className="rounded-md border border-score-high/20 bg-score-high/8 p-3 text-[11px] text-score-high">
                                    official strict preset の条件を満たしています。実行時にも backend 側で再検証されます。
                                </div>
                            )}
                        </>
                    ) : (
                        <div className="rounded-md border border-score-low/20 bg-score-low/8 p-3 text-[11px] text-score-low">
                            Strict preset を取得できませんでした。
                        </div>
                    )}
                </div>
            )}
        </section>
    );
}

function StrictSpec({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-md border border-border bg-bg/80 px-3 py-2">
            <p className="text-[10px] uppercase tracking-[0.16em] text-text-tertiary">{label}</p>
            <p className="mt-1 data-display text-[14px] text-text-primary">{value}</p>
        </div>
    );
}

/* ===================== API KEY SECTION ===================== */
function ApiKeySection() {
    const { apiKeys, setApiKey, deleteApiKey } = useSettingsStore();
    const [drafts, setDrafts] = useState<Partial<Record<Provider, string>>>({});

    const handleSave = (provider: Provider) => {
        const val = drafts[provider];
        if (!val || !val.trim()) return;
        setApiKey(provider, val.trim());
        setDrafts((d) => ({ ...d, [provider]: '' }));
    };

    const connectedCount = Object.values(apiKeys).filter((e) => e?.isValid).length;

    return (
        <section className="space-y-3 animate-fade-up stagger-1">
            <div className="flex items-center justify-between">
                <h2 className="section-label">API Key</h2>
                <span className="text-[11px] text-text-tertiary">
                    {connectedCount}/{PROVIDERS.length} 接続済み
                </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {PROVIDERS.map((provider, i) => {
                    const entry = apiKeys[provider];
                    const draft = drafts[provider] || '';
                    const hasKey = !!entry;

                    return (
                        <div
                            key={provider}
                            className={`card p-4 transition-all duration-150 animate-fade-up ${hasKey && entry.isValid ? 'accent-bar-high' : hasKey ? 'accent-bar-low' : 'accent-bar-ice'}`}
                            style={{ animationDelay: `${(i + 2) * 30}ms` }}
                        >
                            <div className="flex items-center justify-between mb-3">
                                <span className="text-[13px] font-medium text-text-primary">
                                    {PROVIDER_LABELS[provider]}
                                </span>
                                {hasKey ? (
                                    entry.isValid ? (
                                        <span className="flex items-center gap-1 text-[11px] text-score-high">
                                            <span className="w-1.5 h-1.5 rounded-full bg-score-high inline-block" />
                                            接続済み
                                        </span>
                                    ) : (
                                        <span className="flex items-center gap-1 text-[11px] text-score-low">
                                            <span className="w-1.5 h-1.5 rounded-full bg-score-low inline-block" />
                                            エラー
                                        </span>
                                    )
                                ) : (
                                    <span className="flex items-center gap-1 text-[11px] text-text-tertiary">
                                        <span className="w-1.5 h-1.5 rounded-full bg-text-tertiary inline-block" />
                                        未設定
                                    </span>
                                )}
                            </div>

                            {entry?.error && (
                                <div className="mb-3 p-2 rounded bg-danger/8 border border-danger/15 text-[11px] text-score-low">
                                    {entry.error}
                                </div>
                            )}

                            <div className="flex gap-2">
                                <input
                                    type="password"
                                    value={draft}
                                    onChange={(e) => setDrafts((d) => ({ ...d, [provider]: e.target.value }))}
                                    placeholder={hasKey ? '••••••••' : 'API Key を入力'}
                                    className="flex-1 bg-bg border border-border rounded px-3 py-1.5 text-[13px] text-text-primary placeholder-text-tertiary focus:outline-none focus:border-amber/40 transition-colors duration-150"
                                />
                                <button
                                    onClick={() => handleSave(provider)}
                                    disabled={!draft.trim()}
                                    className="px-3 py-1.5 bg-amber text-bg rounded text-[12px] font-medium disabled:opacity-30 disabled:cursor-not-allowed hover:bg-amber-hover transition-colors duration-150"
                                >
                                    保存
                                </button>
                                {hasKey && (
                                    <button
                                        onClick={() => deleteApiKey(provider)}
                                        className="px-2 py-1.5 border border-border rounded text-text-tertiary hover:text-score-low hover:border-score-low/30 transition-colors duration-150"
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </section>
    );
}

function OpenRouterAdminSection() {
    const [draft, setDraft] = useState('');
    const [configured, setConfigured] = useState(false);
    const [credits, setCredits] = useState<{ totalCredits?: number | null; totalUsage?: number | null; remainingCredits?: number | null } | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async (withCredits = true) => {
        setIsLoading(true);
        setError(null);
        try {
            const status = await fetchOpenRouterAdminStatus();
            setConfigured(status.configured);
            if (status.configured && withCredits) {
                const creditState = await fetchOpenRouterCredits();
                setCredits({
                    totalCredits: creditState.totalCredits,
                    totalUsage: creditState.totalUsage,
                    remainingCredits: creditState.remainingCredits,
                });
            } else {
                setCredits(null);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'OpenRouter credits の読み込みに失敗しました');
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        void load(true);
    }, [load]);

    const handleSave = async () => {
        if (!draft.trim()) return;
        setIsSaving(true);
        setError(null);
        try {
            await saveOpenRouterAdminKey(draft.trim());
            setDraft('');
            await load(true);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Management Key の保存に失敗しました');
        } finally {
            setIsSaving(false);
        }
    };

    const handleDelete = async () => {
        setIsRefreshing(true);
        setError(null);
        try {
            await deleteOpenRouterAdminKey();
            setConfigured(false);
            setCredits(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Management Key の削除に失敗しました');
        } finally {
            setIsRefreshing(false);
        }
    };

    const handleRefreshCredits = async () => {
        setIsRefreshing(true);
        setError(null);
        try {
            const creditState = await fetchOpenRouterCredits();
            setConfigured(creditState.configured);
            setCredits({
                totalCredits: creditState.totalCredits,
                totalUsage: creditState.totalUsage,
                remainingCredits: creditState.remainingCredits,
            });
        } catch (err) {
            setError(err instanceof Error ? err.message : 'OpenRouter credits の更新に失敗しました');
        } finally {
            setIsRefreshing(false);
        }
    };

    return (
        <section className="space-y-3 animate-fade-up stagger-2">
            <div className="flex items-center justify-between">
                <h2 className="section-label">OpenRouter Admin</h2>
                <span className={`text-[11px] ${configured ? 'text-score-high' : 'text-text-tertiary'}`}>
                    {configured ? 'Management Key 設定済み' : '未設定'}
                </span>
            </div>

            <div className="card p-4 space-y-4">
                <div className="space-y-1">
                    <p className="text-[13px] font-medium text-text-primary">Credits Monitor</p>
                    <p className="text-[11px] leading-5 text-text-tertiary">
                        OpenRouter の残高確認専用です。通常の推論用 API Key とは分離して保存されます。
                    </p>
                </div>

                <div className="flex gap-2">
                    <input
                        type="password"
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        placeholder={configured ? '••••••••' : 'Management Key を入力'}
                        className="flex-1 bg-bg border border-border rounded px-3 py-1.5 text-[13px] text-text-primary placeholder-text-tertiary focus:outline-none focus:border-amber/40 transition-colors duration-150"
                    />
                    <button
                        onClick={() => void handleSave()}
                        disabled={!draft.trim() || isSaving}
                        className="px-3 py-1.5 bg-amber text-bg rounded text-[12px] font-medium disabled:opacity-30 disabled:cursor-not-allowed hover:bg-amber-hover transition-colors duration-150"
                    >
                        {isSaving ? '保存中...' : '保存'}
                    </button>
                    {configured && (
                        <button
                            onClick={() => void handleDelete()}
                            disabled={isRefreshing}
                            className="px-2 py-1.5 border border-border rounded text-text-tertiary hover:text-score-low hover:border-score-low/30 transition-colors duration-150 disabled:opacity-40"
                        >
                            <Trash2 size={14} />
                        </button>
                    )}
                </div>

                <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-bg/70 px-3 py-3">
                    <div>
                        <p className="text-[10px] uppercase tracking-[0.16em] text-text-tertiary">Remaining Credits</p>
                        <p className="mt-1 data-display text-[20px] text-text-primary">
                            {isLoading
                                ? '...'
                                : typeof credits?.remainingCredits === 'number'
                                    ? credits.remainingCredits.toFixed(4)
                                    : configured
                                        ? '---'
                                        : '未設定'}
                        </p>
                    </div>
                    <button
                        onClick={() => void handleRefreshCredits()}
                        disabled={!configured || isRefreshing}
                        className="flex items-center gap-1.5 px-2.5 py-1.5 border border-border rounded text-[11px] text-text-secondary hover:text-amber hover:border-amber/30 transition-colors duration-150 disabled:opacity-40"
                    >
                        <RefreshCw size={12} className={isRefreshing ? 'animate-spin' : ''} />
                        更新
                    </button>
                </div>

                {credits && (
                    <div className="grid gap-2 md:grid-cols-2">
                        <StrictSpec label="Total Credits" value={typeof credits.totalCredits === 'number' ? credits.totalCredits.toFixed(4) : '---'} />
                        <StrictSpec label="Total Usage" value={typeof credits.totalUsage === 'number' ? credits.totalUsage.toFixed(4) : '---'} />
                    </div>
                )}

                {error && (
                    <div className="rounded-md border border-score-low/20 bg-score-low/8 p-3 text-[11px] text-score-low">
                        {error}
                    </div>
                )}
            </div>
        </section>
    );
}

/* ===================== MODEL SELECTION SECTION ===================== */
function ModelSelectionSection() {
    const {
        apiKeys,
        availableModels,
        modelsLastUpdated,
        evaluationMode,
        strictPreset,
        subjectModelId,
        judgeModelIds,
        setSubjectModel,
        toggleJudgeModel,
        refreshModels,
        freeTextSubject,
        freeTextJudges,
        setFreeTextSubject,
        addFreeTextJudge,
        removeFreeTextJudge,
    } = useSettingsStore();

    const [judgeInput, setJudgeInput] = useState('');
    const hasAnyKey = Object.keys(apiKeys).length > 0;
    const [subjectOpen, setSubjectOpen] = useState(false);
    const [judgeOpen, setJudgeOpen] = useState(false);
    const isStrict = evaluationMode === 'strict';

    const judgeCount = judgeModelIds.length + freeTextJudges.length;
    const showError = judgeCount < 1;
    const showWarning = !isStrict && judgeCount >= 1 && judgeCount < 3;
    const subjectLabel = subjectModelId
        ? availableModels.find((m) => m.id === subjectModelId)?.name || subjectModelId
        : '';
    const judgeLabel = judgeModelIds.length > 0
        ? `${judgeModelIds.length}件選択中`
        : '';

    return (
        <section className={`relative space-y-3 animate-fade-up stagger-3 ${(subjectOpen || judgeOpen) ? 'z-50' : 'z-0'}`}>
            <div className="flex items-center justify-between">
                <h2 className="section-label">モデル</h2>
                <div className="flex items-center gap-3">
                    {modelsLastUpdated && (
                        <span className="text-[11px] text-text-tertiary">
                            {formatDistanceToNow(new Date(modelsLastUpdated), { addSuffix: true, locale: ja })}に更新
                        </span>
                    )}
                    <button
                        onClick={() => refreshModels(true)}
                        className="flex items-center gap-1.5 px-2.5 py-1 border border-border rounded text-[11px] text-text-secondary hover:text-amber hover:border-amber/30 transition-colors duration-150"
                    >
                        <RefreshCw size={12} />
                        再取得
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {/* Subject Model */}
                <div className="card p-4 space-y-2 accent-bar-amber">
                    <label className="section-label text-[9px]">被験モデル</label>
                    {hasAnyKey ? (
                        <ModelPicker
                            availableModels={availableModels}
                            open={subjectOpen}
                            onOpenChange={setSubjectOpen}
                            placeholder="モデルを選択"
                            selectedLabel={subjectLabel}
                            onSelect={(id) => {
                                setSubjectModel(id);
                                setSubjectOpen(false);
                            }}
                            isSelected={(id) => subjectModelId === id}
                        />
                    ) : (
                        <div className="space-y-1.5">
                            <p className="text-[11px] text-text-tertiary">API Key が未設定のため、手動で入力してください。</p>
                            <input
                                value={freeTextSubject}
                                onChange={(e) => setFreeTextSubject(e.target.value)}
                                placeholder="例: gpt-4o"
                                className="w-full bg-bg border border-border rounded px-3 py-2 text-[13px] text-text-primary placeholder-text-tertiary focus:outline-none focus:border-amber/40 transition-colors duration-150"
                            />
                        </div>
                    )}
                </div>

                {/* Judge Models */}
                <div className="card p-4 space-y-2 accent-bar-ice">
                    <label className="section-label text-[9px]">
                        評価モデル
                        <span className={`ml-1.5 font-mono ${showError ? 'text-score-low' : showWarning ? 'text-score-mid' : 'text-score-high'}`}>
                            ({judgeCount})
                        </span>
                    </label>

                    {showError && (
                        <div className="flex items-center gap-1.5 p-2 rounded bg-score-low/8 text-[11px] text-score-low">
                            <AlertCircle size={12} />
                            評価モデルを1つ以上選択してください
                        </div>
                    )}
                    {showWarning && (
                        <div className="flex items-center gap-1.5 p-2 rounded bg-score-mid/8 text-[11px] text-score-mid">
                            <AlertTriangle size={12} />
                            推奨: 3モデル以上
                        </div>
                    )}

                    {isStrict && strictPreset ? (
                        <div className="space-y-2">
                            <div className="rounded-md border border-score-high/20 bg-score-high/8 px-3 py-2 text-[11px] text-score-high">
                                official strict preset により固定されています
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {strictPreset.judgeModels.map((judge) => (
                                    <span key={judge.id} className="flex items-center gap-1 rounded bg-surface-hover px-2 py-1 text-[11px] text-text-secondary">
                                        <span>{judge.label}</span>
                                        <span className="text-text-tertiary">· {PROVIDER_LABELS[judge.provider]}</span>
                                    </span>
                                ))}
                            </div>
                        </div>
                    ) : hasAnyKey ? (
                        <div className="space-y-2">
                            <ModelPicker
                                availableModels={availableModels}
                                open={judgeOpen}
                                onOpenChange={setJudgeOpen}
                                placeholder="評価モデルを選択"
                                selectedLabel={judgeLabel}
                                onSelect={(id) => toggleJudgeModel(id)}
                                isSelected={(id) => judgeModelIds.includes(id)}
                                multi
                            />
                            {judgeModelIds.length > 0 && (
                                <div className="flex flex-wrap gap-1.5">
                                    {judgeModelIds.map((id) => {
                                        const model = availableModels.find((m) => m.id === id);
                                        const label = model?.name || id;
                                        return (
                                            <button
                                                key={id}
                                                onClick={() => toggleJudgeModel(id)}
                                                className="flex items-center gap-1 px-2 py-0.5 bg-amber-dim rounded text-[11px] text-amber hover:text-score-low transition-colors duration-150"
                                            >
                                                <span>{label}</span>
                                                <X size={10} />
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="space-y-1.5">
                            <p className="text-[11px] text-text-tertiary">API Key が未設定のため、手動で入力してください。</p>
                            <div className="flex gap-2">
                                <input
                                    value={judgeInput}
                                    onChange={(e) => setJudgeInput(e.target.value)}
                                    onKeyDown={(e) => { if (e.key === 'Enter') { addFreeTextJudge(judgeInput); setJudgeInput(''); } }}
                                placeholder="例: claude-3.5-sonnet"
                                    className="flex-1 bg-bg border border-border rounded px-3 py-1.5 text-[13px] text-text-primary placeholder-text-tertiary focus:outline-none focus:border-amber/40 transition-colors duration-150"
                                />
                                <button
                                    onClick={() => { addFreeTextJudge(judgeInput); setJudgeInput(''); }}
                                    className="px-2.5 py-1.5 bg-amber text-bg rounded hover:bg-amber-hover transition-colors duration-150"
                                >
                                    <Plus size={14} />
                                </button>
                            </div>
                            {freeTextJudges.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 mt-1">
                                    {freeTextJudges.map((j) => (
                                        <span key={j} className="flex items-center gap-1 px-2 py-0.5 bg-amber-dim rounded text-[11px] text-amber">
                                            {j}
                                            <button onClick={() => removeFreeTextJudge(j)} className="hover:text-score-low"><X size={10} /></button>
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </section>
    );
}

/* ===================== EVAL PARAMS SECTION ===================== */
function EvalParamsSection() {
    const { evaluationMode, strictPreset, evalParams, setJudgeRunCount, setSubjectTemperature } = useSettingsStore();
    const isStrict = evaluationMode === 'strict' && !!strictPreset;

    return (
        <section className="space-y-3 animate-fade-up stagger-5">
            <h2 className="section-label">パラメータ</h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                <div className="card p-4 space-y-2 accent-bar-amber">
                    <label className="text-[11px] font-medium text-text-secondary">評価回数</label>
                    <div className="flex items-center gap-3">
                        {isStrict ? (
                            <div className="flex-1 h-1 bg-border rounded-full" />
                        ) : (
                            <input
                                type="range" min={1} max={5}
                                value={evalParams.judgeRunCount}
                                onChange={(e) => setJudgeRunCount(Number(e.target.value))}
                                className="flex-1 accent-amber h-1"
                            />
                        )}
                        <span className="data-display text-lg text-text-primary w-6 text-center">
                            {evalParams.judgeRunCount}
                        </span>
                    </div>
                    <p className="text-[11px] text-text-tertiary">
                        {isStrict ? 'Strict Mode では fixed value です' : '各評価モデルごとの実行回数（1-5）'}
                    </p>
                </div>

                <div className="card p-4 space-y-2 accent-bar-amber">
                    <label className="text-[11px] font-medium text-text-secondary">Subject Temperature</label>
                    <div className="flex items-center gap-3">
                        {isStrict ? (
                            <div className="flex-1 h-1 bg-border rounded-full" />
                        ) : (
                            <input
                                type="range" min={0} max={100}
                                value={evalParams.subjectTemperature * 100}
                                onChange={(e) => setSubjectTemperature(Number(e.target.value) / 100)}
                                className="flex-1 accent-amber h-1"
                            />
                        )}
                        <span className="data-display text-lg text-text-primary w-10 text-center">
                            {evalParams.subjectTemperature.toFixed(2)}
                        </span>
                    </div>
                    <p className="text-[11px] text-text-tertiary">
                        {isStrict ? 'official strict preset により固定されています' : '創造性（0.0-1.0）'}
                    </p>
                </div>

                <div className="card p-4 space-y-2 opacity-40">
                    <label className="text-[11px] font-medium text-text-secondary">Judge Temperature</label>
                    <div className="flex items-center gap-3">
                        <div className="flex-1 h-1 bg-border rounded-full" />
                        <span className="data-display text-lg text-text-tertiary w-10 text-center">0.00</span>
                    </div>
                    <p className="text-[11px] text-text-tertiary">決定的な評価のため 0.0 固定</p>
                </div>
            </div>
        </section>
    );
}

/* ===================== TASK SELECTION SECTION ===================== */
function TaskSelectionSection() {
    const { evaluationMode, strictPreset, tasks, tasksLoading, selectedTaskIds, toggleTask, selectAllTasks, deselectAllTasks } = useSettingsStore();
    const isStrict = evaluationMode === 'strict' && !!strictPreset;

    return (
        <section className="space-y-3 animate-fade-up stagger-7">
            <div className="flex items-center justify-between">
                <h2 className="section-label">
                    タスク
                    <span className="ml-2 font-mono text-text-tertiary text-[10px]">
                        {selectedTaskIds.length}/{tasks.length}
                    </span>
                </h2>
                <div className="flex gap-1.5">
                    <button
                        onClick={selectAllTasks}
                        disabled={isStrict}
                        className="px-2.5 py-1 rounded text-[11px] text-amber bg-amber-dim hover:bg-amber/15 transition-colors duration-150"
                    >
                        すべて選択
                    </button>
                    <button
                        onClick={deselectAllTasks}
                        disabled={isStrict}
                        className="px-2.5 py-1 rounded text-[11px] text-text-secondary border border-border hover:border-border-focus transition-colors duration-150"
                    >
                        すべて解除
                    </button>
                </div>
            </div>
            {isStrict && (
                <div className="rounded-md border border-score-high/20 bg-score-high/8 px-3 py-2 text-[11px] text-score-high">
                    task set は official strict preset により固定されています
                </div>
            )}

            {tasksLoading ? (
                <div className="flex items-center justify-center h-32">
                    <div className="w-5 h-5 border-2 border-amber border-t-transparent rounded-full animate-spin" />
                </div>
            ) : (
                <div className="space-y-1">
                    {tasks.map((task, i) => {
                        const isSelected = selectedTaskIds.includes(task.id);
                        return (
                            <button
                                key={task.id}
                                onClick={() => toggleTask(task.id)}
                                disabled={isStrict}
                                className={`w-full text-left flex items-center gap-3 px-4 py-3 rounded-md border transition-all duration-150 group ${isSelected
                                    ? 'bg-amber-dim border-amber/15 accent-bar-amber'
                                    : 'bg-surface border-border hover:bg-surface-hover hover:border-border-focus'
                                    }`}
                                style={{ animationDelay: `${i * 20}ms` }}
                            >
                                <div className={`shrink-0 w-4 h-4 rounded border flex items-center justify-center transition-colors ${isSelected ? 'bg-amber border-amber' : 'border-border-focus'}`}>
                                    {isSelected && <Check size={10} className="text-bg" />}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-0.5">
                                        <span className="data-display text-[13px] text-text-primary">{task.id}</span>
                                        <span className={`px-1.5 py-0 rounded text-[10px] font-medium ${TASK_TYPE_STYLE[task.type] || 'bg-surface-hover text-text-secondary'}`}>
                                            {TASK_TYPE_LABELS[task.type] || task.type}
                                        </span>
                                    </div>
                                    <p className="text-[12px] text-text-tertiary truncate">{task.promptPreview}</p>
                                </div>
                            </button>
                        );
                    })}
                </div>
            )}
        </section>
    );
}

function RunLinkSection() {
    return (
        <section className="animate-fade-up stagger-9">
            <div className="card p-6 accent-bar-amber flex flex-col items-center text-center gap-5">
                <div>
                    <h2 className="section-label text-[12px]">次のステップ</h2>
                    <p className="mt-1.5 text-[15px] text-text-secondary">
                        設定が終わったら、そのまま評価実行に進みます。
                    </p>
                </div>
                <Link
                    to="/run"
                    className="inline-flex items-center justify-center px-5 py-3 bg-amber text-bg rounded-md text-[13px] font-display font-semibold hover:bg-amber-hover transition-all duration-200 hover:shadow-[0_0_24px_rgba(226,168,75,0.15)]"
                >
                    実行画面へ進む
                </Link>
            </div>
        </section>
    );
}
