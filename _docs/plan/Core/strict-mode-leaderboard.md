---
title: Strict Mode Leaderboard
status: active
draft_status: n/a
created_at: 2026-04-04
updated_at: 2026-04-04
references: []
related_issues: []
related_prs: []
---

## Overview
- Strict Mode leaderboard を成立させるための前提条件、保存要件、表示要件を定義する。
- 実装として、Settings から `Standard` / `Strict` を切り替え、`Strict` 選択時は official preset を強制する。
- Dashboard の leaderboard 集計対象は `requested: true` かつ `enforced: true` の run のみに限定する。

## Scope
- Strict Mode の判定条件
- ランキング集約単位と比較条件
- 必要な保存メタデータ
- UI と運用ポリシーの最低要件

## Non-Goals
- 公開 API や認証機構の本実装
- 外部公開サイトの運用設計

## Requirements
- **Functional**:
  - Strict Mode run は official preset によって task set、judge set、judge runs、temperature、resource version が固定されていること。
  - official preset:
    - `task_ids`: `01..11`
    - `judge_models`: `openrouter/anthropic/claude-sonnet-4.6`, `openrouter/openai/gpt-5.4`, `openrouter/google/gemini-3.1-pro-preview`
    - `judge_runs`: `3`
    - `subject_temperature`: `0.6`
    - `judge_temperature`: `0.0`
  - Settings UI では strict 選択時に上記設定を lock 表示すること。
  - backend は strict request を実行前に再検証し、条件を満たさない場合は run を開始しないこと。
  - leaderboard 集計対象には、再現に必要な run metadata を保存すること。
  - 表示上は score、variability、subject-side cost efficiency を比較できること。
- **Non-Functional**:
  - 後から監査できるよう、Strict Mode 判定理由と resource version を追跡可能にすること。

## Tasks
- Strict Mode を判定する run metadata スキーマを定義する。
- official preset を API / frontend store / Settings UI に通す。
- leaderboard 集計の grouping / sorting ルールを `enforced strict` 前提に変更する。
- UI の最小要件と公開時の注意事項を整理する。

## Test Plan
- `profile_id` が subject model に依存しないことを unit test で検証する。
- strict parameter mismatch が violation として検出されることを unit test で検証する。
- official preset API が期待値を返すことを API test で検証する。
- 結果サマリーへ strict metadata が保存されることを storage test で検証する。

## Deployment / Rollout
- 結果保存と Dashboard 表示は後方互換で追加し、旧結果は summary rebuild 時に strict metadata を補完する。
- 旧 `eligible` ベースの run は `requested/enforced` を持たないため、formal leaderboard からは外れる。
