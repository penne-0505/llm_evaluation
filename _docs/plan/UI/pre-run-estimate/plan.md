---
title: "Plan: Pre-run cost and duration estimate"
status: active
draft_status: n/a
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/UI/pre-run-estimate/decision.md"
  - "_docs/qa/UI/pre-run-estimate/test-plan.md"
  - "_docs/reference/UI/pre-run-estimate/reference.md"
related_issues: []
related_prs: []
---

# Plan: Pre-run cost and duration estimate

## Overview

Run 画面 idle で、開始前にだいたいの実行コストと所要（待ち時間）を提示する。
判断理由は Intent、計算仕様は reference に分離する。

## Scope

- `frontend/src/lib/preRunEstimate.ts` を単一最近傍から、Intent DEC-001..006 に沿う
  複数履歴合成へ置換（具体式は reference）。
- RunPage idle UI のラベル調整（必要なら）。
- node unit test の更新。
- Intent / reference / QA / verification の同期（UI-Enhance-64）。

## Non-Goals

- バックエンド新規見積 API、OpenRouter 価格のフロント取得。
- summary への judge コスト明示フィールド追加（差分近似で足りる間は後回し）。
- 包括評価の精密見積、並列フラグ照合、事後 CostSection / 実行中 ETA の定義変更。
- 定数のオンライン学習。

## Requirements

- Intent DEC-001..006 と INV-001 / INV-002 を満たす。
- 計算の置き方は `_docs/reference/UI/pre-run-estimate/reference.md` に従い、逸脱するなら
  reference を先に更新する。

## Tasks

1. Intent を Why 中心に薄くし、式を reference へ移す（本改訂）。
2. `preRunEstimate.ts` を reference 仕様で置換する。
3. node test を AC / INV に合わせて更新する。
4. RunPage idle 表示を必要なら調整する。
5. verification を再実行して書く。

## QA Plan

`_docs/qa/UI/pre-run-estimate/test-plan.md`

## Deployment / Rollout

frontend only。既存 result スキーマ変更なし。
