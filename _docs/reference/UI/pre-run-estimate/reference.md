---
title: "Reference: Pre-run cost and duration estimate"
status: active
draft_status: n/a
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/UI/pre-run-estimate/decision.md"
  - "_docs/plan/UI/pre-run-estimate/plan.md"
related_issues: []
related_prs: []
---

# Reference: Pre-run cost and duration estimate

Intent（なぜ）は `_docs/intent/UI/pre-run-estimate/decision.md`。本書は現行の計算仕様
（どう実装しているか／初期実装でどう置くか）だけを置く。式や定数の変更は Intent の
Change freedom の範囲なら、本書とコードを更新すればよい。

## Inputs

履歴サマリーから主に使うもの:

- `subjectModelId` / `targetModel`
- `taskCount`, `judgeCount`, `timestamp`
- `executionDurationMs`（wall-clock）
- `estimatedCostUsd`, `subjectEstimatedCostUsd`
- 任意: `timingSummary.judge_duration_ms`
- 計画側: `subjectRunCount`, `judgeRunCount`, `totalSteps`

## Load units

計画側:

`L_plan = taskCount × (subjectRunCount + judgeCount × judgeRunCount)`

履歴側（run 回数が summary に無い間の仮定）:

`L_hist = taskCount_h × (1 + judgeCount_h)`

## Channels

| Channel | Value | Subject mismatch |
| --- | --- | --- |
| `subject_cost` | `subject_estimated_cost_usd`（無いとき同一被験の総額をレガシー代入） | weight 0（INV-002） |
| `judge_cost` | `estimated_cost_usd − subject_estimated_cost_usd`（欠損時はチャネル欠落） | soft `β` |
| `wall` | `executionDurationMs` | soft `γ > 0` |
| `judge_time`（optional prior） | 現行実装では未使用。wall 欠落時は heuristic | soft `β` |

単位レート: `r_i = value_i / L_hist`。合成後 `hat = r̂ × L_plan`。
コスト主値 = subject + judge。所要主値 = wall。

## Similarity weight (initial)

距離（現行と同じ軸）:

`d_i = |Δtask| + 2 · |Δjudge|`

重み:

`w_{i,c} = s_{i,c} · exp(-α d_i) · exp(-λ age_i)`

- `age_i`: 日数
- `r̂_c = Σ (w r) / Σ w`（分母 0 ならそのチャネル unavailable）

被験ゲート `s`:

- `subject_cost`: match 1 / mismatch **0**
- `judge_cost`, `judge_time`: mismatch `β`
- `wall`: mismatch `γ`（`γ > 0`）

初期定数（較正前提の仮置き）:

- `α = 0.35`
- 半減期 90 日 → `λ = ln 2 / 90`
- `β = 0.25`
- `γ = 0.1`

任意の説明用: `n_eff = (Σw)² / Σ(w²)`。追加の横断混合係数は必須としない。

## Fallbacks

- 有効なコスト合成ができない → cost unavailable（0 埋め禁止）
- wall を含む所要チャネルがすべて欠落 → `totalSteps × ASSUMED_MS_PER_STEP`（heuristic）

## Source labels

- `history` / `history_scaled` / `heuristic` / `unavailable`

（構成補正の有無や UI 文言は Intent DEC-005 の Change freedom 内で調整可）

## Code

- `frontend/src/lib/preRunEstimate.ts`
- tests: `frontend/src/lib/preRunEstimate.node.test.ts`
