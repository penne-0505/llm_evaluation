---
title: "Intent: Fix time ROI calculation (subject vs judge timing)"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/plan/Core/time-roi-task-timing/plan.md"
  - "_docs/qa/Core/time-roi-task-timing/test-plan.md"
  - "_docs/archives/survey/Core/time-roi-task-timing/survey.md"
  - "_docs/intent/Core/task-duration-eta/decision.md"
related_issues: []
related_prs: []
---

# Intent: Fix time ROI calculation (subject vs judge timing)

## Context

Inbox「被験および judge の所要時間をタスク単位で記録し合算」由来。現状、ダッシュボードは
`run.executionDurationMs`（run wall-clock）で時間 ROI を算出し、`ResultDetail` の `CostSection`
は subject / judge 内訳がなければ `executionDurationMs` に暗黙フォールバックする。

並列 judge 実行時、wall-clock は待機・スケジューリングを含み、usage の `duration_ms` 合算や
「モデルが実際に処理した時間」と一致しない。`Core-Feat-34` が `task_timing` を永続化した後、
ROI 分母をその合算へ統一する。

## Decisions

### DEC-001: 時間 ROI の分母はタスク `task_timing` の subject + judge 合算とする

- **What**: run 全体およびタブ（被検 / judge / total）の時間 ROI 分母は、各通常タスクの
  `task_timing.subject_duration_ms` / `judge_duration_ms` を合算した値を使う。並列実行の
  wall-clock は分母に使わない。
- **Why**: ROI は「平均点 per モデル処理秒」を表す指標として読まれる。wall-clock は infra /
  並列度に依存し、モデル比較の指標として歪む。
- **Change freedom**: run サマリー field 名（例: `timing_summary`）、Dashboard 集計粒度、
  表示小数桁は、同一合算定義を維持する限り変更できる。
- **Why not**: `usage_summary.totals.total_duration_ms` だけを直接使うと、holistic judge usage
  の包含範囲が run 定義とずれる可能性がある。タスク `task_timing` を正典にすると Feat-34 と
  一致する。
- **Revisit when**: holistic-only run や subject-less phase の ROI 定義が必要になった時。

### DEC-002: run 保存 payload と summary index に timing totals を明示する

- **What**: benchmark result と summary index に `timing_summary`（または同等）として
  `subject_duration_ms` / `judge_duration_ms` / `total_duration_ms` を付与する。値は
  `task_timing` の合算と一致させる。
- **Why**: Dashboard は summary index から集計するため、毎回 full result を読み直さずに同一
  定義を使える。ResultDetail も run 全体タブで同じ totals を参照できる。
- **Change freedom**: totals を `usage_summary*` へ統合するか別 object にするかは、AC-004 の
  cost_estimator 整合と AC-002 の frontend 単一定義を満たす限り選択できる。
- **Why not**: frontend だけで task 配列から都度再集計すると、Dashboard（summary のみ）と
  ResultDetail（full result）で欠落データ時の挙動がずれる。

### DEC-003: 内訳欠落 run では暗黙 wall-clock フォールバックを廃止する

- **What**: `task_timing` または timing totals が欠落・部分欠落の run では、時間 ROI を N/A
  表示とする。どうしても wall-clock を使う場合はラベルを「推定（wall-clock）」と明示し、
  total タブのみに限定する（採用する場合は QA で固定）。
- **Why**: AC-003 は `executionDurationMs` への暗黙フォールバック廃止または明示を要求する。
  旧 result を wall-clock ROI と誤って比較させない。
- **Change freedom**: 完全 N/A と明示 wall-clock のどちらを採用するかは implementation 時に
  1 つに固定し、両方混在させない。
- **Implementation choice (2026-07-23)**: **完全 N/A** を採用。明示 wall-clock ラベル経路は
  入れない。
- **Why not**: 暗黙フォールバックは並列 run で誤った高/低 ROI を生成し、指標の意味を壊す。

### DEC-004: ダッシュボード集計は通常タスク timing のみをモデル別平均へ使う

- **What**: `buildModelAggregates` の平均時間列と時間 ROI は、各 run の timing totals（通常
  タスク合算）を入力とする。`executionDurationMs` は時間 ROI 入力から除外する。
- **Why**: 現行 `executionTimes.push(run.executionDurationMs)` が wall-clock 依存の原因。
  モデル別 leaderboard の時間 ROI を処理時間ベースに揃える。
- **Change freedom**: strict mode 別 leaderboard への適用順序、表示列ラベルは変更できる。
- **Why not**: wall-clock 平均を残すと DEC-001 と Dashboard / Detail 間で定義が分裂する。

## Consequences / Impact

- ダッシュボード時間 ROI 数値は定義変更により変わる（特に judge 並列 ON の run）。
- 旧 result（`task_timing` 欠落）は時間 ROI N/A となる可能性が高い。
- `Core-Feat-34` への hard dependency。Feat-34 未完了時は本タスクを開始しない。

## Quality Implications

- parallel judge fixture で wall-clock > timing total となるケースを test し、ROI が total
  ms を分母に使うことを確認する。
- cost_estimator の usage 合算と `task_timing` 合算が同一 fixture で一致することを AC-004
  で検証する。

## Intent-derived Invariants

None

## Rollback / Follow-ups

- rollback は ROI 計算と timing summary field の参照を戻す。`task_timing` 永続化は Feat-34
  側で独立に維持できる。
- holistic task timing を Dashboard 集計に含めるかは follow-up で検討する。
