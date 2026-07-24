---
title: "Reference: Progress ETA wall-clock blend"
status: active
draft_status: n/a
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/Core/task-duration-eta/decision.md"
  - "_docs/plan/Core/run-eta-history-blend/plan.md"
  - "_docs/reference/UI/pre-run-estimate/reference.md"
related_issues: []
related_prs: []
---

# Reference: Progress ETA wall-clock blend

Intent（なぜ）は `_docs/intent/Core/task-duration-eta/decision.md` DEC-002。
履歴 wall チャネルの距離・減衰は pre-run reference と同系。

## Measured pace

`measured_remaining = (elapsed_ms / completed_task_count) × remaining_task_count`

## History prior

pre-run wall と同じ類似度重みで `execution_duration_ms / L_hist` をプールし、
`remaining_L = remaining_task_count × (L_plan / task_count)` を掛ける。

## Blend

`α(n) = n / (n + 0.1)`

両方が有るとき、履歴を `[measured/4, measured×4]` にクランプしてから

`eta = α · measured + (1−α) · history_clamped`

- `α ≥ 0.9` → `eta_status: measured`
- それ以外の両信号 → `history_blend`
- 履歴のみ → `history`
- step のみ → `step_fallback`

## Code

- `core/progress_eta.py`
- `server.py` `_compute_progress_eta`（run 開始時に `ResultStorage.list_summaries()` をキャッシュ）
