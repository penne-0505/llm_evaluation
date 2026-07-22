import type { Task } from '../types';

/**
 * Run request and screen display must use the task API's shared canonical order.
 */
export function getSelectedTasksInCanonicalOrder(tasks: Task[], selectedTaskIds: string[]): Task[] {
    const selectedTaskIdSet = new Set(selectedTaskIds);
    return tasks.filter((task) => selectedTaskIdSet.has(task.id));
}
