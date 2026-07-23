---
title: "Survey: Fix time ROI calculation (subject vs judge timing)"
status: archived
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/plan/Core/time-roi-task-timing/plan.md"
  - "_docs/intent/Core/time-roi-task-timing/decision.md"
  - "_docs/archives/survey/Core/task-duration-eta/survey.md"
related_issues: []
related_prs: []
---

## Background

- TODO `Core-Enhance-41` は時間 ROI を run wall-clock ではなく、タスク単位の被検・judge 所要時間
  合算で一貫算出する。
- `Core-Feat-34`（task-duration-eta）に依存。Feat-34 が `task_timing` を永続化する前提で本
  survey は現行 ROI 実装の gap を整理する。

## Objective

- `ResultDetail`、`DashboardPage`、`cost_estimator`、`server.py` における時間関連指標の不一致を
  特定し、Enhance-41 Plan / Intent の根拠とする。

## Method

- `frontend/src/components/ResultDetail.tsx`（`CostSection`）、
  `frontend/src/pages/DashboardPage.tsx`、`frontend/src/api/client.ts`、
  `core/cost_estimator.py`、`server.py`、`core/result_storage.py` を静的調査した。

## Results

### Run 保存と usage 集計（backend）

- `server.py` は run 完了時に `execution_duration_ms`（wall-clock）と `usage_summary` /
  `usage_summary_subject` / `usage_summary_judge` を保存する。
- `cost_estimator.summarize_usage_records` は usage の `duration_ms` を
  `total_duration_ms` へ合算する。タスク粒度の `task_timing` は **未保存**（Feat-34 予定）。
- summary index（`ResultStorage._build_summary`）は `execution_duration_ms` のみ timing 関連
  field を持つ。

### ResultDetail 時間 ROI（CostSection）

- subject / judge タブ: `usageSummarySubject/Judge.totals.totalDurationMs` を分母に使用。
- total タブ: 両方揃えば合算。欠落時は `run.executionDurationMs` に暗黙フォールバックする
  （`frontend/src/components/ResultDetail.tsx` の `CostSection`）。
- 表示 duration（`displayDurationMs`）も total タブで同様に wall-clock フォールバックあり。

### Dashboard 時間 ROI（DashboardPage）

- `buildModelAggregates` は `run.executionDurationMs` を `executionTimes` に push し、
  `avgExecutionTimeMs` と `formatTimeRoi(row.avgScore, row.avgExecutionTimeMs)` を算出する。
- **usage summary の totalDurationMs は Dashboard 集計に使われていない**。
- 並列 judge 実行 run では wall-clock が usage 合算より大きくなり、ROI が過小評価される。

### 並列実行との関係

- judge 並列（`max_parallel_runs_per_judge` / `max_parallel_judges`）は engine 内で複数 run を
  同時実行する。usage `duration_ms` 合算は各 judge call の処理時間の和、wall-clock は重なりを
  含まない待ち時間も反映する。
- 時間 ROI を「モデル処理秒あたりの得点」と読むなら、wall-clock は不適切な分母。

### Feat-34 との接点

- Feat-34 survey より: usage duration は計測済みだがタスク JSON へ明示永続化されていない。
- Enhance-41 は Feat-34 の `task_timing` を ROI 正典として run summary / UI へ接続する。

## Discussion

- ResultDetail と Dashboard で時間 ROI の入力源が既に不一致（前者は usage totals + wall-clock
  fallback、後者は wall-clock のみ）。
- AC-003 が禁止する暗黙 wall-clock フォールバックは ResultDetail total タブに存在する。
- Feat-34 未完了の間、Enhance-41 は実装開始できないが、Intent 上の ROI 分母定義は先行して固定
  できる。

## Recommended Actions

1. Feat-34 完了後、`task_timing` から run `timing_summary` を生成する。
2. ResultDetail `CostSection` の時間 ROI / duration 表示を timing totals ベースへ更新し、
   暗黙 wall-clock fallback を除去（または明示ラベル化）。
3. Dashboard `buildModelAggregates` を timing totals 入力へ切り替える。
4. parallel judge fixture で wall-clock ≠ timing total の regression test を追加する。
5. AC-004 用に `cost_estimator` 合算と timing summary の一致 test を追加する。
