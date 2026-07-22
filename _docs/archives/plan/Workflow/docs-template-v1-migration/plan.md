---
title: "Plan: Docs-driven template v1.0.0 migration"
status: superseded
draft_status: n/a
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/Workflow/docs-template-v1-migration/decision.md"
  - "_docs/qa/Workflow/docs-template-v1-migration/test-plan.md"
related_issues: []
related_prs: []
---

# Plan: Docs-driven template v1.0.0 migration

## Overview

The project is migrated from the legacy template baseline
`afa6de706dd6787b4ed5dc1edb9112ac84c7211d` to the pinned `v1.0.0`
release `f71e9ab20466ea2972158334261f5ae2b2265754`. The matching tree IDs of
the project initial commit and upstream baseline establish provenance without
assuming unrelated commit ancestry.

Work tracking is `Workflow-Chore-30` in `TODO.md`. The compatibility adoption
is verified separately from the remaining repository-wide strict migration and
the pre-existing backend baseline failures.

The owner has now authorized the strict closure phase. Historical documents
that describe Streamlit or otherwise superseded behavior remain historical;
they are archived with explicit retirement rationale instead of being rewritten
to resemble the current React/FastAPI implementation.

This plan was archived after the strict closure recorded a PASS and
`Workflow-Chore-30` was removed from active TODO work.

## Scope

- Freeze project cutoff P at `d309974a77c736b6d333819a38460edaeb21e57e`.
- Reconcile the B to U upstream delta with the B to P project delta.
- Import standards, validators, fixtures, paired skills, hooks, and docs CI.
- Preserve project application code, runtime behavior, tests, build files,
  assets, and project documentation.
- Record the final provenance lock only after compatibility checks pass.
- Complete the owner-approved repository-wide frontmatter/link/intent cleanup.
- Archive legacy, completed, and unscheduled temporary docs under canonical
  retirement intents, leaving live temporary docs only for active TODO work.
- Remove the compatibility scope after unscoped validators pass.
- Make the documented backend test command runnable from the locked project
  environment and document the root runtime-prompt exception.

## Non-Goals

- No application feature or runtime behavior changes beyond development-test
  dependency metadata needed by the documented regression command.
- No push, main update, or inclusion of post-cutoff work.
- No modernization of historical requirements, plans, or drafts to current UI
  architecture; archival metadata and references may be added.
- No import of upstream template lifecycle implementation history or
  template-archive packaging behavior.

## Requirements

- Every path in the raw B to U and B to P deltas has an upstream status,
  project relation, allowed resolution, and separate final disposition.
- CI uses `DD_SCOPE_DIFF_FILTER=ACMR` and the project cutoff as scope base.
- Compatibility and strict-schema results remain separate.
- Front-matter fixtures cover unknown keys, wrong types, duplicate keys, and
  type-specific schema markers.
- Full markdownlint, docs checks, hooks, paired skills, project tests,
  frontend lint/typecheck/build, and runtime smoke are executed when available.
- Unscoped docs checks pass before the compatibility env is removed from CI.
- Every archived temporary document resolves to an active retirement intent,
  and no live/archive duplicate remains.
- `uv sync` installs everything required by `uv run pytest`.
- Full markdownlint must use the retained U-derived policy without migration-
  local markdownlint exemptions and pass after semantics-preserving local
  fixes are inventoried.
- The compatibility scope starts with paths added, copied, modified, or renamed
  from P `d309974a77c736b6d333819a38460edaeb21e57e` while
  `DD_SCOPE_DIFF_FILTER=ACMR` is configured. The 29 legacy paths recorded in
  `artifacts/markdownlint-compatibility-baseline.tsv` are excluded only while
  their current Git blob equals their recorded post-remediation blob. Any
  content change, rename, deletion, or manifest mismatch re-enters ACMR
  validation. This support horizon remains until an owner-approved
  repository-wide strict frontmatter/link/intent migration records a PASS and
  explicitly replaces the compatibility policy.

## Tasks

- [x] Capture raw upstream and project deltas and build the path inventory.
- [x] Create migration Intent and QA test plan.
- [x] Integrate U path by path while preserving project customizations.
- [x] Quarantine only obsolete active guidance that cannot be deleted safely.
- [x] Run compatibility, strict, project, preservation, and diff checks.
- [x] Write verification and update the lock as the final migration write.
- [x] Add retirement intents and canonical metadata for legacy temporary docs.
- [x] Move non-active drafts/plans to archives and repair every reference.
- [x] Remove CI compatibility scope and verify the unscoped workflow.
- [x] Align the canonical backend test command with project dependency metadata.

## QA Plan

- QA document: `_docs/qa/Workflow/docs-template-v1-migration/test-plan.md`
- Risk level: High
- Test strategy:
  - Unit: validator fixtures and project test suites.
  - Integration: docs wrapper, hook tests, paired-skill comparison, build.
  - E2E: launcher/runtime smoke without external credentials.
  - Manual QA: path inventory, provenance, quarantine, and diff review.
  - Validator / static check: scoped and unscoped docs plus markdownlint.
- Review DEC-001 through DEC-004 against preservation and provenance evidence.
- Review DEC-005 through DEC-007 against archive discoverability, strict CI,
  and reproducible project checks.
- Keep `Workflow-Chore-30` open while unscoped strict schema/link/intent and
  backend baseline failures remain unresolved.

## Deployment / Rollout

The migration is committed as one child of P on an isolated branch. It is not
pushed and does not update `main`. Recovery is deletion of the isolated
worktree/branch by the owner; the original detached checkout remains at P.
