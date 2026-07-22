---
title: "QA Test Plan: Docs-driven template v1.0.0 migration"
status: active
draft_status: n/a
qa_status: planned
risk: High
qa_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/Workflow/docs-template-v1-migration/decision.md"
  - "_docs/plan/Workflow/docs-template-v1-migration/plan.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Docs-driven template v1.0.0 migration

## Source of Intent

- TODO: `Workflow-Chore-30`
- Plan: `_docs/plan/Workflow/docs-template-v1-migration/plan.md`
- Intent: `_docs/intent/Workflow/docs-template-v1-migration/decision.md`

## Quality Goal

Adopt U as an operational, provenance-locked docs workflow without changing the
checkpointed application or silently losing project customizations.

## Acceptance Criteria

- AC-001: B and U full SHAs, tag resolution, and matching B tree IDs are recorded.
- AC-002: Raw upstream/project deltas and a complete resolution/disposition map
  have zero missing or duplicate paths.
- AC-003: Project application source, tests, runtime/build inputs, assets, and
  project docs are preserved, including `frontend/src/components/ResultDetail.tsx`.
- AC-004: Scoped compatibility docs checks pass with ACMR; exactly 29
  markdownlint-only legacy documents are skipped only at their recorded blobs,
  and unscoped strict results are recorded separately and are not misreported
  as compatibility failures.
- AC-005: Front-matter fixtures reject unknown fields, wrong types, duplicate
  keys, and schema markers on the wrong document type.
- AC-006: Full CI-equivalent markdownlint, validator fixtures, hook tests, hook
  smoke, and paired-skill comparison pass.
- AC-007: Available backend tests, frontend tests/lint/typecheck/build, and
  launcher/runtime smoke are executed; any baseline failures are proven
  unchanged by the migration and reported separately.
- AC-008: No template-self lifecycle history or stale legacy agent guidance is
  active; any retained obsolete content is quarantined and reported.
- AC-009: The exact U lock is the final migration write and verifies against the
  upstream tag after reconciliation.

## Decision Review Scope

- DEC-001: Verify immutable B/U provenance and final lock.
- DEC-002: Verify inventory completeness and project preservation.
- DEC-003: Verify compatibility and strict-schema verdict separation.
- DEC-004: Verify exclusions and quarantine stay non-operational.

## Intent-derived Invariants

- INV-001: Lock tag and full commit match reconciled U.
- INV-002: Every raw delta path has one resolution and disposition.
- INV-003: Checkpointed application/runtime content remains unchanged.

## Risk Assessment

- Risk level: High
- Risk rationale: Workflow, CI, validators, hooks, provenance, and migration.
- Regression risk: Shared root/docs files may overwrite project guidance.
- Data safety risk: Permanent deletion or lost project documentation.
- Security / privacy risk: Hook and CI imports execute upstream code.
- UX risk: Application behavior may change if runtime files drift.
- Agent misbehavior risk: Branch mixing, blind replacement, premature lock
  advancement, bulk schema edits, or treating compatibility as strict PASS.

## Test Strategy

- Unit: Deno validator fixtures and Python/frontend tests.
- Integration: docs wrapper, hook tests, paired skills, frontend build.
- E2E: launcher/API smoke with local-only resources.
- Manual QA: inventory, provenance, diff, active guidance, quarantine.
- Validator / static check: scoped/unscoped validators and markdownlint.
- Diff review: compare P to child commit and hash preserved runtime paths.

## Test Matrix

| ID | Source | Requirement / Optional Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 / INV-001 | Intent | Immutable provenance | static | `git show`, `git tag --points-at`, lock review | B trees equal; U tag/SHA match | planned |
| AC-002 / INV-002 | Intent | Path-complete inventory | script | inventory coverage comparison | zero missing/duplicates | planned |
| AC-003 / INV-003 | Intent | Runtime preservation | diff/hash/tests | `git diff P --` and project suites | no unintended application diff | planned |
| AC-004 | Plan | Blob-pinned compatibility/strict split | validator | scoped `check-docs.sh`; `scripts/test-validators.mjs` | Current 29 blobs skip; a changed blob and invalid manifest fail closed | planned |
| AC-005 | TODO | Schema marker and parser rejection | fixture | `scripts/test-validators.mjs` | all negative fixtures fail as expected | planned |
| AC-006 | TODO | Workflow tooling integrity | CI/static | markdownlint, hooks, paired diff | lint runs under the U-derived policy with no migration-local exemptions; hook/paired checks pass | planned |
| AC-007 | TODO | Project regression | test/build/smoke | project commands | available suites pass | planned |
| AC-008 | Intent | Active guidance boundary | inventory | file/reference scan | excluded or quarantined paths inactive | planned |
| AC-009 / INV-001 | Intent | Final lock write | diff/provenance | lock and final diff review | lock exact and last write | planned |

## Manual QA Checklist

- [ ] Review all customized shared root files.
- [ ] Confirm excluded lifecycle history is absent.
- [ ] Confirm quarantine contains only exact obsolete paths.
- [ ] Confirm no post-cutoff or unrelated repository changes are included.

## Regression Checklist

- [ ] `ResultDetail.tsx` matches P byte-for-byte.
- [ ] Backend/frontend project suites and build pass.
- [ ] README remains project-specific.
- [ ] Existing Inbox items remain present.

## High-risk Checklist

- [ ] Rollback or recovery path is documented.
- [ ] Data safety has been checked.
- [ ] Security / privacy implications have been checked.
- [ ] Failure mode is understood.

## Out of Scope

- Repository-wide semantic conversion of legacy project docs.
- Push, main movement, deployment, or application feature changes.

## Open Questions

- None; B/P/U and isolated-worktree authority are owner-approved.
