---
title: "Intent: Task duration estimates and ETA on results"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/plan/Core/task-duration-eta/plan.md"
  - "_docs/qa/Core/task-duration-eta/test-plan.md"
  - "_docs/archives/survey/Core/task-duration-eta/survey.md"
  - "_docs/qa/Core/task-duration-eta/verification.md"
related_issues: []
related_prs: []
---

# Intent: Task duration estimates and ETA on results

## Context

adapter は各 LLM 呼び出しで `UsageMetrics.duration_ms` を計測しているが、タスク結果 JSON には
`subject_usage` と judge run ごとの `usage` として間接的にしか残らない。run サマリーには
wall-clock の `execution_duration_ms` のみが記録される。

実行中 UI は経過時間と step 進行（`current` / `total`）を表示するが、残り時間予測はない。
結果詳細もタスクカード単位の duration 内訳を表示していない。並列 judge 実行時、wall-clock と
usage 合算は一致しないため、将来の ROI 改善（`Core-Enhance-41`）に備えタスク単位 timing を
明示永続化する。

## Decisions

### DEC-001: タスク結果 JSON に `task_timing` オブジェクトを正典として追加する

- **What**: 各通常タスク結果に `task_timing: { subject_duration_ms, judge_duration_ms }` を
  永続化する。値は当該タスクの subject usage と judge runs usage から集計する。
- **Why**: usage ネストだけでは UI と ROI が毎回再集計し、multi-turn subject や skipped run の
  扱いがぶれる。タスク粒度の timing を一次データにすると ETA・結果表示・後続 ROI が同じ定義を
  参照できる。
- **Change freedom**: フィールド名、`task_timing` を flat field に flatten するか、holistic task
  への拡張方法は、subject / judge 内訳が保存 JSON から読める限り変更できる。
- **Why not**: run 全体の `execution_duration_ms` をタスク数で割る近似は、並列実行と judge 多重
  run で実測と乖離し、AC-001 を満たさない。
- **Revisit when**: adapter が streaming chunk 単位 timing を返すようになり、タスク内フェーズ
  分解が必要になった時。

### DEC-002: ETA は同一 run 内の完了タスク実測平均を正典とし、不足時のみ step 比率フォールバックする

- **What**: progress ETA は「完了済み通常タスクの `(subject + judge) ms` 平均 × 残タスク数」で
  算出する。完了タスクが 0 件のときのみ `elapsed_ms / current_step × remaining_steps` の step
  比率見積もりを使う。どちらも不可なら `eta_status: unavailable` とする。
- **Why**: 初回実行でも step 進行と経過時間から粗い見積もりは可能だが、実測ゼロで確定値風に
  見せると誤解を招く。完了タスクが溜まった時点から実測ベースへ切り替える。
- **Change freedom**: ETA 計算の実装場所（backend vs frontend）、表示フォーマット、confidence
  ラベルは、AC-004 の「推定不可 / フォールバック明示」を満たす限り変更できる。
- **Why not**: 過去 run の履歴平均は本 run の judge 数・並列設定と一致しないことが多く、初回
  実行要件（AC-004）とも整合しにくい。
- **Revisit when**: run 設定（judge 数、並列度）を跨いだ履歴 ETA が必要になった時。

### DEC-003: ETA と per-task duration 表示は推定であることを UI で区別する

- **What**: step 比率フォールバック時は「推定（step ベース）」、実測ベース時は「推定（実測平均）」
  などラベルまたは `eta_status` で区別する。実測不可は「推定不可」と表示する。
- **Why**: AC-004 は誤った確定値表示を禁止する。数値だけ出すと利用者が wall-clock や SLA と
  混同する。
- **Change freedom**: ラベル文言、tooltip、色分けは変更できるが、fallback と measured の区別は
  維持する。
- **Why not**: ラベルなし数値のみ表示は AC-004 に反する。

## Consequences / Impact

- 保存 JSON に additive field が増える。旧 frontend は field 欠落時 N/A 表示で継続可能。
- SSE progress payload に `eta_ms` / `eta_status`（名称は実装時確定）が追加される。
- `_merge_subject_usage` は multi-turn subject の `duration_ms` 合算を行う必要がある（現状未実装）。
- `Core-Enhance-41` は本 Intent の `task_timing` を ROI 分母の正典として再利用できる。

## Quality Implications

- engine が `task_timing` を正しく集計すること、storage round-trip、client 変換、ETA helper の
  fallback 分岐を unit / node test する。
- parallel judge 実行 fixture で wall-clock より usage 合算が ROI に適する定義であることを
  文書化する（Enhance-41 へ引き渡し）。

## Intent-derived Invariants

None

## Rollback / Follow-ups

- rollback は `task_timing` 永続化、progress ETA field、RunPage / ResultDetail 表示を同時に戻す。
- 包括評価タスクの timing 表示方針は本タスクでは最小限とし、必要なら follow-up で dedicated
  表示を検討する。
