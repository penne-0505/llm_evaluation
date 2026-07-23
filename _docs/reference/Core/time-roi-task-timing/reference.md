---
title: "Reference: Time ROI and task timing"
status: active
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
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

## Time ROI denominator

- Definition: average score / (processing seconds), where processing seconds come from
  `timing_summary.total_duration_ms` (or the subject / judge slice on CostSection tabs).
- Shared frontend helpers: `frontend/src/lib/timeRoi.ts`.
- Legacy runs without `task_timing` / `timing_summary`: time ROI is **N/A** (no silent
  wall-clock fallback).

## Related APIs

- Backend: `core/cost_estimator.summarize_task_timing`
- Persist: `server.py` sets `timing_summary` on save; `ResultStorage._build_summary` indexes it
- Frontend: `ResultDetail` CostSection, `DashboardPage` aggregates
