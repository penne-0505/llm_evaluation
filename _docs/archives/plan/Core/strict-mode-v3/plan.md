---
title: "Plan: Official Strict Mode v3 + provider-flexible judges"
status: completed
draft_status: n/a
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/Core/strict-mode-v3/decision.md"
  - "_docs/qa/Core/strict-mode-v3/test-plan.md"
  - "_docs/qa/Core/strict-mode-v3/verification.md"
related_issues: []
related_prs: []
---

# Plan: Official Strict Mode v3 + provider-flexible judges

## Overview

official strict preset を v3 に更新し、judge を Kimi K3 / GPT-5.6 Terra / Qwen3.7 Max にする。
Strict 適合判定は model ID の末尾セグメント一致とし、UI では一致するモデルだけを
picker に出し、プロバイダルートはユーザーが選ぶ。

## Scope

- `core/strict_mode.py` preset v3 + leaf-id 検証
- Settings Strict judge UI（固定チップ → フィルタ付き picker）
- frontend `getStrictModeIssues` / store の strict 時 judge 更新
- README / tests

## Non-Goals

- v2 leaderboard 結果の再集計・移行
- holistic judge の strict 固定
- モデル catalog への自動同期

## Requirements

- AC-001..004（Intent / QA test-plan 参照）

## Tasks

1. Intent / QA
2. core leaf match + v3 preset
3. frontend picker / issues / store
4. tests + verification + README

## QA Plan

`_docs/qa/Core/strict-mode-v3/test-plan.md`
