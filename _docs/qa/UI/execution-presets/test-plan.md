---
title: "QA Test Plan: Execution Presets"
status: active
draft_status: n/a
qa_status: planned
risk: Medium
qa_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/UI/execution-presets/decision.md"
  - "_docs/reference/UI/execution-presets.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Execution Presets

## Source of Intent

- TODO: None
- Plan: None (Fast Track)
- Intent: `_docs/intent/UI/execution-presets/decision.md`

## Quality Goal

実行設定を秘密情報なしで名前付き保存し、ブラウザ再読み込み後も復元できること。
古いプリセットに欠損モデル・taskが含まれてもSettings UIを中断しないこと。

## Acceptance Criteria

- AC-001: 保存対象6項目をtaskのboolean状態を含むschema v1として保存できる。
- AC-002: 保存・ロード・上書き・削除がlocalStorageへ反映される。
- AC-003: モデル・task欠損を除外し、warningだけを記録する。
- AC-004: catalog未取得時のmanual model文字列をfree-text入力へ復元する。
- AC-005: API key、tool mode、並列設定をプリセットへ保存しない。
- AC-006: 選択済みtaskを現在のtask catalog順で復元し、integer-like task IDのJSONキー列挙順に依存しない。

## Decision Review Scope

- DEC-001: backendを追加せず、既存Zustand persist内に保存しているか。
- DEC-002: 合意済みフィールドだけをschemaへ含めているか。
- DEC-003: 欠損時にUIエラーを追加していないか。

## Intent-derived Invariants

- INV-001 (from DEC-002): 実行プリセットへAPI keyを保存しない。
- INV-002 (from DEC-003): 欠損モデル・taskはUIを中断せずに除外する。

## Risk Assessment

- Risk level: Medium
- Risk rationale: localStorage永続状態と実行条件を変更するuser-facing featureである。
- Regression risk: Settings persistの既存フィールドを失う可能性。
- Data safety risk: 上書き・削除で名前付きプリセットを失う可能性。
- Security / privacy risk: API keyを誤ってsnapshotへ含める可能性。
- UX risk: 欠損項目のsilent filterにより設定不足となる可能性。
- Agent misbehavior risk: None

## Test Strategy

- Unit: capture / resolve / schema生成 / 上書きidentity保持。
- Integration: frontend production buildとZustand persist反映。
- E2E: Settings上で保存、変更、ロード、reload後永続、上書き、削除。
- Manual QA: desktop表示、mobile幅でcontrol存在、console error確認。
- Validator / static check: ESLint、TypeScript build、docs validators。
- Diff review: 保存対象と除外対象の境界、secret非保存を確認。

## Test Matrix

| ID | Source | Requirement / Optional Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | Intent DEC-002 | schema v1とtask boolean | unit | `executionPresets.node.test.ts` | 全taskのtrue/false保存 | verified |
| AC-002 | Intent DEC-001 | CRUDとreload後永続 | rendered QA | Settings `/settings` | `1 saved`、reload後option保持、削除後`0 saved` | verified |
| AC-003 | Intent DEC-003 | 欠損除外 | unit | `executionPresets.node.test.ts` | missing IDと適用値を分離 | verified |
| AC-004 | Intent DEC-002 | manual model復元 | unit | `executionPresets.node.test.ts` | free-textへ復元 | verified |
| AC-006 | Intent DEC-002 | task復元順序 | unit | `executionPresets.node.test.ts` | `02, 04, 10, 11`をcatalog順で復元し、`99`を欠損として検出 | verified |
| INV-001 | DEC-002 | API key非保存 | review | schema / partialize review | configにsecret fieldなし | verified |
| INV-002 | DEC-003 | UIを中断しない | unit / rendered QA | resolve test / browser console | filter後も適用、関連errorなし | verified |

## Manual QA Checklist

- [x] Settingsに実行プリセットsectionが表示される。
- [x] 名前入力で保存buttonが有効になる。
- [x] 保存後に件数とoptionが更新される。
- [x] 設定変更後にロードすると保存値へ戻る。
- [x] reload後も保存済みoptionが残る。
- [x] 上書きと削除のconfirm操作が機能する。
- [x] 関連するconsole error / warningがない。

## Regression Checklist

- [x] frontend production buildが成功する。
- [x] frontend lintが成功する。
- [x] backend test suiteが成功する。
- [x] 既存Settings項目はpersist対象のまま維持される。

## High-risk Checklist

Not applicable (Risk Medium).

## Out of Scope

- 複数ブラウザ間の同期
- import / export
- backend / app data保存
- アプリ全体のmobile navigation / sidebar再設計

## Open Questions

None
