---
title: "Intent: Official Strict Mode v3 + provider-flexible judges"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/archives/plan/Core/strict-mode-v3/plan.md"
  - "_docs/qa/Core/strict-mode-v3/test-plan.md"
related_issues: []
related_prs: []
---

# Intent: Official Strict Mode v3 + provider-flexible judges

## Context

v2 official preset は judge ID を `openrouter/...` に完全一致で固定していた。
adapter 層自体は provider prefix で任意ルートに振れるが、Strict 検証と UI が
OpenRouter ID を強制していた。公式 credit 利用と v3 judge セット更新のため、
比較条件は「どの upstream モデルか」に置き、ルート選択はユーザーに戻す。

## Decisions

### DEC-001: Official preset を v3（Kimi K3 / GPT-5.6 Terra / Qwen3.7 Max）へ更新

- **What**: `official-v3` を現行 official とし、preferred ID は
  `openrouter/moonshotai/kimi-k3`、`openrouter/openai/gpt-5.6-terra`、
  `openrouter/qwen/qwen3.7-max`。task set / runs / subject_temp は v2 と同値を維持。
- **Why**: leaderboard 比較セットを現行の強い judge 候補へ更新する。
- **Change freedom**: preferred provider 付き ID の表記。leaf 集合の意味は維持。

### DEC-002: Strict judge 適合は末尾セグメント（leaf id）の多重集合一致

- **What**: `a/b/c` の leaf は `c`。選択 judge の leaf 多重集合が preset と一致すれば eligible。
- **Why**: 同一 upstream を別 provider 経由で呼んでも比較条件を壊さない。
- **Change freedom**: 正規化（大小文字等）の細部。leaf 定義（最後の `/` 以降）は維持。
- **Why not**: 完全 ID 一致 — 公式ルートを Strict から排除してしまう。

### DEC-003: Strict UI は leaf 一致モデルだけを judge picker に出し、ルートを選択可能にする

- **What**: 固定チップ表示をやめ、catalog を leaf フィルタした multi picker にする。
  同一 leaf の別 ID を選んだら置換する。
- **Why**: ユーザーが API キーのある provider を選べるようにする。
- **Change freedom**: 初期選択の seed 規則（preferred → 既存一致 → 他候補）。

## Consequences / Impact

- 同一 leaf でも provider 差（レイテンシ・価格・挙動）は残り得る。profile は leaf 集合で共有。
- catalog に leaf 一致モデルが無いと Strict 開始条件を満たせない。

## Quality Implications

- leaf mismatch / match の unit、preset endpoint v3、frontend issues の回帰必須。

## Intent-derived Invariants

- INV-001 (from DEC-002): Strict eligible のとき、選択 judge の leaf 多重集合は
  official preset の leaf 多重集合と一致する。

## Rollback / Follow-ups

- rollback: preset と検証を v2 完全 ID 一致へ戻す。
- follow-up: Dashboard で provider 内訳の可視化。
