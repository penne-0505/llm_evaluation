import type { ExecutionPreset, ExecutionPresetConfig, Model, Task } from '../types';

export const EXECUTION_PRESET_SCHEMA_VERSION = 1 as const;

interface CurrentExecutionSettings {
    subjectModelId: string | null;
    judgeModelIds: string[];
    freeTextSubject: string;
    freeTextJudges: string[];
    tasks: Task[];
    selectedTaskIds: string[];
    runHolistic: boolean;
    judgeRunCount: number;
    subjectTemperature: number;
}

export interface ResolvedExecutionPreset {
    subjectModelId: string | null;
    judgeModelIds: string[];
    freeTextSubject: string;
    freeTextJudges: string[];
    selectedTaskIds: string[];
    runHolistic: boolean;
    judgeRunCount: number;
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
        taskSelections: Object.fromEntries(
            settings.tasks.map((task) => [task.id, selectedTaskIds.has(task.id)]),
        ),
        runHolistic: settings.runHolistic,
        judgeRunCount: settings.judgeRunCount,
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
    const requestedModelIds = [
        ...(config.subjectModel ? [config.subjectModel] : []),
        ...config.judgeModels,
    ];
    const missingModelIds = hasCatalogModels
        ? requestedModelIds.filter((id) => !availableModelIds.has(id))
        : [];
    const requestedTaskIds = Object.entries(config.taskSelections)
        .filter(([, selected]) => selected)
        .map(([id]) => id);

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
        selectedTaskIds: requestedTaskIds.filter((id) => availableTaskIds.has(id)),
        runHolistic: config.runHolistic,
        judgeRunCount: Math.min(5, Math.max(1, Math.round(config.judgeRunCount))),
        subjectTemperature: Math.min(1, Math.max(0, config.subjectTemperature)),
        missingModelIds: [...new Set(missingModelIds)],
        missingTaskIds: requestedTaskIds.filter((id) => !availableTaskIds.has(id)),
    };
}
