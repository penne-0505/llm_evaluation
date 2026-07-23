import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
    deleteOpenRouterAdminKey,
    deleteLMStudioConfig,
    fetchLMStudioConfig,
    fetchOpenRouterAdminStatus,
    fetchOpenRouterCredits,
    saveLMStudioConfig,
    saveOpenRouterAdminKey,
} from '../api/client';
import { useSettingsStore } from '../store/settingsStore';
import type { ProviderKind, RegistryProvider, ToolMode } from '../types';
import { providerDisplayName } from '../types';
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
    Save,
    FolderOpen,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { ja } from 'date-fns/locale';
import Button from '../components/Button';

type ModelPickerProps = {
    availableModels: ReturnType<typeof useSettingsStore.getState>['availableModels'];
    registryProviders: RegistryProvider[];
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
    registryProviders,
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
    const setOpen = useCallback((nextOpen: boolean) => {
        if (!nextOpen) {
            setQuery('');
        }
        onOpenChange(nextOpen);
    }, [onOpenChange]);

    const labelFor = useCallback(
        (providerId: string) => providerDisplayName(providerId, registryProviders),
        [registryProviders],
    );

    const filteredModels = useMemo(() => {
        const normalizedQuery = query.trim().toLowerCase();
        if (!normalizedQuery) return availableModels;
        return availableModels.filter((m) =>
            m.name.toLowerCase().includes(normalizedQuery)
            || m.id.toLowerCase().includes(normalizedQuery)
            || labelFor(m.provider).toLowerCase().includes(normalizedQuery)
        );
    }, [availableModels, query, labelFor]);

    const groupedModels = useMemo(() => {
        const groups: { provider: string; label: string; models: typeof filteredModels }[] = [];
        const indexByProvider = new Map<string, number>();
        for (const model of filteredModels) {
            let idx = indexByProvider.get(model.provider);
            if (idx === undefined) {
                idx = groups.length;
                indexByProvider.set(model.provider, idx);
                groups.push({
                    provider: model.provider,
                    label: labelFor(model.provider),
                    models: [],
                });
            }
            groups[idx].models.push(model);
        }
        return groups;
    }, [filteredModels, labelFor]);

    const displayValue = open ? query : selectedLabel;

    useEffect(() => {
        const handlePointerDown = (event: MouseEvent) => {
            if (!rootRef.current?.contains(event.target as Node)) {
                setOpen(false);
            }
        };

        document.addEventListener('mousedown', handlePointerDown);
        return () => document.removeEventListener('mousedown', handlePointerDown);
    }, [setOpen]);

    return (
        <div ref={rootRef} className="relative">
            <div className={`w-full flex items-center gap-2 bg-bg border rounded px-3 py-2 transition-colors duration-150 ${open ? 'border-amber/40' : 'border-border hover:border-border-focus'}`}>
                <input
                    value={displayValue}
                    onFocus={() => setOpen(true)}
                    onChange={(e) => {
                        if (!open) setOpen(true);
                        setQuery(e.target.value);
                    }}
                    onKeyDown={(e) => {
                        if (e.key === 'Escape') {
                            setOpen(false);
                        }
                    }}
                    placeholder={open ? 'モデルを検索...' : placeholder}
                    className="flex-1 bg-transparent text-[13px] text-text-primary placeholder-text-tertiary focus:outline-none"
                />
                <Button
                    type="button"
                    onClick={() => setOpen(!open)}
                    className="shrink-0 text-text-tertiary hover:text-text-primary transition-colors duration-150"
                    aria-label={open ? 'モデル一覧を閉じる' : 'モデル一覧を開く'}
                >
                    <ChevronDown size={14} className={`transition-transform duration-150 ${open ? 'rotate-180' : ''}`} />
                </Button>
            </div>
            {open && (
                <div className="absolute z-20 mt-1 w-full bg-surface border border-border rounded-md shadow-xl max-h-56 overflow-y-auto">
                    {filteredModels.length === 0 && (
                        <div className="px-3 py-2 text-[12px] text-text-tertiary">
                            モデルが見つかりません
                        </div>
                    )}
                    {groupedModels.map((group) => (
                        <div key={group.provider}>
                            <div className="sticky top-0 px-3 py-1.5 text-[10px] uppercase tracking-[0.14em] text-text-tertiary bg-surface border-b border-border/60">
                                {group.label}
                            </div>
                            {group.models.map((m) => {
                                const selected = isSelected(m.id);
                                return (
                                    <Button
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
                                        <span className="shrink-0 text-[11px] text-text-tertiary">{group.label}</span>
                                    </Button>
                                );
                            })}
                        </div>
                    ))}
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
            <ExecutionPresetSection />
            <ApiKeySection />
            <OpenRouterAdminSection />
            <ModelSelectionSection />
            <EvalParamsSection />
            <HolisticSection />
            <ParallelSection />
            <TaskSelectionSection />
            <RunLinkSection />
        </div>
    );
}

function ExecutionPresetSection() {
    const {
        executionPresets,
        modelsLoading,
        tasksLoading,
        saveExecutionPreset,
        overwriteExecutionPreset,
        loadExecutionPreset,
        deleteExecutionPreset,
    } = useSettingsStore();
    const [selectedPresetId, setSelectedPresetId] = useState('');
    const [presetName, setPresetName] = useState('');
    const selectedPreset = executionPresets.find((preset) => preset.id === selectedPresetId);
    const effectiveSelectedPresetId = selectedPreset ? selectedPresetId : '';
    const normalizedName = presetName.trim();
    const duplicateName = executionPresets.some((preset) => preset.name === normalizedName);
    const loadingCatalog = modelsLoading || tasksLoading;

    const handleSave = () => {
        const id = saveExecutionPreset(normalizedName);
        if (!id) return;
        setSelectedPresetId(id);
        setPresetName('');
    };

    const handleOverwrite = () => {
        if (!selectedPreset) return;
        if (!window.confirm(`「${selectedPreset.name}」を現在の設定で上書きしますか？`)) return;
        overwriteExecutionPreset(selectedPreset.id);
    };

    const handleDelete = () => {
        if (!selectedPreset) return;
        if (!window.confirm(`「${selectedPreset.name}」を削除しますか？`)) return;
        deleteExecutionPreset(selectedPreset.id);
        setSelectedPresetId('');
    };

    return (
        <section className="space-y-3 animate-fade-up stagger-2">
            <div className="flex items-end justify-between gap-4">
                <div>
                    <h2 className="section-label">実行プリセット</h2>
                    <p className="mt-1 text-[11px] text-text-tertiary">
                        モデル、タスク、包括評価、評価回数、temperatureをブラウザに保存します
                    </p>
                </div>
                <span className="data-display text-[11px] text-text-tertiary tabular-nums">
                    {executionPresets.length} saved
                </span>
            </div>

            <div className="card p-4 space-y-4">
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
                    <label className="space-y-1.5">
                        <span className="text-[11px] font-medium text-text-secondary">保存済みプリセット</span>
                        <select
                            value={effectiveSelectedPresetId}
                            onChange={(event) => setSelectedPresetId(event.target.value)}
                            className="h-10 w-full rounded-md border border-border bg-bg px-3 text-[13px] text-text-primary focus:border-amber/40 focus:outline-none transition-colors duration-150"
                        >
                            <option value="">プリセットを選択</option>
                            {executionPresets.map((preset) => (
                                <option key={preset.id} value={preset.id}>{preset.name}</option>
                            ))}
                        </select>
                    </label>

                    <div className="flex flex-wrap items-end gap-2">
                        <Button
                            onClick={() => selectedPreset && loadExecutionPreset(selectedPreset.id)}
                            disabled={!selectedPreset || loadingCatalog}
                            className="h-10 min-w-24 rounded-md border border-amber/30 px-3 text-[12px] text-amber transition-[color,background-color,border-color,opacity,transform] duration-150 hover:bg-amber-dim active:scale-[0.96] disabled:opacity-40"
                        >
                            <span className="flex items-center justify-center gap-1.5">
                                <FolderOpen size={13} />
                                読み込み
                            </span>
                        </Button>
                        <Button
                            onClick={handleOverwrite}
                            disabled={!selectedPreset}
                            className="h-10 rounded-md border border-border px-3 text-[12px] text-text-secondary transition-[color,background-color,border-color,opacity,transform] duration-150 hover:border-border-focus hover:text-text-primary active:scale-[0.96] disabled:opacity-40"
                        >
                            上書き
                        </Button>
                        <Button
                            onClick={handleDelete}
                            disabled={!selectedPreset}
                            aria-label="選択中の実行プリセットを削除"
                            className="flex h-10 w-10 items-center justify-center rounded-md border border-border text-text-tertiary transition-[color,background-color,border-color,opacity,transform] duration-150 hover:border-score-low/30 hover:text-score-low active:scale-[0.96] disabled:opacity-40"
                        >
                            <Trash2 size={14} />
                        </Button>
                    </div>
                </div>

                <div className="grid grid-cols-1 gap-3 border-t border-border pt-4 lg:grid-cols-[minmax(0,1fr)_auto]">
                    <label className="space-y-1.5">
                        <span className="text-[11px] font-medium text-text-secondary">新しいプリセット名</span>
                        <input
                            value={presetName}
                            onChange={(event) => setPresetName(event.target.value)}
                            onKeyDown={(event) => {
                                if (event.key === 'Enter' && normalizedName && !duplicateName) {
                                    handleSave();
                                }
                            }}
                            placeholder="例: Strict比較用 / ローカル高速確認"
                            className="h-10 w-full rounded-md border border-border bg-bg px-3 text-[13px] text-text-primary placeholder-text-tertiary focus:border-amber/40 focus:outline-none transition-colors duration-150"
                        />
                    </label>
                    <Button
                        onClick={handleSave}
                        disabled={!normalizedName || duplicateName}
                        title={duplicateName ? '同名のプリセットが存在します' : undefined}
                        className="flex h-10 min-w-28 items-center justify-center gap-1.5 self-end rounded-md bg-amber px-4 text-[12px] font-medium text-bg transition-[color,background-color,opacity,transform] duration-150 hover:bg-amber-hover active:scale-[0.96] disabled:opacity-40"
                    >
                        <Save size={13} />
                        現在設定を保存
                    </Button>
                </div>
            </div>
        </section>
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
                    <Button
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
                    </Button>

                    <Button
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
                    </Button>
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
                                <p className="text-[11px] leading-5 text-text-tertiary">
                                    judge モデルはすべて OpenRouter 経由で呼び出されます。
                                </p>
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

/* ===================== API KEY / PROVIDER REGISTRY SECTION ===================== */
function ApiKeySection() {
    const {
        apiKeys,
        setApiKey,
        deleteApiKey,
        registryProviders,
        addCustomProvider,
        removeCustomProvider,
        registryLoading,
    } = useSettingsStore();
    const [drafts, setDrafts] = useState<Record<string, string>>({});
    const [showAddForm, setShowAddForm] = useState(false);
    const [newName, setNewName] = useState('');
    const [newKind, setNewKind] = useState<ProviderKind>('openai_compatible');
    const [newBaseUrl, setNewBaseUrl] = useState('');
    const [adding, setAdding] = useState(false);
    const [addError, setAddError] = useState<string | null>(null);

    const handleSave = (providerId: string) => {
        const val = drafts[providerId];
        if (!val || !val.trim()) return;
        void setApiKey(providerId, val.trim());
        setDrafts((d) => ({ ...d, [providerId]: '' }));
    };

    const connectedCount = registryProviders.filter((p) => p.hasKey).length;
    const totalCount = registryProviders.length;

    const handleAdd = async () => {
        const name = newName.trim();
        if (!name) return;
        if (newKind === 'openai_compatible' && !newBaseUrl.trim()) {
            setAddError('OpenAI 互換には base URL が必要です');
            return;
        }
        setAdding(true);
        setAddError(null);
        const created = await addCustomProvider({
            displayName: name,
            kind: newKind,
            baseUrl: newKind === 'openai_compatible' ? newBaseUrl.trim() : undefined,
        });
        setAdding(false);
        if (!created) {
            setAddError('プロバイダの追加に失敗しました');
            return;
        }
        setNewName('');
        setNewBaseUrl('');
        setNewKind('openai_compatible');
        setShowAddForm(false);
    };

    return (
        <section className="space-y-3 animate-fade-up stagger-1">
            <div className="flex items-center justify-between">
                <h2 className="section-label">プロバイダ / API Key</h2>
                <span className="text-[11px] text-text-tertiary">
                    {registryLoading ? '読込中…' : `${connectedCount}/${totalCount || '—'} 接続済み`}
                </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {registryProviders.map((provider, i) => {
                    const entry = apiKeys[provider.id];
                    const draft = drafts[provider.id] || '';
                    const hasKey = provider.hasKey || !!entry?.isValid;

                    return (
                        <div
                            key={provider.id}
                            className={`card p-4 transition-all duration-150 animate-fade-up ${hasKey && (!entry || entry.isValid) ? 'accent-bar-high' : entry && !entry.isValid ? 'accent-bar-low' : 'accent-bar-ice'}`}
                            style={{ animationDelay: `${(i + 2) * 30}ms` }}
                        >
                            <div className="flex items-center justify-between mb-2">
                                <div className="min-w-0">
                                    <span className="text-[13px] font-medium text-text-primary">
                                        {provider.displayName}
                                    </span>
                                    <p className="text-[10px] text-text-tertiary mt-0.5 truncate">
                                        {provider.kind}
                                        {provider.baseUrl ? ` · ${provider.baseUrl}` : ''}
                                        {provider.builtin ? ' · 組み込み' : ''}
                                    </p>
                                </div>
                                {hasKey ? (
                                    entry && !entry.isValid ? (
                                        <span className="flex items-center gap-1 text-[11px] text-score-low shrink-0">
                                            <span className="w-1.5 h-1.5 rounded-full bg-score-low inline-block" />
                                            エラー
                                        </span>
                                    ) : (
                                        <span className="flex items-center gap-1 text-[11px] text-score-high shrink-0">
                                            <span className="w-1.5 h-1.5 rounded-full bg-score-high inline-block" />
                                            接続済み
                                        </span>
                                    )
                                ) : (
                                    <span className="flex items-center gap-1 text-[11px] text-text-tertiary shrink-0">
                                        <span className="w-1.5 h-1.5 rounded-full bg-text-tertiary inline-block" />
                                        未設定
                                    </span>
                                )}
                            </div>

                            {provider.id === 'google-ai-studio' && (
                                <p className="mb-3 text-[11px] leading-5 text-text-secondary">
                                    base URL は組み込み済みです。Google AI Studio の Gemini API キーを貼り付けてください。
                                </p>
                            )}

                            {entry?.error && (
                                <div className="mb-3 p-2 rounded bg-danger/8 border border-danger/15 text-[11px] text-score-low">
                                    {entry.error}
                                </div>
                            )}

                            <div className="flex gap-2">
                                <input
                                    type="password"
                                    value={draft}
                                    onChange={(e) => setDrafts((d) => ({ ...d, [provider.id]: e.target.value }))}
                                    placeholder={hasKey ? '••••••••' : 'API Key を入力'}
                                    className="flex-1 bg-bg border border-border rounded px-3 py-1.5 text-[13px] text-text-primary placeholder-text-tertiary focus:outline-none focus:border-amber/40 transition-colors duration-150"
                                />
                                <Button
                                    onClick={() => handleSave(provider.id)}
                                    disabled={!draft.trim()}
                                    className="px-3 py-1.5 bg-amber text-bg rounded text-[12px] font-medium disabled:opacity-30 disabled:cursor-not-allowed hover:bg-amber-hover transition-colors duration-150"
                                >
                                    保存
                                </Button>
                                {hasKey && (
                                    <Button
                                        onClick={() => void deleteApiKey(provider.id)}
                                        className="px-2 py-1.5 rounded border border-border bg-surface-hover/70 text-text-secondary hover:border-border-focus hover:bg-surface-hover hover:text-text-primary transition-colors duration-150"
                                        aria-label={`${provider.displayName} のキーを削除`}
                                    >
                                        <Trash2 size={14} />
                                    </Button>
                                )}
                                {!provider.builtin && (
                                    <Button
                                        onClick={() => void removeCustomProvider(provider.id)}
                                        className="px-2 py-1.5 rounded border border-border bg-surface-hover/70 text-text-secondary hover:border-danger/40 hover:text-score-low transition-colors duration-150"
                                        aria-label={`${provider.displayName} を削除`}
                                        title="プロバイダを削除"
                                    >
                                        <X size={14} />
                                    </Button>
                                )}
                            </div>
                        </div>
                    );
                })}

                <div className="card p-4 accent-bar-ice md:col-span-2 space-y-3">
                    <div className="flex items-center justify-between">
                        <span className="text-[13px] font-medium text-text-primary">カスタムプロバイダを追加</span>
                        <Button
                            type="button"
                            onClick={() => setShowAddForm((v) => !v)}
                            className="flex items-center gap-1 text-[12px] text-amber hover:text-amber-hover"
                        >
                            <Plus size={14} />
                            {showAddForm ? '閉じる' : '追加'}
                        </Button>
                    </div>
                    {showAddForm && (
                        <div className="space-y-2">
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                <input
                                    value={newName}
                                    onChange={(e) => setNewName(e.target.value)}
                                    placeholder="表示名（例: DeepSeek）"
                                    className="bg-bg border border-border rounded px-3 py-1.5 text-[13px] text-text-primary placeholder-text-tertiary focus:outline-none focus:border-amber/40"
                                />
                                <select
                                    value={newKind}
                                    onChange={(e) => setNewKind(e.target.value as ProviderKind)}
                                    className="bg-bg border border-border rounded px-3 py-1.5 text-[13px] text-text-primary focus:outline-none focus:border-amber/40"
                                >
                                    <option value="openai_compatible">OpenAI 互換</option>
                                    <option value="anthropic">Anthropic</option>
                                </select>
                            </div>
                            {newKind === 'openai_compatible' && (
                                <input
                                    value={newBaseUrl}
                                    onChange={(e) => setNewBaseUrl(e.target.value)}
                                    placeholder="base URL（例: https://api.example.com/v1）"
                                    className="w-full bg-bg border border-border rounded px-3 py-1.5 text-[13px] text-text-primary placeholder-text-tertiary focus:outline-none focus:border-amber/40"
                                />
                            )}
                            {addError && (
                                <p className="text-[11px] text-score-low">{addError}</p>
                            )}
                            <Button
                                type="button"
                                onClick={() => void handleAdd()}
                                disabled={adding || !newName.trim()}
                                className="px-3 py-1.5 bg-amber text-bg rounded text-[12px] font-medium disabled:opacity-30"
                            >
                                {adding ? '追加中…' : '登録'}
                            </Button>
                        </div>
                    )}
                </div>

                <LMStudioCard className="md:col-span-2" />
            </div>
        </section>
    );
}

function LMStudioCard({ className = '' }: { className?: string }) {
    const refreshModels = useSettingsStore((s) => s.refreshModels);
    const [baseUrlDraft, setBaseUrlDraft] = useState('http://127.0.0.1:1234/v1');
    const [tokenDraft, setTokenDraft] = useState('');
    const [configured, setConfigured] = useState(false);
    const [tokenConfigured, setTokenConfigured] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const config = await fetchLMStudioConfig();
            setConfigured(config.configured);
            setTokenConfigured(config.apiTokenConfigured);
            setBaseUrlDraft(config.baseUrl || 'http://127.0.0.1:1234/v1');
        } catch (err) {
            setError(err instanceof Error ? err.message : 'LM Studio 設定の読み込みに失敗しました');
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        void load();
    }, [load]);

    const handleSave = async () => {
        if (!baseUrlDraft.trim()) return;
        setIsSaving(true);
        setError(null);
        try {
            const next = await saveLMStudioConfig(baseUrlDraft.trim(), tokenDraft);
            setConfigured(next.configured);
            setTokenConfigured(next.apiTokenConfigured);
            setBaseUrlDraft(next.baseUrl || 'http://127.0.0.1:1234/v1');
            setTokenDraft('');
            await refreshModels(true);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'LM Studio 設定の保存に失敗しました');
        } finally {
            setIsSaving(false);
        }
    };

    const handleDelete = async () => {
        setIsDeleting(true);
        setError(null);
        try {
            await deleteLMStudioConfig();
            setConfigured(false);
            setTokenConfigured(false);
            setTokenDraft('');
            setBaseUrlDraft('http://127.0.0.1:1234/v1');
            await refreshModels(true);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'LM Studio 設定の削除に失敗しました');
        } finally {
            setIsDeleting(false);
        }
    };

    return (
        <div className={`card p-4 space-y-4 transition-all duration-150 animate-fade-up accent-bar-ice ${className}`}>
            <div className="flex items-center justify-between gap-3">
                <p className="text-[13px] font-medium text-text-primary">LM Studio</p>
                <div className="flex items-center gap-3 text-[11px]">
                    <span className={configured ? 'text-score-high' : 'text-text-tertiary'}>
                        {configured ? 'URL 設定済み' : '未設定'}
                    </span>
                    <span className={tokenConfigured ? 'text-score-high' : 'text-text-tertiary'}>
                        {tokenConfigured ? 'Token 設定済み' : 'Token 省略'}
                    </span>
                </div>
            </div>

            <div className="space-y-2">
                <label className="text-[11px] font-medium text-text-secondary">Server URL</label>
                <input
                    value={baseUrlDraft}
                    onChange={(e) => setBaseUrlDraft(e.target.value)}
                    placeholder="http://127.0.0.1:1234/v1"
                    className="w-full bg-bg border border-border rounded px-3 py-2 text-[13px] text-text-primary placeholder-text-tertiary focus:outline-none focus:border-amber/40 transition-colors duration-150"
                />
            </div>

            <div className="space-y-2">
                <label className="text-[11px] font-medium text-text-secondary">API Token (optional)</label>
                <div className="flex gap-2">
                    <input
                        type="password"
                        value={tokenDraft}
                        onChange={(e) => setTokenDraft(e.target.value)}
                        placeholder={tokenConfigured ? '••••••••' : '未設定でも利用できます'}
                        className="flex-1 bg-bg border border-border rounded px-3 py-2 text-[13px] text-text-primary placeholder-text-tertiary focus:outline-none focus:border-amber/40 transition-colors duration-150"
                    />
                    <Button
                        onClick={() => void handleSave()}
                        disabled={!baseUrlDraft.trim() || isSaving || isLoading}
                        className="px-3 py-2 bg-amber text-bg rounded text-[12px] font-medium disabled:opacity-30 disabled:cursor-not-allowed hover:bg-amber-hover transition-colors duration-150"
                    >
                        {isSaving ? '保存中...' : '保存'}
                    </Button>
                    {configured && (
                        <Button
                            onClick={() => void handleDelete()}
                            disabled={isDeleting}
                            className="px-2 py-2 border border-border rounded text-text-tertiary hover:text-score-low hover:border-score-low/30 transition-colors duration-150 disabled:opacity-40"
                        >
                            <Trash2 size={14} />
                        </Button>
                    )}
                </div>
            </div>

            {error && (
                <div className="rounded-md border border-score-low/20 bg-score-low/8 p-3 text-[11px] text-score-low">
                    {error}
                </div>
            )}
        </div>
    );
}

