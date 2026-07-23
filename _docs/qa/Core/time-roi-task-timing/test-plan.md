---
title: "QA Test Plan: Fix time ROI calculation (subject vs judge timing)"
status: active
draft_status: n/a
qa_schema: 2
qa_status: planned
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/plan/Core/time-roi-task-timing/plan.md"
  - "_docs/intent/Core/time-roi-task-timing/decision.md"
  - "_docs/archives/survey/Core/time-roi-task-timing/survey.md"
  - "_docs/intent/Core/task-duration-eta/decision.md"
  - "_docs/qa/Core/time-roi-task-timing/verification.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Fix time ROI calculation (subject vs judge timing)

## Source of Intent

- `_docs/intent/Core/time-roi-task-timing/decision.md`

## Decision Review Scope

- `DEC-001`: 時間 ROI 分母が task_timing subject + judge 合算であること。
- `DEC-002`: run payload / summary index に timing totals が載り frontend が参照すること。
- `DEC-003`: 内訳欠落 run で暗黙 wall-clock フォールバックを使わないこと。
- `DEC-004`: Dashboard 集計が `executionDurationMs` を時間 ROI 入力に使わないこと。

## Quality Goal

時間 ROI が run wall-clock や並列待機込み総時間に依存せず、タスク単位の被検・judge 所要時間
合算で ResultDetail と Dashboard が一貫して算出される。

## Acceptance Criteria

- AC-001: 各タスク結果に被検所要時間・judge 所要時間（ms）が永続化され、run サマリー
  （subject / judge / total）へ正しく合算される。
- AC-002: `ResultDetail` の時間 ROI（`CostSection`）と `DashboardPage` の時間 ROI
  （`AggregationTable.formatTimeRoi`）が、同一の subject+judge 合算定義を用い、並列実行による
  wall-clock 膨張を ROI 分母に使わない。
- AC-003: subject / judge 内訳が欠落する run では ROI を N/A または部分表示とし、
  `executionDurationMs` への暗黙フォールバックを廃止するか、フォールバック時は
  「推定（wall-clock）」と明示する。
- AC-004: 既存の usage ベース duration 集計（`core/cost_estimator.py`）との整合性がテストで
  検証される。

## Intent-derived Invariants

None

## Risk Assessment

- Medium: ROI 定義変更によりダッシュボード数値が変わり、過去 run との直接比較に注意が必要。
- Medium: summary index と full result で timing totals の欠落扱いがずれると AC-002 / AC-003 を
  満たさない。
- Dependency: `Core-Feat-34` 完了前は AC-001 以降を検証できない。

## Test Strategy

- Python unit test で run 保存時の timing summary 合算と `task_timing` round-trip を確認する。
- Python unit test で parallel judge fixture において wall-clock ≠ timing total となることを
  固定し、保存 payload が timing total を使うことを確認する。
- Node unit test で `CostSection` helper と `buildModelAggregates` / `formatTimeRoi` が同一
  ms 入力で同一 ROI を返すことを確認する。
- 旧フォーマット result fixture で AC-003（N/A または明示ラベル）を確認する。
- `cost_estimator.summarize_*` と timing totals の一致を AC-004 で確認する。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | task_timing → run timing summary 合算 | unit | `uv run pytest tests/test_result_storage.py tests/test_server_frontend.py` | subject / judge / total ms が task 合算と一致 | verified |
| AC-001 | DEC-002 | summary index に timing totals | unit | `uv run pytest tests/test_result_storage.py` | index entry が timing fields を保持 | verified |
| AC-002 | TODO | ResultDetail 時間 ROI が timing total 使用 | node unit | CostSection helper test | parallel fixture で wall-clock より小さい ms が分母 | verified |
| AC-002 | TODO | Dashboard formatTimeRoi が同一定義 | node unit | `DashboardPage` aggregate helper test | 同一 run fixture で Detail と同値 ROI | verified |
| AC-002 | DEC-001 | wall-clock を ROI 分母に使わない | unit + node | server save + frontend ROI test | `execution_duration_ms` > timing total でも ROI は timing ベース | verified |
| AC-003 | TODO | 内訳欠落 run の N/A / 明示 fallback | node unit | 旧 result fixture test | 暗黙 `executionDurationMs` フォールバックなし | verified |
| AC-003 | DEC-003 | fallback 採用時は wall-clock 明示 | review + unit | `ResultDetail.tsx` diff | ラベル「推定（wall-clock）」または N/A のみ | verified |
| AC-004 | TODO | cost_estimator との整合 | unit | `uv run pytest tests/test_cost_estimator.py` | usage total_duration_ms と timing total が一致 | verified |
| DEC-004 | Intent | Dashboard が executionDurationMs を除外 | node unit | `buildModelAggregates` test | `avgExecutionTimeMs` が timing totals 由来 | verified |
| AC-001--004 | Plan | regression safety | lint/build | `npm run lint --prefix frontend` / `npm run build --prefix frontend` / `uv run pytest` | build と backend suite success | verified |

## Manual QA Checklist

- [ ] judge 並列 ON の run で、時間 ROI が run 経過時間より「速い」値にならない（wall-clock 誤用なし）。
- [ ] ResultDetail total タブと Dashboard 集計表の時間 ROI が同一 run で一致する。
- [ ] 旧 result（task_timing 欠落）で時間 ROI が N/A または明示ラベルになる。
- [ ] 被検 / judge タブ単体の時間 ROI が各内訳 ms を分母に使う。

## Regression Checklist

- [ ] コスト ROI（USD）計算が変わらない。
- [ ] `execution_duration_ms` の表示（経過時間メタデータ）が削除されない。
- [ ] usage_summary token / cost 表示が退行しない。

## Out of Scope

- 実行中 ETA（`Core-Feat-34`）。
- 旧 result の backfill migration。
- live judge API smoke。

## Open Questions

- DEC-003: ~~内訳欠落時に完全 N/A と明示 wall-clock のどちらを採用するか~~ → **完全 N/A に固定**（verification 記録済み）。

