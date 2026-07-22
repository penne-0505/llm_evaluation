---
title: "Decision: Retire legacy UI temporary documentation"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/Workflow/docs-template-v1-migration/decision.md"
  - "_docs/qa/Workflow/docs-template-v1-migration/test-plan.md"
  - "_docs/archives/draft/UI/legacy-documentation-retirement/dashboard_implementation.md"
  - "_docs/archives/draft/UI/legacy-documentation-retirement/ui-rebuild-feature-inventory.md"
  - "_docs/archives/plan/UI/legacy-documentation-retirement/UI-Feature-15-dashboard.md"
  - "_docs/archives/plan/UI/legacy-documentation-retirement/UI-Feature-15-Ext-dashboard-enhancement.md"
  - "_docs/archives/plan/UI/legacy-documentation-retirement/confidence-experience.md"
  - "_docs/archives/plan/UI/legacy-documentation-retirement/dashboard-roi-and-variability.md"
  - "_docs/archives/plan/UI/legacy-documentation-retirement/model-selection-ui.md"
  - "_docs/archives/plan/UI/legacy-documentation-retirement/result-score-indicator-normalization.md"
  - "_docs/archives/plan/UI/legacy-documentation-retirement/run-progress-kanban.md"
related_issues: []
related_prs: []
---

# Decision: Retire legacy UI temporary documentation

## Context

The UI shelf contains Streamlit-era dashboard documents and React-era plans
whose behavior is already represented in the current frontend. No UI plan is
referenced by active TODO work after the holistic progress task is separated
under Core.

## Decisions

### DEC-001: Keep legacy UI designs as history, not current instructions

- **What**: Archive the referenced UI drafts and plans with their original body
  content intact.
- **Why**: Old component names and layouts are useful provenance but conflict
  with the current React routes and components when left in live plan paths.
- **Change freedom**: Future UI work may reuse ideas after creating a structured
  TODO and a new plan; it need not restore the old file verbatim.

## Consequences / Impact

- Current UI behavior remains defined by implementation and durable references.
- The unresolved font asset contract remains separately tracked as `UI-Bug-33`.

## Quality Implications

- Archived UI docs must not retain broken local links to removed Streamlit files.
- No live/archive duplicate may remain.

## Intent-derived Invariants

- INV-001 (from DEC-001): Referenced UI temporary documents remain outside live
  draft/plan paths until an approved TODO reactivates their scope.

## Enforced in (optional)

- `_docs/archives/{draft,plan}/UI/legacy-documentation-retirement/`
- `_docs/qa/Workflow/docs-template-v1-migration/verification.md`

## Rollback / Follow-ups

- Reactivate individual ideas through TODO intake rather than restoring the
  entire historical UI shelf.
