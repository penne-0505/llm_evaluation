import type { RunParams } from './client';
import type { SSEConnection } from './sse';

export interface StartRunJobRequest {
    params: RunParams;
    label: string;
    totalSteps: number;
}

export interface RunCoordinatorActions {
    startJob: (request: StartRunJobRequest) => string | null;
    requestCancel: (jobId: string) => void;
    dismissJob: (jobId: string) => void;
}

/** Active SSE connections owned by the app shell rather than a route view. */
export class RunConnectionRegistry {
    private readonly connections = new Map<string, SSEConnection>();

    track(jobId: string, connection: SSEConnection): void {
        const previous = this.connections.get(jobId);
        if (previous && previous !== connection) {
            previous.abort();
        }
        this.connections.set(jobId, connection);

        const release = () => {
            if (this.connections.get(jobId) === connection) {
                this.connections.delete(jobId);
            }
        };
        void connection.done.then(release, release);
    }

    abort(jobId: string): boolean {
        const connection = this.connections.get(jobId);
        if (!connection) return false;
        this.connections.delete(jobId);
        connection.abort();
        return true;
    }

    abortAll(): void {
        const connections = [...this.connections.values()];
        this.connections.clear();
        for (const connection of connections) {
            connection.abort();
        }
    }

    has(jobId: string): boolean {
        return this.connections.has(jobId);
    }

    size(): number {
        return this.connections.size;
    }
}
