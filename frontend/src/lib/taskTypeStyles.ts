import type { TaskType } from '../types';

export const TASK_TYPE_STYLE: Record<TaskType, string> = {
    fact: 'bg-amber-dim text-amber',
    creative: 'bg-score-high/10 text-score-high',
    speculative: 'bg-ice-dim text-ice',
};

export const TASK_TYPE_LABELS: Record<TaskType, string> = {
    fact: '事実',
    creative: '創作',
    speculative: '推測',
};
