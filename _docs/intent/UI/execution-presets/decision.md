---
title: "Decision: Browser-local execution presets"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/reference/UI/execution-presets.md"
  - "_docs/qa/UI/execution-presets/test-plan.md"
  - "_docs/qa/UI/execution-presets/verification.md"
related_issues: []
related_prs: []
---

# Decision: Browser-local execution presets

## Context

反復評価ではモデル、task set、評価回数、temperatureを切り替えるため、同じ実行条件を
手作業で再構成する負担がある。一方、このアプリは個人利用を前提としており、プリセットの
共有、backend同期、複数端末間の移行は必要ない。

## Decisions

### DEC-001: プリセットはlocalStorageに保存する

- **What**: 名前付き実行プリセットを既存Zustand persistのlocalStorageへ保存する。
- **Why**: backend APIとapp data schemaを増やさず、現在のSettings永続化と同じ障害範囲で扱える。
- **Change freedom**: 個人利用の単純さを維持できる限り、localStorage keyやstate分割は変更できる。
- **Revisit when**: 複数ブラウザ間の同期、import / export、共有が必要になった場合。

### DEC-002: 実行結果へ影響する限定フィールドだけを保存する

- **What**: 被験・judgeモデル、task選択、包括評価、judge評価回数、subject temperatureを保存する。
- **Why**: API keyなどの秘密情報を混入させず、tool modeや並列数など今回の再利用目的に含まれない設定を固定しない。
- **Change freedom**: 新しい実行条件を追加するときはschema versionを更新して保存対象を拡張できる。

### DEC-003: 欠損モデルとtaskはUI通知なしで除外する

- **What**: ロード時に現在存在しないモデル・taskを適用対象から除外し、console warningだけを残す。
- **Why**: 個人利用では古いプリセットの部分適用を優先し、警告UIや修復フローの運用負担を持たない。
- **Change freedom**: UIを中断しない限り、warning形式や診断情報は変更できる。
- **Revisit when**: プリセット不整合をユーザーが見落とすことで誤評価が発生した場合。

## Consequences / Impact

- localStorageを消去するとプリセットも失われる。
- プリセットをロードするとStandard modeへ切り替わる。Strictはofficial presetを引き続き唯一の設定源とする。
- モデルカタログが空の場合は保存モデルをfree-text入力へ戻し、LM Studioなどの手動指定を維持する。
- 欠損項目の除外後に実行条件が不足した場合、既存Run画面の開始条件が実行を抑止する。

## Quality Implications

- API keyを含む秘密情報がプリセットへ保存されないこと。
- task選択は選択済みIDだけでなく、保存時点の各taskのbooleanとして監査できること。
- 欠損項目を除外しても、残った設定値が壊れずに適用されること。
- schema変更時に旧データを無条件適用しないこと。

## Intent-derived Invariants

- INV-001 (from DEC-002): 実行プリセットへAPI keyを保存しない。
- INV-002 (from DEC-003): 欠損モデル・taskはUIを中断せずに除外する。

## Enforced in (optional)

- DEC-001: `frontend/src/store/settingsStore.ts`
- DEC-002: `frontend/src/lib/executionPresets.ts`
- DEC-003: `frontend/src/lib/executionPresets.ts`, `frontend/src/store/settingsStore.ts`

## Rollback / Follow-ups

- 機能を無効化する場合はSettings UIとstore actionを外す。既存localStorage内の
  `executionPresets`は他のSettingsへ影響しない。
- import / exportやbackend同期は今回の対象外とする。
