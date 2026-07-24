---
title: "Intent: Task duration estimates and ETA on results"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-23
updated_at: 2026-07-24
references:
  - "_docs/archives/plan/Core/task-duration-eta/plan.md"
  - "_docs/plan/Core/run-eta-history-blend/plan.md"
  - "_docs/qa/Core/task-duration-eta/test-plan.md"
  - "_docs/archives/survey/Core/task-duration-eta/survey.md"
  - "_docs/qa/Core/task-duration-eta/verification.md"
  - "_docs/reference/UI/pre-run-estimate/reference.md"
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

### DEC-002: ETA 正典は残り待ち時間（wall-clock）。実測ペースを強く、履歴は弱い事前

- **What**: progress ETA は「押してから終わるまでの残り」を出す。同一 run の
  `経過 / 完了タスク数 × 残タスク数` を実測ペースとし、完了が増えるほど強く効かせる。
  pre-run と同系の類似度重み付き履歴 wall を弱い事前として backend SSE に載せる。
  完了 0 かつ履歴が無いときだけ step 比率へ落とす。
- **Why**: 実行中に知りたいのは処理時間合算ではなく待ちの残りだから。履歴だけで決めると
  本 run の実速度を無視し、実測だけだと序盤が不安定なので履歴を薄い事前にする。
- **Change freedom**: `α(n)`、履歴カーネル定数、`eta_status` 語彙、実装モジュール分割は変更可。
- **Why not**: `task_timing` 平均×残タスクを主値にすると並列待ちとずれる。履歴を使わないと
  完了 0 の序盤が step 比率だけになり、構成類似の過去が活きない。
- **Revisit when**: タスク単位 wall-clock や並列度が summary に載り、ペース定義を細かくできる時。

### DEC-003: ETA と per-task duration 表示は推定であることを UI で区別する

- **What**: `eta_status` で実測ペース / 実測+履歴 / 履歴 / step 比率 / 推定不可を区別する。
  実測不可は「推定不可」と表示する。
- **Why**: 数値だけ出すと利用者が確定の残り時間と混同する。
- **Change freedom**: ラベル文言、tooltip、色分けは変更できるが、status の区別は維持する。
- **Why not**: ラベルなし数値のみ表示は誤解を招く。

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
