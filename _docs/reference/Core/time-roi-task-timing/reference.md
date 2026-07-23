---
title: "Reference: Time ROI and task timing"
status: active
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-24
references:
  - "_docs/intent/Core/time-roi-task-timing/decision.md"
  - "_docs/intent/Core/task-duration-eta/decision.md"
  - "_docs/qa/Core/time-roi-task-timing/verification.md"
related_issues: []
related_prs: []
---

# Reference: Time ROI and task timing

## Timing fields

| Field | Scope | Meaning |
| --- | --- | --- |
| `task_timing.subject_duration_ms` | per usual task | Subject processing time (usage `duration_ms`) |
| `task_timing.judge_duration_ms` | per usual task | Sum of judge-run usage `duration_ms` |
| `timing_summary` | run + summary index | Sum of usual-task `task_timing` (subject / judge / total) |
| `execution_duration_ms` | run + summary index | Wall-clock from run start to complete (metadata only for ROI) |

Holistic tasks are excluded from `timing_summary` (DEC-004).

## Time ROI

- **Formula (DEC-005)**: `(averageScore × taskCount) / (processing_ms / 60000)` → **点/分**
- Processing minutes come from `timing_summary.total_duration_ms` on Dashboard, or the
  subject timing slice for ResultDetail cost/time ROI on subject and total tabs (DEC-007).
  Judge tab does not show score-based ROI (DEC-006). Denominator rules: DEC-001 / DEC-003 /
  DEC-004 / DEC-007.
- Shared frontend helpers: `frontend/src/lib/timeRoi.ts` (`runScoreSum`, `computeTimeRoi`,
  `formatTimeRoi`).
- Dashboard aggregates timed runs as `Σ(averageScore×taskCount) / Σ(processing_ms)`.
- Legacy runs without `task_timing` / `timing_summary`: time ROI is **N/A** (no silent
  wall-clock fallback).
- **ResultDetail Judge tab (DEC-006)**: cost ROI / time ROI are shown as **対象外** (score
  numerator does not apply to judges). Card slots remain for layout stability; execution
  time still uses the judge timing slice.
- **ResultDetail total tab ROI (DEC-007)**: cost / time ROI denominators are **subject-only**
  (same values as the subject tab). Subs state that Judge is excluded. Estimated cost,
  tokens, and execution time on the total tab still show subject+judge totals.

## Related APIs

- Backend: `core/cost_estimator.summarize_task_timing`
- Persist: `server.py` sets `timing_summary` on save; `ResultStorage._build_summary` indexes it
- Frontend: `ResultDetail` CostSection, `DashboardPage` aggregates
