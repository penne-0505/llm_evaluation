---
title: "Plan: Pre-run cost and duration estimate"
status: active
draft_status: n/a
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/UI/pre-run-estimate/decision.md"
  - "_docs/qa/UI/pre-run-estimate/test-plan.md"
related_issues: []
related_prs: []
---

# Plan: Pre-run cost and duration estimate

## Overview

Run 画面 idle で、開始前に「だいたいの実行コスト」と「だいたいの所要（待ち時間）」を
提示する。履歴（同一被検）を優先し、タスク数・judge 数・run 回数の差は構成ベースで
補正する。履歴が無い場合のみ粗い構成ヒューリスティックに落とす。

## Scope

- フロントエンドの見積 helper（履歴マッチ・負荷補正・ヒューリスティック）。
- RunPage idle UI に見積カードを追加。
- `historyStore` のサマリー（`executionDurationMs` / `estimatedCostUsd` / task・judge 数）を入力にする。
- node unit test。

## Non-Goals

- バックエンド新規見積 API、OpenRouter 価格のフロント取得。
- 包括評価フェーズの精密見積（軽い注記に留めるか無視）。
- 並列 ON/OFF フラグの履歴照合（summary に無い）。
- 事後 CostSection / 実行中 ETA の定義変更。

## Requirements

- 被検モデル一致を履歴マッチの必須条件とする。
- 所要の正典は wall-clock（`executionDurationMs`）。
- コストは履歴の `estimatedCostUsd`（partial 可）。無い・不明は N/A（0 埋め禁止）。
- 構成差は負荷ユニット比で補正し、ラベルで明示する。
- 履歴無しの所要は step 数ベースの粗い推定。コストは単価情報無しなら N/A。

## Tasks

1. Intent / QA を固定する。
2. `frontend/src/lib/preRunEstimate.ts` と node test を追加する。
3. RunPage idle にカードを接続し `historyStore.initialize` する。
4. verification を書く。

## QA Plan

`_docs/qa/UI/pre-run-estimate/test-plan.md`

## Deployment / Rollout

frontend only。既存 result スキーマ変更なし。
