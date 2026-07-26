---
title: "QA Test Plan: Execution Presets"
status: active
draft_status: n/a
qa_status: planned
risk: Medium
qa_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-26
references:
  - "_docs/archives/plan/UI/execution-presets/plan.md"
  - "_docs/intent/UI/execution-presets/decision.md"
  - "_docs/reference/UI/execution-presets.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Execution Presets

## Source of Intent

- TODO: `UI-Enhance-74`
- Plan: `_docs/archives/plan/UI/execution-presets/plan.md`
- Intent: `_docs/intent/UI/execution-presets/decision.md`

## Quality Goal

評価対象モデルから独立した実行条件を秘密情報なしで名前付き保存し、プリセット読込時に
現在の被験モデルを維持すること。schema v1に被験モデルが含まれていても無視し、残りの
条件を復元できること。

## Acceptance Criteria

- AC-001: schema v2の新規保存・上書きに被験モデルIDと被験モデル専用preferred hostを含めない。
- AC-002: 読込前後でcatalog選択・free-text被験モデルを維持する。
- AC-003: schema v1の`subjectModel`を無視し、その他の対応fieldを適用する。
- AC-004: judge / 包括judgeのモデル、preferred host、task、包括評価、評価回数、temperatureを保存・復元する。
- AC-005: モデル・task欠損を除外し、warningだけを記録する。
- AC-006: API key、tool mode、並列設定をプリセットへ保存しない。
- AC-007: 選択済みtaskを現在のtask catalog順で復元し、integer-like task IDのJSONキー列挙順に依存しない。
- AC-008: SettingsとREADMEの説明が被験モデルを保存対象として案内しない。
- AC-009: 優先ホストピッカーの候補が後続UIに隠れず、選択操作できる。

## Decision Review Scope

- DEC-001: backendを追加せず、既存Zustand persist内に保存しているか。
- DEC-002: 被験モデルから独立したフィールドだけをschemaへ含めているか。
- DEC-003: 欠損時にUIエラーを追加していないか。
- DEC-004: schema v1を全失効させず、legacy subject modelだけを無視しているか。

## Intent-derived Invariants

- INV-001 (from DEC-002): 実行プリセットへAPI keyを保存しない。
- INV-002 (from DEC-003): 欠損モデル・taskはUIを中断せずに除外する。
- INV-003 (from DEC-002): 実行プリセットの保存・読込で被験モデルの選択を変更しない。

## Risk Assessment

- Risk level: Medium
- Risk rationale: localStorage永続状態と実行条件を変更するuser-facing featureである。
- Regression risk: schema v1を読めなくする、または読込時に被験モデルを上書きし続ける可能性。
- Data safety risk: 上書き・削除で名前付きプリセットを失う可能性。
- Security / privacy risk: API keyを誤ってsnapshotへ含める可能性。
- UX risk: 欠損項目のsilent filterにより設定不足となる可能性。
- UX risk: stacking contextまたはancestor overflowによりhost候補が見えても選択できない可能性。
- Agent misbehavior risk: None

## Test Strategy

- Unit: schema v2 capture / schema v1 resolve / host filtering / schema生成 / 上書きidentity保持。
- Integration: frontend production buildとZustand persist反映。
- E2E: Settings上で保存、変更、ロード、reload後永続、上書き、削除。
- Manual QA: desktop表示、mobile幅でcontrol存在、console error確認。
- Validator / static check: ESLint、TypeScript build、docs validators。
- Diff review: 保存対象と除外対象の境界、secret非保存を確認。

## Test Matrix

| ID | Source | Requirement / Optional Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | v2からsubject identityを除外 | unit | `executionPresets.node.test.ts` | configにsubject modelと専用hostなし | verified |
| AC-002 | TODO / INV-003 | current subjectを維持 | unit | `settingsStore.node.test.ts` | load後もcatalog / free-text subjectが不変 | verified |
| AC-003 | DEC-004 | schema v1互換読込 | unit | `executionPresets.node.test.ts` | legacy subjectだけ無視して他fieldを解決 | verified |
| AC-004 | DEC-002 | judge系条件を復元 | unit | `executionPresets.node.test.ts` | judge / holistic judgeと必要hostを往復 | verified |
| AC-005 | DEC-003 / INV-002 | 欠損除外 | unit | `executionPresets.node.test.ts` | missing IDと適用値を分離 | verified |
| AC-006 | DEC-002 / INV-001 | secret等の非保存 | review | schema / capture review | configにsecret fieldなし | verified |
| AC-007 | DEC-002 | task復元順序 | unit | `executionPresets.node.test.ts` | catalog順復元と欠損検出 | verified |
| AC-008 | TODO | 説明の同期 | docs review | Settings / README / reference | 被験モデルを保存対象としない | verified |
| AC-009 | TODO | host pickerの前面表示 | component test / manual | HostPicker / Settings | 候補が後続要素より前面で選択可能 | verified |
| INV-003 | DEC-002 | 被験モデル非変更 | unit / manual | store test / Settings | 保存・読込前後で同一 | verified |

## Manual QA Checklist

- [ ] 現在の被験モデルを選択してプリセットを保存する。
- [ ] 別の被験モデルへ変更後、プリセットをロードして変更後モデルが維持される。
- [ ] judge、task、評価回数、temperatureはプリセット値へ戻る。
- [ ] schema v1 fixtureをロードして被験モデルだけが変わらない。
- [ ] host pickerを開き、後続のSettings sectionに隠れず候補を選択できる。
- [ ] 関連するconsole errorがない。

## Regression Checklist

- [ ] frontend production buildが成功する。
- [ ] frontend lintとtest suiteが成功する。
- [ ] backend test suiteが成功する。
- [ ] docs validatorsが成功する。
- [ ] 既存Settings項目はpersist対象のまま維持される。

## High-risk Checklist

Not applicable (Risk Medium).

## Out of Scope

- 複数ブラウザ間の同期
- import / export
- backend / app data保存
- アプリ全体のmobile navigation / sidebar再設計

## Open Questions

None
