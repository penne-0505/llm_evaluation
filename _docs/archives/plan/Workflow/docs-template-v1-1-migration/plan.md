---
title: "Plan: Docs-driven template v1.1.0 migration"
status: superseded
draft_status: n/a
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/Workflow/docs-template-v1-1-migration/decision.md"
  - "_docs/qa/Workflow/docs-template-v1-1-migration/test-plan.md"
related_issues: []
related_prs: []
---

# Plan: Docs-driven template v1.1.0 migration

## Overview

Migrate the repository from pinned template `v1.0.0`
(`f71e9ab20466ea2972158334261f5ae2b2265754`) to recommended release `v1.1.0`
(`9f4503030bd42521541a951adc79fe3aa40823c3`) on `main` at cutoff
`P=34d9f6275127b3e2c18adc5b4de93d3b49eb5dba` (clean tree).

`v1.1.0` primarily ports docs validators and agent-workflow hooks from Deno
JavaScript (`.mjs`) to TypeScript (`.ts`) with `deno.json`, and updates paired
skills / standards references. Project customizations from the `v1.0.0`
adoption must be preserved through a path-complete three-way inventory.

Work tracking: `Workflow-Chore-62`.

## Scope

- Freeze and record provenance `B` / `U` / `P`.
- Reconcile every path in the `B→U` delta against the `B→P` project relation.
- Import TypeScript validators, tests, `deno.json`, and matching wrapper/CI.
- Merge project-specific validator and smoke customizations onto U TypeScript.
- Keep project QUICKSTART, direct `docs-template.lock.json` policy, and
  `judge_system_prompt.md` root-markdown exception.
- Exclude template-self lifecycle docs and `docs-template.lock.example.json`.
- Quarantine superseded `.mjs` scripts (no permanent deletion).
- Advance `docs-template.lock.json` only after compatibility checks pass.

## Non-Goals

- No application feature or runtime behavior changes.
- No repository-wide strict schema conversion of legacy docs.
- No import of upstream template lifecycle-self-audit history.
- No push or remote update as part of this plan.
- No modernization of historical verification commands that already recorded
  `.mjs` invocations.

## Requirements

- Inventory covers all 44 upstream delta paths with resolution and disposition.
- Compatibility migration verdict is separate from any deferred strict schema
  work.
- `./scripts/check-docs.sh` uses TypeScript entrypoints and passes relative to
  the recorded pre-migration baseline (baseline already failed two scope
  fixture cases that U's `scope.ts` LD sanitization is expected to fix).
- Project frontmatter fixture mode, duplicate-key checks, type-specific keys,
  compatibility-baseline scope behavior, and direct-lock smoke assertions remain.
- Lock tag/SHA match integrated `U` after the final write.

## Tasks

- [x] Capture raw upstream delta and path inventory artifacts.
- [x] Create Intent and QA test plan; add TODO `Workflow-Chore-62`.
- [x] Apply unmodified U paths; merge customized shared paths.
- [x] Quarantine superseded `.mjs` scripts under `.migration-quarantine/`.
- [x] Run compatibility verification and record results.
- [x] Advance `docs-template.lock.json` as the final migration write.

## QA Plan

- QA document: `_docs/qa/Workflow/docs-template-v1-1-migration/test-plan.md`
- Risk level: High
- Strategy: validator fixtures, docs wrapper, hook tests, paired-skill
  comparison, provenance/diff review, agent misbehavior checks.

## Deployment / Rollout

Work proceeds on `main` per owner approval. Recovery is `git` revert of the
migration commit(s) plus quarantine retention. Lock advances only after
compatibility PASS.
