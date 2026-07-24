import assert from 'node:assert/strict';
import test from 'node:test';
import {
    etaStatusLabel,
    formatDurationMs,
    formatEtaDisplay,
    formatTaskTimingBreakdown,
} from './taskTiming.ts';

test('formatDurationMs formats as m s', () => {
    assert.equal(formatDurationMs(450), '0m 00s');
    assert.equal(formatDurationMs(2500), '0m 02s');
    assert.equal(formatDurationMs(125000), '2m 05s');
    assert.equal(formatDurationMs(undefined), 'N/A');
});

test('formatEtaDisplay labels measured vs history vs step fallback vs unavailable', () => {
    assert.deepStrictEqual(formatEtaDisplay(12000, 'measured'), {
        value: '0m 12s',
        label: '推定（実測ペース）',
    });
    assert.deepStrictEqual(formatEtaDisplay(45000, 'history_blend'), {
        value: '0m 45s',
        label: '推定（実測+履歴）',
    });
    assert.deepStrictEqual(formatEtaDisplay(30000, 'history'), {
        value: '0m 30s',
        label: '推定（履歴）',
    });
    assert.deepStrictEqual(formatEtaDisplay(45000, 'step_fallback'), {
        value: '0m 45s',
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
        '被検 0m 01s · judge 0m 03s',
    );
    assert.equal(formatTaskTimingBreakdown(undefined), null);
});
