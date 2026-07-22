---
title: Execution Presets
status: active
draft_status: n/a
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/UI/execution-presets/decision.md"
  - "_docs/qa/UI/execution-presets/test-plan.md"
  - "_docs/qa/UI/execution-presets/verification.md"
related_issues: []
related_prs: []
---

# Execution Presets

## Overview

Settings の実行プリセットは、現在の実行条件へ名前を付けてブラウザの
localStorage に保存し、後から同じ条件を復元する機能である。保存・ロード・
上書き・削除は frontend 内で完結し、backend API や app data は使用しない。

## Storage

- Zustand persist の localStorage key `llm-eval-settings` 内に
  `executionPresets` 配列として保存する。
- 各プリセットは `schemaVersion: 1` を持つ。
- API key やprovider設定は保存しない。
- 同名プリセットの新規保存は行わない。既存プリセットの更新には上書き操作を使う。

## Schema

```ts
interface ExecutionPreset {
    id: string;
    name: string;
    schemaVersion: 1;
    createdAt: string;
    updatedAt: string;
    config: {
        subjectModel: string | null;
        judgeModels: string[];
        taskSelections: Record<string, boolean>;
        runHolistic: boolean;
        judgeRunCount: number;
        subjectTemperature: number;
    };
}
```

## Captured Settings

- 被験モデル
- judgeモデル
- task ID ごとの選択状態
- 包括評価の有無
- judge評価回数
- subject temperature

次の設定はプリセットへ含めない。

- API key
- Standard / Strict のevaluation mode
- task tool mode override
- subject / judge の並列実行設定
- judge temperature

## Load Behavior

- プリセットのロード時はevaluation modeをStandardへ切り替える。
- モデルカタログが利用可能な場合、存在しない被験・judgeモデルを除外する。
- モデルカタログが空の場合、保存したモデル文字列をfree-text入力として復元する。
- 現在のtask一覧に存在しないtask IDは除外する。
- 除外したモデル・taskはUIへ表示せず、`console.warn`へ記録する。
- judge評価回数は`1..5`、subject temperatureは`0..1`へ正規化する。
- 未対応のschema versionは適用せず、`console.warn`へ記録する。

## UI Operations

- `現在設定を保存`: 入力した名前で新規プリセットを作成する。
- `読み込み`: 選択中プリセットを現在のSettingsへ適用する。
- `上書き`: 選択中プリセットのconfigと`updatedAt`を現在値で更新する。
- `削除`: 確認後、選択中プリセットをlocalStorageから削除する。

## Verification

- `frontend/src/lib/executionPresets.node.test.ts`: capture / resolve と欠損除外
- `frontend/src/store/settingsStore.node.test.ts`: schema生成と上書き時のidentity保持
- `npm run build --prefix frontend`: TypeScriptとproduction bundle
- `npm run lint --prefix frontend`: frontend lint
