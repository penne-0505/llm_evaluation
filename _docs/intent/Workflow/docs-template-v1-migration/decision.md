---
title: "Decision: Docs-driven template v1.0.0 migration"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/plan/Workflow/docs-template-v1-migration/plan.md"
  - "_docs/qa/Workflow/docs-template-v1-migration/test-plan.md"
related_issues: []
related_prs: []
---

# Decision: Docs-driven template v1.0.0 migration

## Context

The repository began from a pre-release template snapshot and has no provenance
lock. Its initial root tree matches a known upstream commit exactly, while the
current project contains extensive application and documentation customizations.
`Workflow-Chore-30` tracks the compatibility migration and its remaining
verification boundaries.

## Decisions

### DEC-001: Establish B by root-tree identity

- **What**: Treat upstream `afa6de706dd6787b4ed5dc1edb9112ac84c7211d`
  as B because its tree `03b1b4b2465ecf56e922206c942dc74409c667d9`
  equals the tree of project initial commit
  `b4723d60e37b5dbf14eba6b96ec6d5feb8f87512`.
- **Why**: Tree identity proves identical adopted content without fabricating
  ancestry between independent repositories.
- **Change freedom**: Future migrations may use a prior lock or other immutable
  provenance evidence, provided B is not guessed from a moving reference.

### DEC-002: Preserve project state through a path-complete three-way inventory

- **What**: Classify the union of B to U and B to P paths independently, assign
  one allowed resolution and a separate disposition to each, and verify raw
  artifact coverage mechanically.
- **Why**: A project-customized shared path can be lost by blind upstream
  replacement even when application tests still pass.
- **Change freedom**: The artifact format and reconciliation tooling may change
  if path coverage and rationale remain auditable.

### DEC-003: Separate compatibility adoption from strict schema adoption

- **What**: Adopt U validators in legacy-compatible scoped mode, report the
  unscoped strict result separately, and do not bulk-edit existing project docs
  solely to obtain a strict-schema verdict. The 29 legacy documents changed
  only for markdownlint are excluded from ACMR scope solely when their current
  Git blobs match the checked-in compatibility baseline.
- **Why**: The workflow can become operational at U without converting
  historical project documents whose semantics were not reviewed in this task.
- **Change freedom**: Individual legacy documents may migrate when substantive
  edits justify semantic review, or a later owner-approved strict migration may
  convert them as a dedicated change. The baseline representation may change,
  but a legacy document must re-enter strict validation on every content change,
  rename, deletion, or baseline mismatch.
- **Revisit when**: The owner authorizes a repository-wide semantic schema
  conversion with its own inventory and QA plan.

### DEC-004: Keep only downstream-operational template content active

- **What**: Exclude upstream template lifecycle history and template packaging
  self-work; retain validators, evals, hooks, standards, and migration skills.
  Obsolete active guidance is quarantined rather than permanently deleted.
- **Why**: Downstream agents need current workflow contracts, not records or
  tooling that describe maintenance of the template repository itself.
- **Change freedom**: The exact quarantine location may change if content stays
  non-operational, auditable, and outside validator/agent discovery surfaces.

## Consequences / Impact

The project gains pinned provenance, modern docs QA, and lifecycle guardrails.
Application runtime and user-facing behavior are intentionally unchanged. Some
legacy project documents remain outside strict schema v2 until reviewed;
unscoped schema/link/intent failures and pre-existing backend baseline
failures therefore remain explicit residual work rather than a compatibility
failure. Full markdownlint is clean under the retained U-derived policy after
the project-local, semantics-preserving fixes recorded in the migration
inventory.

## Quality Implications

- Provenance and inventory completeness are required for closure.
- Scoped compatibility checks must pass before lock advancement.
- Project tests and hash/diff checks protect checkpointed runtime state.
- Schema marker behavior must be covered by negative fixtures.

## Intent-derived Invariants

- INV-001 (from DEC-001): The active provenance lock identifies a release tag
  and the exact full commit whose reconciled files are present.
- INV-002 (from DEC-002): Every raw delta path has exactly one recorded
  resolution and one final disposition.
- INV-003 (from DEC-002): The checkpointed project runtime and application
  source are unchanged by the template migration.

## Enforced in (optional)

- DEC-001 / INV-001: `docs-template.lock.json` and migration verification.
- DEC-002 / INV-002: migration inventory artifacts and coverage check.
- DEC-002 / INV-003: project diff and application verification commands.
- DEC-003: `.github/workflows/docs-ci.yml`,
  `artifacts/markdownlint-compatibility-baseline.tsv`, and verification verdict
  split.

## Rollback / Follow-ups

The isolated migration commit can be abandoned without moving the original
checkout or main. Strict schema conversion remains a separate owner decision.
