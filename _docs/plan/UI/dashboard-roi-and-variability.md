---
title: Dashboard ROI And Variability
status: active
draft_status: n/a
created_at: 2026-04-04
updated_at: 2026-04-04
references: []
related_issues: []
related_prs: []
---

## Overview
- Dashboard に ROI 散布図を追加し、スコアだけでなくコスト効率も比較できるようにする。
- あわせて、モデル平均スコアの横に変動量を出し、複数 run の安定性を読めるようにする。

## Scope
- Result summary に subject 側 token/cost の軽量メタデータを持たせる。
- Dashboard に `Cost Efficiency` セクションを追加する。
- Summary / chart tooltip に `avg ± variability` を出す。

## Non-Goals
- judge 側コストを subject モデル価格へ混ぜて比較すること。
- 厳密な会計監査用途のコスト算出。

## Requirements
- **Functional**:
  - ROI 散布図は横軸 `average score`、縦軸 `subject cost per 1M tokens` とする。
  - Dashboard の集約表示では `avg` に加えて `±sd` を表示する。
  - subject 側価格が不明な run は ROI 散布図から除外し、欠損時メッセージを出す。
- **Non-Functional**:
  - Dashboard は結果詳細 JSON を大量に開かず、サマリー中心で描画できること。

## Tasks
- `ResultStorage` summary に subject token/cost 指標を追加する。
- API / client / history store に subject ROI 指標を通す。
- Dashboard に散布図と変動量表示を追加する。

## Test Plan
- summary 保存テストで subject token 指標が index に入ることを確認する。
- `npm run build` で Dashboard の型・描画コードが通ることを確認する。

## Deployment / Rollout
- 通常のフロントエンド更新として配布する。
