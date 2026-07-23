import type { ExecutionPreset, ExecutionPresetConfig, Model, Task } from '../types';

export const EXECUTION_PRESET_SCHEMA_VERSION = 1 as const;

interface CurrentExecutionSettings {
    subjectModelId: string | null;
    judgeModelIds: string[];
    freeTextSubject: string;
    freeTextJudges: string[];
    holisticJudgeModelIds: string[];
    freeTextHolisticJudges: string[];
    tasks: Task[];
    selectedTaskIds: string[];
    runHolistic: boolean;
    excludeUnreliableJudges: boolean;
    judgeRunCount: number;
    subjectRunCount: number;
    subjectTemperature: number;
}

export interface ResolvedExecutionPreset {
    subjectModelId: string | null;
    judgeModelIds: string[];
    freeTextSubject: string;
    freeTextJudges: string[];
    holisticJudgeModelIds: string[];
    freeTextHolisticJudges: string[];
    selectedTaskIds: string[];
    runHolistic: boolean;
    excludeUnreliableJudges: boolean;
    judgeRunCount: number;
    subjectRunCount: number;
    subjectTemperature: number;
    missingModelIds: string[];
    missingTaskIds: string[];
}

export function createExecutionPreset(
    id: string,
    name: string,
    timestamp: string,
    config: ExecutionPresetConfig,
): ExecutionPreset {
    return {
        id,
        name,
        schemaVersion: EXECUTION_PRESET_SCHEMA_VERSION,
        createdAt: timestamp,
        updatedAt: timestamp,
        config,
    };
}

export function overwriteExecutionPresetConfig(
    preset: ExecutionPreset,
    config: ExecutionPresetConfig,
    timestamp: string,
): ExecutionPreset {
    return { ...preset, config, updatedAt: timestamp };
}

export function captureExecutionPresetConfig(
    settings: CurrentExecutionSettings,
): ExecutionPresetConfig {
    const selectedTaskIds = new Set(settings.selectedTaskIds);
    const freeTextSubject = settings.freeTextSubject.trim();
    return {
        subjectModel: settings.subjectModelId || freeTextSubject || null,
        judgeModels: settings.judgeModelIds.length > 0
            ? [...settings.judgeModelIds]
            : [...settings.freeTextJudges],
        // intent: DEC-004 (Core/holistic-judge-model) — 空配列 = judgeModels へ fallback
        holisticJudgeModels: settings.holisticJudgeModelIds.length > 0
            ? [...settings.holisticJudgeModelIds]
            : [...settings.freeTextHolisticJudges],
        taskSelections: Object.fromEntries(
            settings.tasks.map((task) => [task.id, selectedTaskIds.has(task.id)]),
        ),
        runHolistic: settings.runHolistic,
        // intent: DEC-003 — legacy preset は false
        excludeUnreliableJudges: settings.excludeUnreliableJudges,
        judgeRunCount: settings.judgeRunCount,
        subjectRunCount: settings.subjectRunCount,
        subjectTemperature: settings.subjectTemperature,
    };
}

export function resolveExecutionPresetConfig(
    config: ExecutionPresetConfig,
    availableModels: Model[],
    availableTasks: Task[],
): ResolvedExecutionPreset {
    const availableModelIds = new Set(availableModels.map((model) => model.id));
    const availableTaskIds = new Set(availableTasks.map((task) => task.id));
    const hasCatalogModels = availableModels.length > 0;
    // intent: DEC-004 (Core/holistic-judge-model) — 旧 preset（field なし）は空配列扱い
    const holisticJudgeModels = config.holisticJudgeModels ?? [];
    const requestedModelIds = [
        ...(config.subjectModel ? [config.subjectModel] : []),
        ...config.judgeModels,
        ...holisticJudgeModels,
    ];
    const missingModelIds = hasCatalogModels
        ? requestedModelIds.filter((id) => !availableModelIds.has(id))
        : [];
    const requestedTaskIds = Object.entries(config.taskSelections)
        .filter(([, selected]) => selected)
        .map(([id]) => id);
    const requestedTaskIdSet = new Set(requestedTaskIds);

    return {
        subjectModelId:
            hasCatalogModels && config.subjectModel && availableModelIds.has(config.subjectModel)
                ? config.subjectModel
                : null,
        judgeModelIds: hasCatalogModels
            ? config.judgeModels.filter((id) => availableModelIds.has(id))
            : [],
        freeTextSubject: hasCatalogModels ? '' : config.subjectModel ?? '',
        freeTextJudges: hasCatalogModels ? [] : [...config.judgeModels],
        holisticJudgeModelIds: hasCatalogModels
            ? holisticJudgeModels.filter((id) => availableModelIds.has(id))
            : [],
        freeTextHolisticJudges: hasCatalogModels ? [] : [...holisticJudgeModels],
        selectedTaskIds: availableTasks
            .filter((task) => requestedTaskIdSet.has(task.id))
            .map((task) => task.id),
        runHolistic: config.runHolistic,
        excludeUnreliableJudges: Boolean(config.excludeUnreliableJudges),
        judgeRunCount: Math.min(5, Math.max(1, Math.round(config.judgeRunCount))),
        // intent: DEC-002/005 (Core/subject-multi-run-judge-batch) — legacy preset は 1
        subjectRunCount: Math.min(
            5,
            Math.max(1, Math.round(config.subjectRunCount ?? 1)),
        ),
        subjectTemperature: Math.min(1, Math.max(0, config.subjectTemperature)),
        missingModelIds: [...new Set(missingModelIds)],
        missingTaskIds: requestedTaskIds.filter((id) => !availableTaskIds.has(id)),
    };
}
