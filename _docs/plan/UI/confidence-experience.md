---
title: Confidence Experience
status: active
draft_status: n/a
created_at: 2026-04-04
updated_at: 2026-04-04
references:
  - _docs/draft/judge_sys_instruction.md
related_issues: []
related_prs: []
---

## Overview
- confidence の意味、見方、使い方を Result UI 上で伝わる形へ改善する。

## Scope
- confidence ガイド表示
- judge evaluation card の confidence 表現
- flagged reason の wording 調整

## Non-Goals
- confidence 算出ロジックそのものの変更
- judge system prompt の全面書き換え

## Requirements
- **Functional**:
  - high / medium / low の意味を UI 上で説明する。
  - confidence は「judge の自己申告的な確信度」であると明示する。
  - low confidence は自動失敗ではなく、再確認シグナルとして読めるようにする。
- **Non-Functional**:
  - 説明を増やしても Result 画面の主導線を邪魔しないこと。

## Tasks
- confidence guide block を追加する。
- judge evaluation card の confidence chips と補助文言を見直す。
- flagged wording を不必要に断定的でない表現へ調整する。

## Test Plan
- Result 画面で confidence の意味が high / medium / low の 3 段階として読めることを確認する。
- `npm run build` で UI が通ることを確認する。

## Deployment / Rollout
- 通常のフロントエンド更新として配布する。
