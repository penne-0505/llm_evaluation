---
title: "Plan: Docs-driven template v1.0.0 migration"
status: active
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

## Scope

- Freeze project cutoff P at `d309974a77c736b6d333819a38460edaeb21e57e`.
- Reconcile the B to U upstream delta with the B to P project delta.
- Import standards, validators, fixtures, paired skills, hooks, and docs CI.
- Preserve project application code, runtime behavior, tests, build files,
  assets, and project documentation.
- Record the final provenance lock only after compatibility checks pass.

## Non-Goals

- No application feature or runtime behavior changes.
- No push, main update, or inclusion of post-cutoff work.
- No bulk conversion of legacy project documents to strict schema v2.
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

- [ ] Capture raw upstream and project deltas and build the path inventory.
- [ ] Create migration Intent and QA test plan.
- [ ] Integrate U path by path while preserving project customizations.
- [ ] Quarantine only obsolete active guidance that cannot be deleted safely.
- [ ] Run compatibility, strict, project, preservation, and diff checks.
- [ ] Write verification and update the lock as the final migration write.

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
- Keep `Workflow-Chore-30` open while unscoped strict schema/link/intent and
  backend baseline failures remain unresolved.

## Deployment / Rollout

The migration is committed as one child of P on an isolated branch. It is not
pushed and does not update `main`. Recovery is deletion of the isolated
worktree/branch by the owner; the original detached checkout remains at P.
