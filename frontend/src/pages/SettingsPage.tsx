import { useState } from 'react';
import { useSettingsStore } from '../store/settingsStore';
import type { Provider } from '../types';
import { PROVIDER_LABELS } from '../types';
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

const PROVIDERS: Provider[] = ['openai', 'anthropic', 'gemini', 'openrouter'];

const TASK_TYPE_STYLE: Record<string, string> = {
    fact: 'bg-amber-dim text-amber',
    creative: 'bg-score-mid/10 text-score-mid',
    speculative: 'bg-ice-dim text-ice',
};

export default function SettingsPage() {
    return (
        <div className="space-y-10 animate-fade-up">
            {/* Hero - Asymmetric */}
            <div className="hero-glow relative flex items-end justify-between py-2">
                <div className="relative z-10">
                    <p className="section-label mb-2">Calibration</p>
                    <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">
                        Settings
                    </h1>
                    <p className="text-text-secondary mt-1 text-[13px]">
                        Configure API keys, models, parameters, and tasks
                    </p>
                </div>
            </div>

            <ApiKeySection />
            <ModelSelectionSection />
            <EvalParamsSection />
            <TaskSelectionSection />
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
                <h2 className="section-label">API Keys</h2>
                <span className="text-[11px] text-text-tertiary">
                    {connectedCount}/{PROVIDERS.length} connected
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
                                            Connected
                                        </span>
                                    ) : (
                                        <span className="flex items-center gap-1 text-[11px] text-score-low">
                                            <span className="w-1.5 h-1.5 rounded-full bg-score-low inline-block" />
                                            Error
                                        </span>
                                    )
                                ) : (
                                    <span className="flex items-center gap-1 text-[11px] text-text-tertiary">
                                        <span className="w-1.5 h-1.5 rounded-full bg-text-tertiary inline-block" />
                                        Not set
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
                                    placeholder={hasKey ? '••••••••' : 'Enter API key...'}
                                    className="flex-1 bg-bg border border-border rounded px-3 py-1.5 text-[13px] text-text-primary placeholder-text-tertiary focus:outline-none focus:border-amber/40 transition-colors duration-150"
                                />
                                <button
                                    onClick={() => handleSave(provider)}
                                    disabled={!draft.trim()}
                                    className="px-3 py-1.5 bg-amber text-bg rounded text-[12px] font-medium disabled:opacity-30 disabled:cursor-not-allowed hover:bg-amber-hover transition-colors duration-150"
                                >
                                    Save
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

/* ===================== MODEL SELECTION SECTION ===================== */
function ModelSelectionSection() {
    const {
        apiKeys,
        availableModels,
        modelsLastUpdated,
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

    const judgeCount = judgeModelIds.length + freeTextJudges.length;
    const showError = judgeCount < 1;
    const showWarning = judgeCount >= 1 && judgeCount < 3;

    return (
        <section className="space-y-3 animate-fade-up stagger-3">
            <div className="flex items-center justify-between">
                <h2 className="section-label">Models</h2>
                <div className="flex items-center gap-3">
                    {modelsLastUpdated && (
                        <span className="text-[11px] text-text-tertiary">
                            Updated {formatDistanceToNow(new Date(modelsLastUpdated), { addSuffix: true })}
                        </span>
                    )}
                    <button
                        onClick={() => refreshModels(true)}
                        className="flex items-center gap-1.5 px-2.5 py-1 border border-border rounded text-[11px] text-text-secondary hover:text-amber hover:border-amber/30 transition-colors duration-150"
                    >
                        <RefreshCw size={12} />
                        Refresh
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {/* Subject Model */}
                <div className="card p-4 space-y-2 accent-bar-amber">
                    <label className="section-label text-[9px]">Subject Model</label>
                    {hasAnyKey ? (
                        <div className="relative">
                            <button
                                onClick={() => setSubjectOpen(!subjectOpen)}
                                className="w-full flex items-center justify-between bg-bg border border-border rounded px-3 py-2 text-[13px] text-text-primary hover:border-border-focus transition-colors duration-150"
                            >
                                <span>{subjectModelId ? availableModels.find((m) => m.id === subjectModelId)?.name || subjectModelId : 'Select a model...'}</span>
                                <ChevronDown size={14} className={`text-text-tertiary transition-transform duration-150 ${subjectOpen ? 'rotate-180' : ''}`} />
                            </button>
                            {subjectOpen && (
                                <div className="absolute z-20 mt-1 w-full bg-surface border border-border rounded-md shadow-xl max-h-56 overflow-y-auto">
                                    {availableModels.map((m) => (
                                        <button
                                            key={m.id}
                                            onClick={() => { setSubjectModel(m.id); setSubjectOpen(false); }}
                                            className={`w-full text-left px-3 py-2 text-[13px] hover:bg-surface-hover transition-colors flex items-center justify-between ${subjectModelId === m.id ? 'text-amber' : 'text-text-primary'}`}
                                        >
                                            <span>{m.name}</span>
                                            <span className="text-[11px] text-text-tertiary">{PROVIDER_LABELS[m.provider]}</span>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="space-y-1.5">
                            <p className="text-[11px] text-text-tertiary">No API keys configured. Enter manually:</p>
                            <input
                                value={freeTextSubject}
                                onChange={(e) => setFreeTextSubject(e.target.value)}
                                placeholder="e.g. gpt-4o"
                                className="w-full bg-bg border border-border rounded px-3 py-2 text-[13px] text-text-primary placeholder-text-tertiary focus:outline-none focus:border-amber/40 transition-colors duration-150"
                            />
                        </div>
                    )}
                </div>

                {/* Judge Models */}
                <div className="card p-4 space-y-2 accent-bar-ice">
                    <label className="section-label text-[9px]">
                        Judge Models
                        <span className={`ml-1.5 font-mono ${showError ? 'text-score-low' : showWarning ? 'text-score-mid' : 'text-score-high'}`}>
                            ({judgeCount})
                        </span>
                    </label>

                    {showError && (
                        <div className="flex items-center gap-1.5 p-2 rounded bg-score-low/8 text-[11px] text-score-low">
                            <AlertCircle size={12} />
                            Select at least 1 judge model
                        </div>
                    )}
                    {showWarning && (
                        <div className="flex items-center gap-1.5 p-2 rounded bg-score-mid/8 text-[11px] text-score-mid">
                            <AlertTriangle size={12} />
                            Recommended: at least 3 judges
                        </div>
                    )}

                    {hasAnyKey ? (
                        <div className="space-y-1 max-h-44 overflow-y-auto">
                            {availableModels.map((m) => (
                                <label
                                    key={m.id}
                                    className={`flex items-center gap-2.5 px-3 py-2 rounded text-[13px] cursor-pointer transition-colors duration-150 ${judgeModelIds.includes(m.id)
                                        ? 'bg-amber-dim text-text-primary'
                                        : 'text-text-secondary hover:bg-surface-hover'
                                        }`}
                                >
                                    <input
                                        type="checkbox"
                                        checked={judgeModelIds.includes(m.id)}
                                        onChange={() => toggleJudgeModel(m.id)}
                                        className="sr-only"
                                    />
                                    <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${judgeModelIds.includes(m.id) ? 'bg-amber border-amber' : 'border-border-focus'}`}>
                                        {judgeModelIds.includes(m.id) && <Check size={9} className="text-bg" />}
                                    </div>
                                    <span className="flex-1">{m.name}</span>
                                    <span className="text-[11px] text-text-tertiary">{PROVIDER_LABELS[m.provider]}</span>
                                </label>
                            ))}
                        </div>
                    ) : (
                        <div className="space-y-1.5">
                            <p className="text-[11px] text-text-tertiary">No API keys configured. Enter manually:</p>
                            <div className="flex gap-2">
                                <input
                                    value={judgeInput}
                                    onChange={(e) => setJudgeInput(e.target.value)}
                                    onKeyDown={(e) => { if (e.key === 'Enter') { addFreeTextJudge(judgeInput); setJudgeInput(''); } }}
                                    placeholder="e.g. claude-3.5-sonnet"
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
    const { evalParams, setJudgeRunCount, setSubjectTemperature } = useSettingsStore();

    return (
        <section className="space-y-3 animate-fade-up stagger-5">
            <h2 className="section-label">Parameters</h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                <div className="card p-4 space-y-2 accent-bar-amber">
                    <label className="text-[11px] font-medium text-text-secondary">Judge Run Count</label>
                    <div className="flex items-center gap-3">
                        <input
                            type="range" min={1} max={5}
                            value={evalParams.judgeRunCount}
                            onChange={(e) => setJudgeRunCount(Number(e.target.value))}
                            className="flex-1 accent-amber h-1"
                        />
                        <span className="data-display text-lg text-text-primary w-6 text-center">
                            {evalParams.judgeRunCount}
                        </span>
                    </div>
                    <p className="text-[11px] text-text-tertiary">Evaluations per judge (1-5)</p>
                </div>

                <div className="card p-4 space-y-2 accent-bar-amber">
                    <label className="text-[11px] font-medium text-text-secondary">Subject Temperature</label>
                    <div className="flex items-center gap-3">
                        <input
                            type="range" min={0} max={100}
                            value={evalParams.subjectTemperature * 100}
                            onChange={(e) => setSubjectTemperature(Number(e.target.value) / 100)}
                            className="flex-1 accent-amber h-1"
                        />
                        <span className="data-display text-lg text-text-primary w-10 text-center">
                            {evalParams.subjectTemperature.toFixed(2)}
                        </span>
                    </div>
                    <p className="text-[11px] text-text-tertiary">Creativity (0.0-1.0)</p>
                </div>

                <div className="card p-4 space-y-2 opacity-40">
                    <label className="text-[11px] font-medium text-text-secondary">Judge Temperature</label>
                    <div className="flex items-center gap-3">
                        <div className="flex-1 h-1 bg-border rounded-full" />
                        <span className="data-display text-lg text-text-tertiary w-10 text-center">0.00</span>
                    </div>
                    <p className="text-[11px] text-text-tertiary">Fixed at 0.0 for deterministic evaluation</p>
                </div>
            </div>
        </section>
    );
}

/* ===================== TASK SELECTION SECTION ===================== */
function TaskSelectionSection() {
    const { tasks, tasksLoading, selectedTaskIds, toggleTask, selectAllTasks, deselectAllTasks } = useSettingsStore();

    return (
        <section className="space-y-3 animate-fade-up stagger-7">
            <div className="flex items-center justify-between">
                <h2 className="section-label">
                    Tasks
                    <span className="ml-2 font-mono text-text-tertiary text-[10px]">
                        {selectedTaskIds.length}/{tasks.length}
                    </span>
                </h2>
                <div className="flex gap-1.5">
                    <button
                        onClick={selectAllTasks}
                        className="px-2.5 py-1 rounded text-[11px] text-amber bg-amber-dim hover:bg-amber/15 transition-colors duration-150"
                    >
                        Select All
                    </button>
                    <button
                        onClick={deselectAllTasks}
                        className="px-2.5 py-1 rounded text-[11px] text-text-secondary border border-border hover:border-border-focus transition-colors duration-150"
                    >
                        Deselect All
                    </button>
                </div>
            </div>

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
                                            {task.type}
                                        </span>
                                    </div>
                                    <p className="text-[12px] text-text-tertiary truncate">{task.prompt}</p>
                                </div>
                            </button>
                        );
                    })}
                </div>
            )}
        </section>
    );
}
