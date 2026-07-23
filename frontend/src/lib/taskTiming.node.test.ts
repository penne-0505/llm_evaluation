import assert from 'node:assert/strict';
import test from 'node:test';
import {
    etaStatusLabel,
    formatDurationMs,
    formatEtaDisplay,
    formatTaskTimingBreakdown,
} from './taskTiming.ts';

test('formatDurationMs formats ms and mm:ss', () => {
    assert.equal(formatDurationMs(450), '450ms');
    assert.equal(formatDurationMs(2500), '2s');
    assert.equal(formatDurationMs(125000), '2:05');
    assert.equal(formatDurationMs(undefined), 'N/A');
});

test('formatEtaDisplay labels measured vs step fallback vs unavailable', () => {
    assert.deepStrictEqual(formatEtaDisplay(12000, 'measured'), {
        value: '12s',
        label: '推定（実測平均）',
    });
    assert.deepStrictEqual(formatEtaDisplay(45000, 'step_fallback'), {
        value: '45s',
        label: '推定（step ベース）',
    });
    assert.deepStrictEqual(formatEtaDisplay(null, 'unavailable'), {
        value: '—',
        label: '推定不可',
    });
    assert.equal(etaStatusLabel('unavailable'), '推定不可');
});

test('formatTaskTimingBreakdown renders subject/judge split', () => {
    assert.equal(
        formatTaskTimingBreakdown({ subjectDurationMs: 1200, judgeDurationMs: 3400 }),
        '被検 1s · judge 3s',
    );
    assert.equal(formatTaskTimingBreakdown(undefined), null);
});
