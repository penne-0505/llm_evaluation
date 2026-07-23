---
title: "QA Test Plan: Docs-driven template v1.1.0 migration"
status: active
draft_status: n/a
qa_schema: 2
qa_status: planned
risk: High
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/Workflow/docs-template-v1-1-migration/decision.md"
  - "_docs/archives/plan/Workflow/docs-template-v1-1-migration/plan.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Docs-driven template v1.1.0 migration

## Source of Intent

- Intent: `_docs/intent/Workflow/docs-template-v1-1-migration/decision.md`
- Plan: `_docs/archives/plan/Workflow/docs-template-v1-1-migration/plan.md`
- TODO: `Workflow-Chore-62`

## Decision Review Scope

- DEC-001 through DEC-006
- INV-001, INV-002

## Quality Goal

Prove that `v1.1.0` TypeScript validators/hooks are integrated without losing
project customizations, without importing template-self meta-work, and with a
provenance lock that matches the integrated release.

## Acceptance Criteria

- AC-001: Path inventory covers every `B→U` path with relation, resolution, and
  disposition.
- AC-002: Active `scripts/check-docs.sh` runs `.ts` entrypoints and
  `deno fmt`/`deno check` over `scripts/*.ts`.
- AC-003: Project frontmatter fixtures (duplicate/unknown/wrong-type/schema
  placement) still pass under TypeScript validators.
- AC-004: Direct `docs-template.lock.json` smoke assertions remain; example lock
  file is not required.
- AC-005: Template lifecycle-self-audit docs and lock example are absent from
  the live tree.
- AC-006: Superseded `.mjs` validators are quarantined, not permanently deleted.
- AC-007: After compatibility PASS, lock tag/commit equal `v1.1.0` /
  `9f4503030bd42521541a951adc79fe3aa40823c3`.
- AC-008: Agent misbehavior checks fail closed for premature lock advance,
  branch-tip pinning language, and blind customized-file replacement in the
  recorded review.

## Intent-derived Invariants

- INV-001: Provenance lock equals integrated U.
- INV-002: Active docs entrypoints are TypeScript.

## Risk Assessment

- **Risk**: High
- **Why**: Validators, hooks, CI wrapper, and agent skill contracts change
  together; customization loss would silently weaken docs enforcement.
- **Mitigations**: Three-way inventory, baseline capture, fixture suite,
  quarantine instead of delete, lock-last write order.

## Test Strategy

- Unit: validator fixtures and hook unit tests.
- Integration: `./scripts/check-docs.sh`, paired skill path comparison.
- Manual / diff review: inventory, quarantine manifest, lock contents,
  customized-file merges.
- Agent misbehavior: review notes against DEC-001/002/004/006 failure modes.

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | Inventory complete | diff review | `artifacts/path-inventory.tsv` | 44 paths classified | verified |
| AC-002 | TODO / INV-002 | TS entrypoints | static check | `scripts/check-docs.sh` | `.ts` invocations only | verified |
| AC-003 | TODO | Frontmatter fixtures | automated | `./scripts/check-docs.sh` | frontmatter fixture PASS lines | verified |
| AC-004 | DEC-004 | Direct lock smoke | automated | `scripts/test-agent-workflow-smoke.ts` | lock.json assertions PASS | verified |
| AC-005 | DEC-004 | No template-self import | diff review | live tree paths | lifecycle-self-audit / lock.example absent | verified |
| AC-006 | DEC-005 | Quarantine not delete | diff review | `.migration-quarantine/` | mjs retained outside active scripts | verified |
| AC-007 | INV-001 | Lock equals U | static check | `docs-template.lock.json` | tag+SHA match U | verified |
| AC-008 | TODO | Agent misbehavior | manual QA | verification notes | no tip-pin / blind replace / early lock | verified |
| INV-001 | Intent | Lock integrity | static check | lock + `git ls-remote` | SHA still peels from tag | verified |
| INV-002 | Intent | TS active path | static check | `check-docs.sh` + absence of active mjs validators | no active mjs validators on CI path | verified |

## Manual QA Checklist

- [x] Confirm working tree cutoff evidence vs post-cutoff edits.
- [x] Review customized merges for QUICKSTART, documentation_operations,
      frontmatter, smoke, and doc-links.
- [x] Confirm quarantine manifest lists every superseded `.mjs`.

## Regression Checklist

- [x] Compare post-migration `./scripts/check-docs.sh` to
      `artifacts/check-docs-baseline.log`.
- [x] Confirm markdownlint still uses existing project globs/config.

## High-risk Checklist

- [x] Rollback or recovery path is documented.
- [x] Data safety has been checked (quarantine, no permanent deletion).
- [x] Security / privacy implications have been checked (imported scripts reviewed).
- [x] Failure mode is understood (premature lock / blind replace / tip pin).

## Out of Scope

- Application pytest / frontend build regressions unrelated to docs tooling.
- Repository-wide strict schema conversion.

## Open Questions

- None remaining after owner approved `main` + `v1.1.0`.
