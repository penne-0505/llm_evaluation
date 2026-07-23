import type { EtaStatus, TaskTiming } from '../types';

export function formatDurationMs(ms: number | null | undefined): string {
    if (ms == null || !Number.isFinite(ms) || ms < 0) {
        return 'N/A';
    }
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}m ${seconds.toString().padStart(2, '0')}s`;
}

/** intent: DEC-003 (Core/task-duration-eta) — never present a bare number as a certainty. */
export function etaStatusLabel(status: EtaStatus | undefined): string {
    switch (status) {
        case 'measured':
            return '推定（実測平均）';
        case 'step_fallback':
            return '推定（step ベース）';
        case 'unavailable':
        default:
            return '推定不可';
    }
}

export function formatEtaDisplay(
    etaMs: number | null | undefined,
    etaStatus: EtaStatus | undefined,
): { value: string; label: string } {
    const label = etaStatusLabel(etaStatus);
    if (etaStatus === 'unavailable' || etaMs == null) {
        return { value: '—', label };
    }
    return { value: formatDurationMs(etaMs), label };
}

export function formatTaskTimingBreakdown(timing: TaskTiming | undefined): string | null {
    if (!timing) {
        return null;
    }
    return `被検 ${formatDurationMs(timing.subjectDurationMs)} · judge ${formatDurationMs(timing.judgeDurationMs)}`;
}
