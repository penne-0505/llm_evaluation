import test from 'node:test';
import assert from 'node:assert/strict';

import { RunConnectionRegistry } from './runCoordinator.ts';
import type { SSEConnection } from './sse.ts';

function fakeConnection(): {
    connection: SSEConnection;
    abortCount: () => number;
    finish: () => void;
} {
    let aborts = 0;
    let finish: () => void = () => {};
    const done = new Promise<void>((resolve) => {
        finish = resolve;
    });
    return {
        connection: {
            abort: () => {
                aborts += 1;
            },
            done,
        },
        abortCount: () => aborts,
        finish,
    };
}

test('INV-004 keeps active connections until terminal completion or app-shell teardown', async () => {
    const registry = new RunConnectionRegistry();
    const first = fakeConnection();
    const second = fakeConnection();

    registry.track('job-1', first.connection);
    registry.track('job-2', second.connection);

    assert.equal(registry.size(), 2);
    assert.equal(first.abortCount(), 0);
    assert.equal(second.abortCount(), 0);

    first.finish();
    await first.connection.done;
    await Promise.resolve();

    assert.equal(registry.has('job-1'), false);
    assert.equal(registry.has('job-2'), true);
    assert.equal(second.abortCount(), 0);

    registry.abortAll();
    assert.equal(registry.size(), 0);
    assert.equal(second.abortCount(), 1);
});

test('tracking a replacement connection aborts only the superseded stream', () => {
    const registry = new RunConnectionRegistry();
    const previous = fakeConnection();
    const replacement = fakeConnection();

    registry.track('job-1', previous.connection);
    registry.track('job-1', replacement.connection);

    assert.equal(previous.abortCount(), 1);
    assert.equal(replacement.abortCount(), 0);
    assert.equal(registry.size(), 1);
});