function OpenRouterAdminSection() {
    const [draft, setDraft] = useState('');
    const [configured, setConfigured] = useState(false);
    const [remainingCredits, setRemainingCredits] = useState<number | null>(null);
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
                setRemainingCredits(
                    typeof creditState.remainingCredits === 'number'
                        ? creditState.remainingCredits
                        : null
                );
            } else {
                setRemainingCredits(null);
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
            setRemainingCredits(null);
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
            setRemainingCredits(
                typeof creditState.remainingCredits === 'number'
                    ? creditState.remainingCredits
                    : null
            );
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
                    <Button
                        onClick={() => void handleSave()}
                        disabled={!draft.trim() || isSaving}
                        className="px-3 py-1.5 bg-amber text-bg rounded text-[12px] font-medium disabled:opacity-30 disabled:cursor-not-allowed hover:bg-amber-hover transition-colors duration-150"
                    >
                        {isSaving ? '保存中...' : '保存'}
                    </Button>
                    {configured && (
                        <Button
                            onClick={() => void handleDelete()}
                            disabled={isRefreshing}
                            className="px-2 py-1.5 border border-border rounded text-text-tertiary hover:text-score-low hover:border-score-low/30 transition-colors duration-150 disabled:opacity-40"
                        >
                            <Trash2 size={14} />
                        </Button>
                    )}
                </div>

                <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-bg/70 px-3 py-3">
                    <div>
                        <p className="text-[10px] uppercase tracking-[0.16em] text-text-tertiary">Remaining Credits</p>
                        <p className="mt-1 data-display text-[20px] text-text-primary">
                            {isLoading
                                ? '...'
                                : typeof remainingCredits === 'number'
                                    ? remainingCredits.toFixed(4)
                                    : configured
                                        ? '---'
                                        : '未設定'}
                        </p>
                    </div>
                    <Button
                        onClick={() => void handleRefreshCredits()}
                        disabled={!configured || isRefreshing}
                        className="flex items-center gap-1.5 px-2.5 py-1.5 border border-border rounded text-[11px] text-text-secondary hover:text-amber hover:border-amber/30 transition-colors duration-150 disabled:opacity-40"
                    >
                        <RefreshCw size={12} className={isRefreshing ? 'animate-spin' : ''} />
                        更新
                    </Button>
                </div>

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
        registryProviders,
    } = useSettingsStore();

    const [judgeInput, setJudgeInput] = useState('');
    const hasCatalogModels = availableModels.length > 0;
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
                    <Button
                        onClick={() => refreshModels(true)}
                        className="flex items-center gap-1.5 px-2.5 py-1 border border-border rounded text-[11px] text-text-secondary hover:text-amber hover:border-amber/30 transition-colors duration-150"
                    >
                        <RefreshCw size={12} />
                        再取得
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {/* Subject Model */}
                <div className="card p-4 space-y-2 accent-bar-amber">
                    <label className="section-label text-[9px]">被験モデル</label>
                    {hasCatalogModels ? (
                        <ModelPicker
                            availableModels={availableModels}
                            registryProviders={registryProviders}
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
                            <p className="text-[11px] text-text-tertiary">利用可能なモデル一覧がないため、手動で入力してください。LM Studio は <code>lmstudio/&lt;model-id&gt;</code> 形式です。</p>
                            <input
                                value={freeTextSubject}
                                onChange={(e) => setFreeTextSubject(e.target.value)}
                                placeholder="例: gpt-4o / lmstudio/openai/gpt-oss-20b"
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
                            <p className="text-[11px] leading-5 text-text-tertiary">
                                Strict Mode の judge はすべて OpenRouter から実行されます。
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                                {strictPreset.judgeModels.map((judge) => (
                                    <span key={judge.id} className="flex items-center gap-1 rounded bg-surface-hover px-2 py-1 text-[11px] text-text-secondary">
                                        <span>{judge.label}</span>
                                        <span className="text-text-tertiary">· {providerDisplayName(judge.provider, registryProviders)}</span>
                                    </span>
                                ))}
                            </div>
                        </div>
                    ) : hasCatalogModels ? (
                        <div className="space-y-2">
                            <ModelPicker
                                availableModels={availableModels}
                                registryProviders={registryProviders}
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
                                            <Button
                                                key={id}
                                                onClick={() => toggleJudgeModel(id)}
                                                className="flex items-center gap-1 px-2 py-0.5 bg-amber-dim rounded text-[11px] text-amber hover:text-score-low transition-colors duration-150"
                                            >
                                                <span>{label}</span>
                                                <X size={10} />
                                            </Button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="space-y-1.5">
                            <p className="text-[11px] text-text-tertiary">利用可能なモデル一覧がないため、手動で入力してください。LM Studio は <code>lmstudio/&lt;model-id&gt;</code> 形式です。</p>
                            <div className="flex gap-2">
                                <input
                                    value={judgeInput}
                                    onChange={(e) => setJudgeInput(e.target.value)}
                                    onKeyDown={(e) => { if (e.key === 'Enter') { addFreeTextJudge(judgeInput); setJudgeInput(''); } }}
                                    placeholder="例: claude-3.5-sonnet / lmstudio/openai/gpt-oss-20b"
                                    className="flex-1 bg-bg border border-border rounded px-3 py-1.5 text-[13px] text-text-primary placeholder-text-tertiary focus:outline-none focus:border-amber/40 transition-colors duration-150"
                                />
                                <Button
                                    onClick={() => { addFreeTextJudge(judgeInput); setJudgeInput(''); }}
                                    className="px-2.5 py-1.5 bg-amber text-bg rounded hover:bg-amber-hover transition-colors duration-150"
                                >
                                    <Plus size={14} />
                                </Button>
                            </div>
                            {freeTextJudges.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 mt-1">
                                    {freeTextJudges.map((j) => (
                                        <span key={j} className="flex items-center gap-1 px-2 py-0.5 bg-amber-dim rounded text-[11px] text-amber">
                                            {j}
                                            <Button onClick={() => removeFreeTextJudge(j)} className="hover:text-score-low"><X size={10} /></Button>
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

/* ===================== HOLISTIC SECTION ===================== */
function HolisticSection() {
    const {
        runHolistic,
        setRunHolistic,
        availableModels,
        holisticJudgeModelIds,
        toggleHolisticJudgeModel,
        freeTextHolisticJudges,
        addFreeTextHolisticJudge,
        removeFreeTextHolisticJudge,
        registryProviders,
    } = useSettingsStore();
    const [holisticJudgeOpen, setHolisticJudgeOpen] = useState(false);
    const [holisticJudgeInput, setHolisticJudgeInput] = useState('');
    const hasCatalogModels = availableModels.length > 0;
    const holisticJudgeCount = holisticJudgeModelIds.length + freeTextHolisticJudges.length;
    const holisticJudgeLabel = holisticJudgeModelIds.length > 0
        ? `${holisticJudgeModelIds.length}件選択中`
        : '';

    return (
        <section className={`space-y-3 animate-fade-up stagger-5 relative ${holisticJudgeOpen ? 'z-50' : 'z-0'}`}>
            <h2 className="section-label">包括評価</h2>
            <button
                onClick={() => setRunHolistic(!runHolistic)}
                className="card p-5 w-full text-left cursor-pointer hover:border-border-focus transition-colors duration-150"
            >
                <div className="flex items-center justify-between gap-4">
                    <div>
                        <p className="text-[12px] font-medium text-text-primary mb-0.5">文体・言語運用の横断評価</p>
                        <p className="text-[12px] text-text-secondary">全タスク完了後、creativeタスクを除く出力をまとめてjudgeに渡し、文体・語の選択・読みやすさを評価します</p>
                    </div>
                    <div className={`relative shrink-0 inline-flex h-5 w-9 items-center rounded-full transition-colors duration-200 ${runHolistic ? 'bg-amber' : 'bg-border'}`}>
                        <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform duration-200 ${runHolistic ? 'translate-x-[18px]' : 'translate-x-0.5'}`} />
                    </div>
                </div>
            </button>

            {runHolistic && (
                <div className="card p-4 space-y-2 accent-bar-ice">
                    <label className="section-label text-[9px]">
                        包括評価モデル
                        <span className="ml-1.5 font-mono text-text-tertiary">
                            ({holisticJudgeCount || '通常と同じ'})
                        </span>
                    </label>
                    <p className="text-[11px] text-text-tertiary leading-5">
                        未選択時は通常の評価モデルと同じセットを使います。Strict Mode でもここは自由に選べます。
                    </p>
                    {hasCatalogModels ? (
                        <div className="space-y-2">
                            <ModelPicker
                                availableModels={availableModels}
                                registryProviders={registryProviders}
                                open={holisticJudgeOpen}
                                onOpenChange={setHolisticJudgeOpen}
                                placeholder="包括評価モデルを選択（任意）"
                                selectedLabel={holisticJudgeLabel}
                                onSelect={(id) => toggleHolisticJudgeModel(id)}
                                isSelected={(id) => holisticJudgeModelIds.includes(id)}
                                multi
                            />
                            {holisticJudgeModelIds.length > 0 && (
                                <div className="flex flex-wrap gap-1.5">
                                    {holisticJudgeModelIds.map((id) => {
                                        const model = availableModels.find((m) => m.id === id);
                                        const label = model?.name || id;
                                        return (
                                            <Button
                                                key={id}
                                                onClick={() => toggleHolisticJudgeModel(id)}
                                                className="flex items-center gap-1 px-2 py-0.5 bg-amber-dim rounded text-[11px] text-amber hover:text-score-low transition-colors duration-150"
                                            >
                                                <span>{label}</span>
                                                <X size={10} />
                                            </Button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="space-y-1.5">
                            <div className="flex gap-2">
                                <input
                                    value={holisticJudgeInput}
                                    onChange={(e) => setHolisticJudgeInput(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') {
                                            addFreeTextHolisticJudge(holisticJudgeInput);
                                            setHolisticJudgeInput('');
                                        }
                                    }}
                                    placeholder="例: claude-3.5-sonnet（任意）"
                                    className="flex-1 bg-bg border border-border rounded px-3 py-1.5 text-[13px] text-text-primary placeholder-text-tertiary focus:outline-none focus:border-amber/40 transition-colors duration-150"
                                />
                                <Button
                                    onClick={() => {
                                        addFreeTextHolisticJudge(holisticJudgeInput);
                                        setHolisticJudgeInput('');
                                    }}
                                    className="px-2.5 py-1.5 bg-amber text-bg rounded hover:bg-amber-hover transition-colors duration-150"
                                >
                                    <Plus size={14} />
                                </Button>
                            </div>
                            {freeTextHolisticJudges.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 mt-1">
                                    {freeTextHolisticJudges.map((j) => (
                                        <span key={j} className="flex items-center gap-1 px-2 py-0.5 bg-amber-dim rounded text-[11px] text-amber">
                                            {j}
                                            <Button onClick={() => removeFreeTextHolisticJudge(j)} className="hover:text-score-low"><X size={10} /></Button>
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </section>
    );
}

/* ===================== PARALLEL SECTION ===================== */
function ParallelSection() {
    const { subjectParallel, setSubjectParallel, judgeParallel, setJudgeParallel } = useSettingsStore();

    return (
        <section className="space-y-3 animate-fade-up stagger-5">
            <h2 className="section-label">並列実行設定</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <button
                    onClick={() => setSubjectParallel(!subjectParallel)}
                    className="card p-5 w-full text-left cursor-pointer hover:border-border-focus transition-colors duration-150"
                >
                    <div className="flex items-center justify-between gap-4">
                        <div>
                            <p className="text-[12px] font-medium text-text-primary mb-0.5">被検モデル並列実行</p>
                            <p className="text-[12px] text-text-secondary">OFF にするとタスクを1つずつ順次実行します（ローカルLLM向け）</p>
                        </div>
                        <div className={`relative shrink-0 inline-flex h-5 w-9 items-center rounded-full transition-colors duration-200 ${subjectParallel ? 'bg-amber' : 'bg-border'}`}>
                            <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform duration-200 ${subjectParallel ? 'translate-x-[18px]' : 'translate-x-0.5'}`} />
                        </div>
                    </div>
                </button>
                <button
                    onClick={() => setJudgeParallel(!judgeParallel)}
                    className="card p-5 w-full text-left cursor-pointer hover:border-border-focus transition-colors duration-150"
                >
                    <div className="flex items-center justify-between gap-4">
                        <div>
                            <p className="text-[12px] font-medium text-text-primary mb-0.5">評価モデル並列実行</p>
                            <p className="text-[12px] text-text-secondary">OFF にすると judge も1モデル・1回ずつ順次評価します</p>
                        </div>
                        <div className={`relative shrink-0 inline-flex h-5 w-9 items-center rounded-full transition-colors duration-200 ${judgeParallel ? 'bg-amber' : 'bg-border'}`}>
                            <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform duration-200 ${judgeParallel ? 'translate-x-[18px]' : 'translate-x-0.5'}`} />
                        </div>
                    </div>
                </button>
            </div>
        </section>
    );
}

function EvalParamsSection() {
    const {
        evaluationMode,
        strictPreset,
        evalParams,
        setJudgeRunCount,
        setSubjectRunCount,
        setSubjectTemperature,
    } = useSettingsStore();
    const isStrict = evaluationMode === 'strict' && !!strictPreset;

    return (
        <section className="space-y-3 animate-fade-up stagger-5">
            <h2 className="section-label">パラメータ</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-2">
                <div className="card p-4 space-y-2 accent-bar-amber">
                    <label className="text-[11px] font-medium text-text-secondary">被験回数</label>
                    <div className="flex items-center gap-3">
                        <input
                            type="range" min={1} max={5}
                            value={evalParams.subjectRunCount}
                            onChange={(e) => setSubjectRunCount(Number(e.target.value))}
                            className="flex-1 accent-amber h-1"
                        />
                        <span className="data-display text-lg text-text-primary w-6 text-center">
                            {evalParams.subjectRunCount}
                        </span>
                    </div>
                    <p className="text-[11px] text-text-tertiary">
                        被験モデルの実行回数（1-5）。複数回は1回の judge 入力に束ねます
                    </p>
                </div>

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
const TOOL_MODE_OPTIONS: { value: ToolMode; label: string }[] = [
    { value: 'auto', label: 'auto' },
    { value: 'native', label: 'native' },
    { value: 'text', label: 'text' },
];

function TaskSelectionSection() {
    const { evaluationMode, strictPreset, tasks, tasksLoading, selectedTaskIds, taskToolModeOverrides, toggleTask, selectAllTasks, deselectAllTasks, setTaskToolMode } = useSettingsStore();
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
                    <Button
                        onClick={selectAllTasks}
                        disabled={isStrict}
                        className="px-2.5 py-1 rounded text-[11px] transition-colors duration-150 text-amber border border-amber/30 hover:bg-amber-dim"
                    >
                        すべて選択
                    </Button>
                    <Button
                        onClick={deselectAllTasks}
                        disabled={isStrict}
                        className="px-2.5 py-1 rounded text-[11px] transition-colors duration-150 text-amber border border-amber/30 hover:bg-amber-dim"
                    >
                        すべて解除
                    </Button>
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
                            <Button
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
                                        {task.toolMode && (
                                            <div
                                                className={`ml-auto flex items-center gap-0.5 rounded-full border border-border bg-surface-hover p-0.5 transition-opacity duration-150 ${isSelected ? 'opacity-100' : 'opacity-40'}`}
                                                onClick={(e) => e.stopPropagation()}
                                            >
                                                {TOOL_MODE_OPTIONS.map((opt) => {
                                                    const effective = taskToolModeOverrides[task.id] ?? task.toolMode;
                                                    const active = effective === opt.value;
                                                    return (
                                                        <Button
                                                            key={opt.value}
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                setTaskToolMode(task.id, opt.value);
                                                            }}
                                                            className={`px-2 py-0.5 rounded-full text-[10px] font-mono transition-colors duration-100 ${active ? 'bg-amber text-bg' : 'text-text-tertiary hover:text-text-secondary'}`}
                                                        >
                                                            {opt.label}
                                                        </Button>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </div>
                                    <p className="text-[12px] text-text-tertiary truncate">{task.promptPreview}</p>
                                </div>
                            </Button>
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
