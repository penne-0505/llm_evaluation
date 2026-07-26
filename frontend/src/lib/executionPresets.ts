import type { ExecutionPreset, ExecutionPresetConfig, Model, Task } from '../types';

export const EXECUTION_PRESET_SCHEMA_VERSION = 2 as const;
export const SUPPORTED_EXECUTION_PRESET_SCHEMA_VERSIONS = [1, 2] as const;

type ResolvableExecutionPresetConfig = ExecutionPresetConfig & {
    /** Legacy schema v1 only. Deliberately ignored during resolution. */
    subjectModel?: string | null;
};

interface CurrentExecutionSettings {
    judgeModelIds: string[];
    freeTextJudges: string[];
    holisticJudgeModelIds: string[];
    freeTextHolisticJudges: string[];
    preferredHosts: Record<string, string>;
    tasks: Task[];
    selectedTaskIds: string[];
    runHolistic: boolean;
    excludeUnreliableJudges: boolean;
    judgeRunCount: number;
    subjectRunCount: number;
    subjectTemperature: number;
}

export interface ResolvedExecutionPreset {
    judgeModelIds: string[];
    freeTextJudges: string[];
    holisticJudgeModelIds: string[];
    freeTextHolisticJudges: string[];
    preferredHosts: Record<string, string>;
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
    return {
        ...preset,
        schemaVersion: EXECUTION_PRESET_SCHEMA_VERSION,
        config,
        updatedAt: timestamp,
    };
}

export function isSupportedExecutionPresetSchemaVersion(version: number): boolean {
    return SUPPORTED_EXECUTION_PRESET_SCHEMA_VERSIONS.some(
        (supportedVersion) => supportedVersion === version,
    );
}

export function captureExecutionPresetConfig(
    settings: CurrentExecutionSettings,
): ExecutionPresetConfig {
    const selectedTaskIds = new Set(settings.selectedTaskIds);
    const judgeModels = settings.judgeModelIds.length > 0
        ? [...settings.judgeModelIds]
        : [...settings.freeTextJudges];
    const holisticJudgeModels = settings.holisticJudgeModelIds.length > 0
        ? [...settings.holisticJudgeModelIds]
        : [...settings.freeTextHolisticJudges];
    const presetHostModelIds = new Set([...judgeModels, ...holisticJudgeModels]);
    return {
        judgeModels,
        // intent: DEC-004 (Core/holistic-judge-model) — 空配列 = judgeModels へ fallback
        holisticJudgeModels,
        // intent: DEC-002 (Core/openrouter-preferred-host)
        preferredHosts: Object.fromEntries(
            Object.entries(settings.preferredHosts)
                .filter(([modelId]) => presetHostModelIds.has(modelId)),
        ),
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
    config: ResolvableExecutionPresetConfig,
    availableModels: Model[],
    availableTasks: Task[],
): ResolvedExecutionPreset {
    const availableModelIds = new Set(availableModels.map((model) => model.id));
    const availableTaskIds = new Set(availableTasks.map((task) => task.id));
    const hasCatalogModels = availableModels.length > 0;
    // intent: DEC-004 (Core/holistic-judge-model) — 旧 preset（field なし）は空配列扱い
    const holisticJudgeModels = config.holisticJudgeModels ?? [];
    const requestedModelIds = [...config.judgeModels, ...holisticJudgeModels];
    const missingModelIds = hasCatalogModels
        ? requestedModelIds.filter((id) => !availableModelIds.has(id))
        : [];
    const resolvedHostModelIds = new Set(
        hasCatalogModels
            ? requestedModelIds.filter((id) => availableModelIds.has(id))
            : requestedModelIds,
    );
    const requestedTaskIds = Object.entries(config.taskSelections)
        .filter(([, selected]) => selected)
        .map(([id]) => id);
    const requestedTaskIdSet = new Set(requestedTaskIds);

    return {
        judgeModelIds: hasCatalogModels
            ? config.judgeModels.filter((id) => availableModelIds.has(id))
            : [],
        freeTextJudges: hasCatalogModels ? [] : [...config.judgeModels],
        holisticJudgeModelIds: hasCatalogModels
            ? holisticJudgeModels.filter((id) => availableModelIds.has(id))
            : [],
        freeTextHolisticJudges: hasCatalogModels ? [] : [...holisticJudgeModels],
        // intent: DEC-002 / INV-002 (Core/openrouter-preferred-host) — missing → {}
        preferredHosts: Object.fromEntries(
            Object.entries(config.preferredHosts ?? {})
                .filter(([modelId]) => resolvedHostModelIds.has(modelId)),
        ),
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

export function mergeExecutionPresetPreferredHosts(
    currentHosts: Record<string, string>,
    currentSubjectModelId: string | null,
    presetHosts: Record<string, string>,
): Record<string, string> {
    const subjectHost = currentSubjectModelId
        ? currentHosts[currentSubjectModelId]
        : undefined;
    if (
        !currentSubjectModelId
        || !subjectHost
        || Object.hasOwn(presetHosts, currentSubjectModelId)
    ) {
        return { ...presetHosts };
    }
    return { ...presetHosts, [currentSubjectModelId]: subjectHost };
}
