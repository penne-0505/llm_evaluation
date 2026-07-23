import type { Model, StrictModePreset, Task } from '../types';

function sortedValues(values: string[]): string[] {
    return [...values].sort((a, b) => a.localeCompare(b));
}

/** Segment after the last `/` — Strict judge match key (DEC-002). */
export function judgeModelLeafId(modelId: string): string {
    const text = String(modelId || '').trim();
    if (!text) return '';
    const idx = text.lastIndexOf('/');
    return idx >= 0 ? text.slice(idx + 1) : text;
}

export function judgeModelLeafIds(modelIds: string[]): string[] {
    return sortedValues(modelIds.map(judgeModelLeafId));
}

export function strictJudgeLeafSet(preset: StrictModePreset): Set<string> {
    return new Set(preset.judgeModels.map((judge) => judgeModelLeafId(judge.id)));
}

export function filterModelsByStrictJudgeLeaves(
    models: Model[],
    preset: StrictModePreset,
): Model[] {
    const leaves = strictJudgeLeafSet(preset);
    return models.filter((model) => leaves.has(judgeModelLeafId(model.id)));
}

/**
 * Seed Strict judge IDs: keep current leaf matches when still in catalog,
 * else preferred preset id, else any catalog match for that leaf.
 */
export function resolveStrictJudgeSelection(
    preset: StrictModePreset,
    currentIds: string[],
    availableModels: Model[],
): string[] {
    const availableIds = new Set(availableModels.map((model) => model.id));
    const byLeaf = new Map<string, string[]>();
    for (const model of availableModels) {
        const leaf = judgeModelLeafId(model.id);
        const list = byLeaf.get(leaf) ?? [];
        list.push(model.id);
        byLeaf.set(leaf, list);
    }

    return preset.judgeModels.map((judge) => {
        const leaf = judgeModelLeafId(judge.id);
        const existing = currentIds.find(
            (id) => judgeModelLeafId(id) === leaf && availableIds.has(id),
        );
        if (existing) return existing;
        if (availableIds.has(judge.id)) return judge.id;
        const alts = byLeaf.get(leaf) ?? [];
        return alts[0] ?? judge.id;
    });
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

    const presetLeaves = judgeModelLeafIds(
        strictPreset.judgeModels.map((judge) => judge.id),
    );
    const activeLeaves = judgeModelLeafIds(judgeModelIds);
    if (presetLeaves.join('|') !== activeLeaves.join('|')) {
        issues.push('judge set（モデル leaf）が official strict preset と一致していません');
    }

    if (judgeRunCount !== strictPreset.judgeRuns) {
        issues.push(`judge runs は ${strictPreset.judgeRuns} 固定です`);
    }

    if (Number(subjectTemperature.toFixed(2)) !== Number(strictPreset.subjectTemperature.toFixed(2))) {
        issues.push(`Subject Temperature は ${strictPreset.subjectTemperature.toFixed(2)} 固定です`);
    }

    const availableLeaves = new Set(
        availableModels.map((model) => judgeModelLeafId(model.id)),
    );
    strictPreset.judgeModels.forEach((judge) => {
        const leaf = judgeModelLeafId(judge.id);
        if (!availableLeaves.has(leaf)) {
            issues.push(`${judge.label}（${leaf}）がモデル一覧に見つかりません`);
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
