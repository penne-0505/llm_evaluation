---
title: "Decision: Retire legacy DevOps temporary documentation"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/Workflow/docs-template-v1-migration/decision.md"
  - "_docs/qa/Workflow/docs-template-v1-migration/test-plan.md"
  - "_docs/archives/plan/DevOps/legacy-documentation-retirement/github-release-binary.md"
  - "_docs/archives/plan/DevOps/legacy-documentation-retirement/windows-local-browser-distribution.md"
related_issues: []
related_prs: []
---

# Decision: Retire legacy DevOps temporary documentation

## Context

Initial binary and Windows distribution plans have been superseded by the
verified Windows portable ZIP and Linux AppImage contracts.

## Decisions

### DEC-001: Prefer verified distribution contracts over initial release plans

- **What**: Archive the superseded DevOps plans and retain current distribution
  intent, guide, reference, workflow, and release verification as operational.
- **Why**: The initial plans name installer and binary shapes that were not the
  final release contract and should not be interpreted as pending work.
- **Change freedom**: New packaging formats may be proposed through TODO without
  changing the historical plan records.

## Consequences / Impact

- Windows portable ZIP and Linux AppImage remain the supported release forms.

## Quality Implications

- Release guides and references must not link to removed live plan paths.

## Intent-derived Invariants

- INV-001 (from DEC-001): The archived initial plans do not coexist with live
  copies under `_docs/plan/DevOps`.

## Enforced in (optional)

- `_docs/archives/plan/DevOps/legacy-documentation-retirement/`

## Rollback / Follow-ups

- Revisit distribution formats through a new TODO and decision record.
