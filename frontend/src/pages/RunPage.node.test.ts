import test from 'node:test';
import assert from 'node:assert/strict';

import { getSelectedTasksInCanonicalOrder } from './runPageTaskSelection.ts';
import type { Task } from '../types/index.ts';

test('AC-003 canonicalizes selected task IDs in the rendered task order', () => {
    const tasks: Task[] = [
        { id: 'task-a', type: 'fact', promptPreview: 'A' },
        { id: 'task-b', type: 'creative', promptPreview: 'B' },
        { id: 'task-c', type: 'speculative', promptPreview: 'C' },
    ];

    const selectedTasks = getSelectedTasksInCanonicalOrder(tasks, [
        'task-c',
        'missing-task',
        'task-a',
        'task-c',
    ]);

    assert.deepEqual(
        selectedTasks.map((task) => task.id),
        ['task-a', 'task-c'],
    );
});
