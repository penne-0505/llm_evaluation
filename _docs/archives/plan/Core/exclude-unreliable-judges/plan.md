---
title: "Plan: Exclude unreliable judges from aggregate score"
status: archived
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/survey/Core/exclude-unreliable-judges/survey.md"
  - "_docs/intent/Core/exclude-unreliable-judges/decision.md"
  - "_docs/qa/Core/exclude-unreliable-judges/test-plan.md"
related_issues: []
related_prs: []
---

# Plan: Exclude unreliable judges from aggregate score

## Overview

現状、全 task × 全 judge 系統の `total_score_mean` を単純平均して `average_score` を出す。
`ResultAggregator.aggregate_all_judges` と `ResultDetail.computeReviewFlags` はばらつき・低信頼・
critical fail を **警告として表示するのみ** で、集計からは除外しない。

本変更は、包括評価 `runHolistic` と同型の toggle で「信頼性の低い judge 系統を総合得点から除外」
モードを切り替え、除外理由と除外前後のスコアを結果 UI で追跡可能にする。

## Scope

- 信頼性判定ルールを backend 単一モジュールに集約し、`ResultAggregator` から参照する。
- `RunRequest` / 保存 JSON / frontend 設定に `exclude_unreliable_judges` toggle を追加する。
- `server.py` の `average_score` / `best_score` 算出に除外ロジックを適用する。
- `ResultDetail` に toggle UI、除外 judge 一覧、除外前後スコア、N/A 表示を追加する。
- `computeReviewFlags` と backend 除外理由の文言・条件を整合させる。
- cross-judge 乖離判定（同一 task の judge mean 差）を新規追加する。
- backend unit test（除外・全除外・toggle OFF 回帰）を追加する。

## Non-Goals

- judge プロンプト、ルーブリック、個別 run の再採点を変更しない。
- 除外された judge の task 別詳細スコアを UI から隠さない（横断集計のみ除外）。
- 機械学習ベースの信頼性推定や動的閾値学習を導入しない。
- holistic task を hero `average_score` に含める変更は行わない（現行維持）。

## Requirements

- **Functional**
  - toggle OFF: 現行どおり全 judge 系統を平均に含める。
  - toggle ON: Intent で定義した基準に該当する judge 系統を `average_score` / `best_score`、
    `computeJudgeSummaries` から除外する。
  - 除外 judge・理由・除外前後スコアを結果詳細で表示する。
  - 全 judge 除外時はスコア N/A と警告（0 点や空平均を出さない）。
  - 保存済み run 再表示で toggle 状態と再計算結果が一貫する。
- **Non-Functional**
  - 閾値は Intent / 定数モジュールに集約し magic number を散在させない。
  - 既存結果 JSON（toggle フィールドなし）は OFF 相当として読み込める。

## Tasks

1. Intent の DEC と閾値定数を確定する。
2. `core/judge_reliability.py`（仮）に除外判定と理由生成を実装する。
3. `ResultAggregator.aggregate_all_judges` を拡張し、除外メタデータを返す。
4. `server.py` の run 保存時・結果 API で toggle 反映した `average_score` / `best_score` を計算する。
5. frontend: Run 設定 toggle、ResultDetail 横断サマリー、除外理由表示を追加する。
6. `computeReviewFlags` と backend 理由コードのマッピングを共通化する。
7. backend test と docs validator を実行し、verification を記録する。

## QA Plan

- Risk: Medium。集計ロジックと UI 表示が対象で、judge 実行意味論は対象外。
- `AC-001`〜`AC-005` は `_docs/qa/Core/exclude-unreliable-judges/test-plan.md` の Test Matrix に
  対応付ける。
- `DEC-001`〜`DEC-004` は verification で閾値・永続化・N/A 契約を review する。

## Deployment / Rollout

- API consumer は bundled frontend のみ。`RunRequest` と結果 JSON への additive field のため
  段階 rollout は不要。
- 旧 frontend は toggle 未送信 → backend default OFF。旧結果 JSON は OFF として表示。
- rollback は toggle UI と集計分岐を戻すだけでよく、migration は不要。
