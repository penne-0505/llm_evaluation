---
title: Result Score Indicator Normalization
status: proposed
draft_status: n/a
created_at: 2026-04-04
updated_at: 2026-04-04
references:
  - _docs/plan/Core/llm_benchmark_app.md
related_issues: []
related_prs: []
---

## Overview
- Result 画面の各評価軸インジケーターは、task type ごとの配点上限に合わせて正規化して表示する。

## Scope
- `ResultDetail` の `Logic & Fact`、`Constraint`、`Helpfulness`、`Total` のバー表示と色分け。

## Non-Goals
- judge の採点ロジックや配点自体の変更。
- Dashboard 全体の配色ルール変更。

## Requirements
- **Functional**:
  - `fact` は `60 / 30 / 10`、`creative` は `30 / 30 / 40`、`speculative` は `40 / 20 / 40` を各軸の満点として扱う。
  - `Total` は引き続き 100 点満点で表示する。
  - 軸バーの色分けと幅は、各軸の実得点をその満点で割った割合に基づいて決める。
- **Non-Functional**:
  - UI 上で「低スコアに見えるだけの満点差」が起きないこと。

## Tasks
- `ResultDetail` に task type ごとの軸配点テーブルを追加する。
- `ScoreBar` を満点可変の正規化表示へ変更する。

## Test Plan
- `fact` / `creative` / `speculative` それぞれで、満点付近の軸が十分な長さと高評価色で表示されることを確認する。
- `npm run build` で型エラーがないことを確認する。

## Deployment / Rollout
- 通常のフロントエンド更新として配布する。
