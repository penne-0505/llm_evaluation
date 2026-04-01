import type { Model, StrictModePreset, Task } from '../types';

function sortedValues(values: string[]): string[] {
    return [...values].sort((a, b) => a.localeCompare(b));
}

export function getStrictModeIssues({
    strictPreset,
    availableModels,
    tasks,
    selectedTaskIds,
    judgeModelIds,
    judgeRunCount,
    subjectTemperature,
}: {
    strictPreset: StrictModePreset | null;
    availableModels: Model[];
    tasks: Task[];
    selectedTaskIds: string[];
    judgeModelIds: string[];
    judgeRunCount: number;
    subjectTemperature: number;
}): string[] {
    if (!strictPreset) {
        return ['Strict Mode preset を読み込めていません'];
    }

    const issues: string[] = [];
    const presetTaskIds = sortedValues(strictPreset.taskIds);
    const activeTaskIds = sortedValues(selectedTaskIds);
    if (presetTaskIds.join('|') !== activeTaskIds.join('|')) {
        issues.push('task set が official strict preset と一致していません');
    }

    const presetJudgeIds = sortedValues(strictPreset.judgeModels.map((judge) => judge.id));
    const activeJudgeIds = sortedValues(judgeModelIds);
    if (presetJudgeIds.join('|') !== activeJudgeIds.join('|')) {
        issues.push('judge set が official strict preset と一致していません');
    }

    if (judgeRunCount !== strictPreset.judgeRuns) {
        issues.push(`judge runs は ${strictPreset.judgeRuns} 固定です`);
    }

    if (Number(subjectTemperature.toFixed(2)) !== Number(strictPreset.subjectTemperature.toFixed(2))) {
        issues.push(`Subject Temperature は ${strictPreset.subjectTemperature.toFixed(2)} 固定です`);
    }

    const availableModelIds = new Set(availableModels.map((model) => model.id));
    strictPreset.judgeModels.forEach((judge) => {
        if (!availableModelIds.has(judge.id)) {
            issues.push(`${judge.label} がモデル一覧に見つかりません`);
        }
    });

    const availableTaskIds = new Set(tasks.map((task) => task.id));
    strictPreset.taskIds.forEach((taskId) => {
        if (!availableTaskIds.has(taskId)) {
            issues.push(`task ${taskId} が現在の bundled task set に見つかりません`);
        }
    });

    return issues;
}
