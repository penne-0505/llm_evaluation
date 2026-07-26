import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { fetchOpenRouterEndpoints } from '../api/client';
import type { OpenRouterHostEndpoint } from '../types';
import Button from './Button';

function formatMetric(value: number | null, digits = 2): string {
    if (value == null || Number.isNaN(value)) return '—';
    if (Math.abs(value) >= 100) return value.toFixed(0);
    return value.toFixed(digits);
}

type HostPickerProps = {
    modelId: string | null;
    /** OpenRouter 以外や未選択でも枠は出し、disabled にする */
    isOpenRouter: boolean;
    selectedHostSlug: string | null;
    onSelectHost: (slug: string | null) => void;
    label?: string;
};

/**
 * OpenRouter preferred-host picker.
 * intent: DEC-003 — always visible; enabled only when endpoints >= 2
 * intent: DEC-004 — show tps / $/M metrics per host
 */
export function HostPicker({
    modelId,
    isOpenRouter,
    selectedHostSlug,
    onSelectHost,
    label = '優先ホスト',
}: HostPickerProps) {
    const [open, setOpen] = useState(false);
    const [errorByModel, setErrorByModel] = useState<Record<string, string>>({});
    const [endpointsByModel, setEndpointsByModel] = useState<
        Record<string, OpenRouterHostEndpoint[]>
    >({});
    const rootRef = useRef<HTMLDivElement | null>(null);
    const fetchKey = isOpenRouter && modelId ? modelId : null;

    useEffect(() => {
        if (!fetchKey) return;
        let cancelled = false;
        void fetchOpenRouterEndpoints(fetchKey)
            .then((res) => {
                if (cancelled) return;
                setEndpointsByModel((prev) => ({ ...prev, [fetchKey]: res.endpoints }));
                setErrorByModel((prev) => {
                    if (!(fetchKey in prev)) return prev;
                    const next = { ...prev };
                    delete next[fetchKey];
                    return next;
                });
            })
            .catch((err: unknown) => {
                if (cancelled) return;
                setEndpointsByModel((prev) => ({ ...prev, [fetchKey]: [] }));
                setErrorByModel((prev) => ({
                    ...prev,
                    [fetchKey]: err instanceof Error ? err.message : 'ホスト一覧の取得に失敗しました',
                }));
            });
        return () => {
            cancelled = true;
        };
    }, [fetchKey]);

    useEffect(() => {
        const handlePointerDown = (event: MouseEvent) => {
            if (!rootRef.current?.contains(event.target as Node)) {
                setOpen(false);
            }
        };
        document.addEventListener('mousedown', handlePointerDown);
        return () => document.removeEventListener('mousedown', handlePointerDown);
    }, []);

    const endpoints = useMemo(
        () => (fetchKey ? (endpointsByModel[fetchKey] ?? []) : []),
        [endpointsByModel, fetchKey],
    );
    const error = fetchKey ? (errorByModel[fetchKey] ?? null) : null;
    const showLoading = Boolean(fetchKey) && !(fetchKey && fetchKey in endpointsByModel);
    const enabled = Boolean(fetchKey) && endpoints.length >= 2;

    const selectedLabel = useMemo(() => {
        if (!selectedHostSlug) return '自動（優先なし）';
        const match = endpoints.find((ep) => ep.slug === selectedHostSlug);
        return match?.providerName || selectedHostSlug;
    }, [endpoints, selectedHostSlug]);

    const handleSelect = useCallback(
        (slug: string | null) => {
            onSelectHost(slug);
            setOpen(false);
        },
        [onSelectHost],
    );

    return (
        <div ref={rootRef} className="relative space-y-1.5">
            <label className="section-label text-[9px]">{label}</label>
            <div
                className={`w-full flex items-center gap-2 bg-bg border rounded px-3 py-2 transition-colors duration-150 ${
                    !enabled
                        ? 'opacity-50 cursor-not-allowed border-border'
                        : open
                            ? 'border-amber/40'
                            : 'border-border hover:border-border-focus'
                }`}
            >
                <button
                    type="button"
                    disabled={!enabled}
                    onClick={() => enabled && setOpen(!open)}
                    className="flex-1 text-left text-[13px] text-text-primary disabled:cursor-not-allowed focus:outline-none"
                >
                    {showLoading ? 'ホスト一覧を取得中…' : selectedLabel}
                </button>
                <Button
                    type="button"
                    disabled={!enabled}
                    onClick={() => enabled && setOpen(!open)}
                    className="shrink-0 text-text-tertiary hover:text-text-primary transition-colors duration-150 disabled:cursor-not-allowed"
                    aria-label={open ? 'ホスト一覧を閉じる' : 'ホスト一覧を開く'}
                >
                    <ChevronDown
                        size={14}
                        className={`transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
                    />
                </Button>
            </div>
            {!isOpenRouter && (
                <p className="text-[11px] text-text-tertiary">OpenRouter モデル選択時に有効になります</p>
            )}
            {isOpenRouter && Boolean(modelId) && !showLoading && !error && endpoints.length < 2 && (
                <p className="text-[11px] text-text-tertiary">
                    ホストが複数あるときだけ選択できます（現在 {endpoints.length}）
                </p>
            )}
            {error && <p className="text-[11px] text-score-low">{error}</p>}
            {open && enabled && (
                <div className="absolute z-30 mt-1 w-full bg-surface border border-border rounded-md shadow-xl max-h-64 overflow-y-auto">
                    <Button
                        type="button"
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => handleSelect(null)}
                        className={`w-full text-left px-3 py-2 text-[13px] hover:bg-surface-hover transition-colors ${
                            !selectedHostSlug ? 'text-amber' : 'text-text-primary'
                        }`}
                    >
                        自動（優先なし）
                    </Button>
                    {endpoints.map((ep) => {
                        const selected = selectedHostSlug === ep.slug;
                        return (
                            <Button
                                key={ep.slug}
                                type="button"
                                onMouseDown={(e) => e.preventDefault()}
                                onClick={() => handleSelect(ep.slug)}
                                className={`w-full text-left px-3 py-2.5 hover:bg-surface-hover transition-colors border-t border-border/50 ${
                                    selected ? 'text-amber' : 'text-text-primary'
                                }`}
                            >
                                <div className="flex items-baseline justify-between gap-2">
                                    <span className="text-[13px] font-medium truncate">
                                        {ep.providerName}
                                    </span>
                                    <span className="shrink-0 text-[10px] text-text-tertiary font-mono">
                                        {ep.slug}
                                    </span>
                                </div>
                                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] font-mono text-text-tertiary">
                                    <span>tps {formatMetric(ep.tpsP50, 1)}</span>
                                    <span>in/M {formatMetric(ep.inputPerMillion)}</span>
                                    <span>out/M {formatMetric(ep.outputPerMillion)}</span>
                                    <span>cache/M {formatMetric(ep.cacheReadPerMillion)}</span>
                                </div>
                            </Button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
