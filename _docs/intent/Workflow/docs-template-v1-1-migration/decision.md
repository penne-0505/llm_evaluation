---
title: "Decision: Docs-driven template v1.1.0 migration"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/archives/plan/Workflow/docs-template-v1-1-migration/plan.md"
  - "_docs/qa/Workflow/docs-template-v1-1-migration/test-plan.md"
related_issues: []
related_prs: []
---

# Decision: Docs-driven template v1.1.0 migration

## Context

The repository already pins docs-driven template `v1.0.0` in
`docs-template.lock.json`. Upstream published `v1.1.0`, which replaces Deno
`.mjs` validators/hooks with TypeScript and adds `deno.json`. The project has
post-`v1.0.0` customizations (frontmatter fixture mode, scope compatibility
baseline, direct lock policy, app QUICKSTART) that must survive the update.
Owner approved migration on `main` with cutoff
`P=34d9f6275127b3e2c18adc5b4de93d3b49eb5dba`.

## Decisions

### DEC-001: Pin migration endpoints by lock and release tag

- **What**: Treat lock revision `v1.0.0` /
  `f71e9ab20466ea2972158334261f5ae2b2265754` as `B`, and selected release
  `v1.1.0` / `9f4503030bd42521541a951adc79fe3aa40823c3` as `U`. Reject moving
  branch tips.
- **Why**: Tag plus full SHA are the only reproducible update unit; a retargeted
  tag must stop the migration.
- **Change freedom**: Later migrations may choose a newer release tag with the
  same provenance rules.

### DEC-002: Preserve project customizations through three-way path inventory

- **What**: Classify every `B→U` path against `B→P`, assign one resolution, and
  merge rather than wholesale-replace customized shared files.
- **Why**: Blind U replacement would drop frontmatter fixture enforcement,
  direct-lock smoke checks, and project documentation exceptions.
- **Change freedom**: Inventory artifact format may change if coverage remains
  auditable.

### DEC-003: Keep compatibility migration separate from strict schema work

- **What**: Close this task on TypeScript/runtime compatibility and provenance.
  Do not bulk-convert legacy documents solely to claim a new strict-schema PASS.
- **Why**: `v1.1.0` does not introduce a new document schema; mixing schema
  conversion would hide migration regressions.
- **Change freedom**: A later owner-approved strict migration may proceed under
  its own inventory and QA.

### DEC-004: Exclude template-self meta-work and example lock file

- **What**: Do not import `lifecycle-self-audit` docs or
  `docs-template.lock.example.json`. Continue operating a tracked
  `docs-template.lock.json` only.
- **Why**: Downstream agents need operational contracts, not template-repo
  packaging history; this project already rejected the example-file workflow.
- **Change freedom**: Example file may be added later if the project explicitly
  adopts dual lock+example semantics.

### DEC-005: Quarantine superseded `.mjs` instead of permanent deletion

- **What**: After TypeScript entrypoints work, move superseded `.mjs` scripts
  into `.migration-quarantine/` rather than `git rm` / `rm`.
- **Why**: Repository policy forbids permanent deletion without explicit owner
  deletion authority; quarantine keeps auditability.
- **Change freedom**: Owner may later authorize permanent removal of quarantined
  blobs.

### DEC-006: Advance the provenance lock only after compatibility PASS

- **What**: Update `docs-template.lock.json` to `v1.1.0` /
  `9f4503030bd42521541a951adc79fe3aa40823c3` as the final migration write after
  reconciled U files and compatibility checks succeed.
- **Why**: A lock that points at U before integration claims a false baseline.
- **Change freedom**: Deferred follow-ups must not leave the lock on `B` once U
  files are the reconciled baseline.

## Consequences / Impact

- Local and CI docs checks run TypeScript validators via `scripts/check-docs.sh`.
- Skills and standards reference `.ts` paths.
- Project QUICKSTART and judge-prompt root exception remain.
- Pre-migration scope fixture failures may clear via U's sanitized git env.

## Quality Implications

- High risk: validators, hooks, CI, and agent workflow contracts change together.
- Agent misbehavior risks: branch-tip pinning, blind replacement, premature lock
  advance, and importing template-self docs.

## Intent-derived Invariants

- INV-001 (from DEC-001): `docs-template.lock.json` identifies the integrated
  release tag and its exact full commit after migration closure.
- INV-002 (from DEC-006): `scripts/check-docs.sh` invokes TypeScript
  validators/tests and does not depend on active-tree `.mjs` validators for the
  docs CI path.

## Enforced in (optional)

- DEC-001 / INV-001: `docs-template.lock.json` and migration verification.
- DEC-002: `_docs/qa/Workflow/docs-template-v1-1-migration/artifacts/path-inventory.tsv`
- DEC-004: absence of lifecycle-self-audit and lock.example in the live tree.
- DEC-005: quarantine-first adoption, then owner-authorized removal of
  `.migration-quarantine/` trees (git history remains recoverable).
- DEC-006 / INV-002: `scripts/check-docs.sh`, `deno.json`, and docs CI.

## Rollback / Follow-ups

Recover by reverting the migration commit(s) on `main`. Quarantine trees for
v1.0.0 and v1.1.0 superseded files were permanently removed with owner
authority on 2026-07-24; restore from git history if needed. Strict schema
conversion remains a separate owner-approved follow-up and is not required to
keep the `v1.1.0` lock.
