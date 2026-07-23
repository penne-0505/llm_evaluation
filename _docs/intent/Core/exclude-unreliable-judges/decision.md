---
title: "Intent: Exclude unreliable judges from aggregate score"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/survey/Core/exclude-unreliable-judges/survey.md"
  - "_docs/archives/plan/Core/exclude-unreliable-judges/plan.md"
  - "_docs/qa/Core/exclude-unreliable-judges/test-plan.md"
related_issues: []
related_prs: []
---

# Intent: Exclude unreliable judges from aggregate score

## Context

ベンチマーク結果の hero スコア（`average_score` / `best_score`）は、全 task × 全 judge 系統の
`total_score_mean` を単純平均している。一方、`ResultAggregator.aggregate_all_judges` と
`ResultDetail.computeReviewFlags` は、ばらつき（SD > 5）、低信頼、critical fail を検出して
警告表示するが、集計には反映しない。

利用者は「信頼できない judge 系統を総合点から外したスコア」も見たいが、現状は手動で
flags を読み取り再計算する必要がある。判定条件は frontend / backend で SD 閾値は一致するが、
judge 間乖離は未実装である。

## Decisions

### DEC-001: 除外単位は judge 系統（モデル ID）とし、task 内で 1 回でも信頼性 flag を満たせば系統全体を除外する

- **What**: 除外判定の粒度は task × judge 評価単位とし、同一 judge 系統が複数 task で
  flag を持つ場合、その系統の **全 task スコア** を横断集計から除外する。
- **Why**: `computeReviewFlags` が task × judge 単位で理由を出しており、UI の警告と
  集計除外の対象を一致させると利用者が追跡しやすい。judge 系統単位の平均だけを外すより、
  「この judge は信頼できない」という解釈に合う。
- **Change freedom**: 将来 task 単位の部分除外が必要なら、系統内サブセット除外へ拡張できる。
  初版は系統全体除外に限定する。
- **Why not**: task ごとに系統の一部だけ残すと、hero スコアの意味（どの judge が含まれたか）が
  読み手ごとに異なり、再現説明が難しくなる。

### DEC-002: 除外基準と閾値は単一モジュールに固定し、frontend / backend が同じ理由コードを使う

- **What**: 以下の条件の **いずれか** で judge 系統を除外候補とする。閾値は定数として集中管理する。

  | 理由コード | 条件 |
  | --- | --- |
  | `high_variance` | いずれか task × judge で `total_score_std > 5` |
  | `low_confidence` | いずれか task × judge で `confidence_distribution.low > 0` |
  | `critical_fail` | いずれか task × judge で `critical_fail == true` |
  | `cross_judge_divergence` | 同一 task で judge 間 `total_score_mean` の range > 15 |

- **Why**: Survey で確認したとおり、SD > 5 と low confidence / critical fail は既存警告と整合する。
  cross-judge divergence は新規だが、Inbox 要件と利用者の「judge 間乖離」期待に対応する。
  magic number 散在を避ける。
- **Change freedom**: 閾値（5 / 15）や理由コードの表示文言は、定数モジュール 1 箇所変更で
  更新できる。新しい理由コードの追加は可能。
- **Why not**: frontend のみで再計算すると保存 JSON と hero スコアがずれ、API consumer が
  一貫した値を得られない。

### DEC-003: toggle 状態は run 時に確定し、結果 JSON に保存する

- **What**: `RunRequest.exclude_unreliable_judges`（default `false`）を run 開始時に受け取り、
  保存 JSON の top-level に記録する。再表示時は保存値を正とし、同じ raw task データから
  集計を再現する。
- **Why**: AC-005 の一貫性と `runHolistic` 先例に合わせ、run 再現性を優先する。
- **Change freedom**: 結果画面で「what-if 表示」（保存 toggle を変えずに一時的に再計算 preview）
  は追加 UI として載せられるが、保存スコアは run 時 toggle に従う。
- **Why not**: 閲覧時のみ toggle だと、同じ run ID を開いた人によって hero スコアが変わり、
  ダッシュボード比較の正典が失われる。

### DEC-004: 全 judge 系統が除外対象のとき hero スコアは `null`（N/A）とし 0 を返さない

- **What**: 有効な judge 系統スコアが 0 件のとき `average_score` / `best_score` は `null` とし、
  UI は N/A 表示 + 全除外警告を出す。`0` や空平均のサイレント返却を禁止する。
- **Why**: 0 点は「全 judge が 0 点採点した」意味と混同される。AC-004 の明示要求。
- **Change freedom**: UI の N/A 表現（`—`、`N/A`、警告色）は変更可能。
- **Revisit when**: 除外 OFF かつ全 task 失敗など、別経路で N/A が必要になった場合。

## Consequences / Impact

- 保存 JSON に `exclude_unreliable_judges`、`score_aggregation`（除外前後・除外 judge 一覧）が
  additive に増える。
- frontend `EvaluationRun` 型と ResultDetail hero / JudgeSummary が N/A と除外メタを扱う。
- 既存 run（フィールドなし）は OFF 相当。hero スコアは現行値のまま。

## Quality Implications

- backend unit test で各理由コード、toggle OFF 回帰、全除外 N/A を検証する。
- frontend で toggle 表示と除外理由が `computeReviewFlags` と矛盾しないことを確認する。
- cross-judge divergence の閾値 15 は代表 run で sanity check する（QA manual）。

## Intent-derived Invariants

- INV-001 (from DEC-004): 除外 ON で有効 judge スコアが 0 件のとき、hero スコアは数値 0 ではなく
  N/A（null）である。
- INV-002 (from DEC-002): 除外理由コード集合は backend 定義が正であり、frontend は表示のみ
  変換する（条件の二重定義をしない）。

## Rollback / Follow-ups

- rollback は toggle、集計分岐、`score_aggregation` フィールド生成を除去する。
  保存済み JSON の unknown field は無視可能。
- 閾値調整は Intent 更新 + 定数変更で行い、過去 run の保存 hero スコアは再計算しない
  （再現性優先）。
