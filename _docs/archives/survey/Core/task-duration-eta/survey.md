---
title: "Survey: Task duration estimates and ETA on results"
status: completed
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/plan/Core/task-duration-eta/plan.md"
  - "_docs/intent/Core/task-duration-eta/decision.md"
related_issues: []
related_prs: []
---

## Background

- TODO `Core-Feat-34` は実行中・結果画面双方でタスク単位の所要時間目安と ETA を提供する。
- Inbox 由来の時間 ROI 改善（`Core-Enhance-41`）と timing スキーマを共有しうるが、本タスクは
  ETA 表示にスコープを限定する。

## Objective

- 現行の duration 計測・保存・進捗 UI・結果表示の gap を特定し、Plan / Intent の根拠とする。

## Method

- `core/cost_estimator.py`、`core/benchmark_engine.py`（`TaskResult`）、`core/result_storage.py`、
  `server.py`（progress / `execution_duration_ms`）、`frontend`（RunPage、`ResultDetail`、
  `client.ts`）を静的調査した。

## Results

### Usage 計測（adapter / cost_estimator）

- `UsageMetrics.duration_ms` は adapter が `perf_counter` 差分で設定する（OpenRouter / LM Studio）。
- `summarize_usage_records` は usage レコードの `duration_ms` をモデル別・合計
  `total_duration_ms` へ集計する。
- run 保存時、`server.py` は `summarize_benchmark_usage` / `summarize_subject_usage` /
  `summarize_judge_usage` を `usage_summary*` として付与する。

### タスク結果 JSON（BenchmarkEngine / TaskResult）

- `TaskResult.to_dict()` は `subject_usage` と judge run 内 `usage` を含むが、タスク粒度の
  `subject_duration_ms` / `judge_duration_ms` フィールドはない。
- subject は `subject_result.usage.to_dict()` をそのまま保存。multi-turn では
  `_merge_subject_usage` が token を合算するが、**`duration_ms` は合算していない**（gap）。
- judge は各 run の `usage.duration_ms` を個別保持。タスク単位 judge 合算は保存時に未実施。

### Run 全体 timing（server.py / result_storage）

- `execution_duration_ms` は run 開始から完了までの **wall-clock**（`perf_counter` 差分）。
- `ResultStorage._build_summary` は summary index に `execution_duration_ms` のみ載せ、
  per-task timing はない。

### 実行中 UI（SSE progress / RunPage）

- SSE `progress` event は `current` / `total` step、`completedTaskCount`、lane snapshot を送る。
- **ETA / remaining time フィールドは存在しない**。
- RunPage は `liveElapsedMs`（経過時間）のみ表示。残り時間予測 UI なし。

### 結果詳細（ResultDetail）

- `TaskResultCard` はスコア・回答・judge 評価を表示。**per-task duration 表示なし**。
- `CostSection` は run 全体の `usageSummarySubject/Judge.totals.totalDurationMs` を参照するが、
  タスクカード内訳は未提供。
- `SubjectUsage` 型（frontend）は token / cost のみで **`durationMs` を持たない**（`UsageCall`
  は持つ）。

## Discussion

- usage ベースの duration は既に計測されているが、タスク JSON へ明示永続化されていないため、
  ETA・結果内訳・後続 ROI が毎回再解釈される。
- wall-clock（`execution_duration_ms`）は並列 judge / subject 並列実行で usage 合算より大きく
  なり、タスク単位 ETA や ROI 分母に使うと AC 意図とずれる。
- 初回実行 ETA は完了タスク実測が 0 のため、step 比率または unavailable 表示が必要（現 UI に
  該当実装なし）。

## Recommended Actions

1. `task_timing` を `TaskResult.to_dict()` と保存 JSON に追加し、subject / judge ms をタスク完了時
   に集計する。
2. `_merge_subject_usage` に `duration_ms` 合算を追加する。
3. `server.py` progress builder に ETA（measured / step fallback / unavailable）を追加する。
4. RunPage と ResultDetail に ETA / per-task duration 表示を接続する。
5. `Core-Enhance-41` へ timing 正典を引き渡し、ROI 分母を統一する。
