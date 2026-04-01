export function buildResultDetailPath(runId: string): string {
    return `/results/${encodeURIComponent(runId)}`;
}

export function decodeResultRouteParam(runId: string | undefined): string {
    if (!runId) {
        return '';
    }
    try {
        return decodeURIComponent(runId);
    } catch {
        return runId;
    }
}
