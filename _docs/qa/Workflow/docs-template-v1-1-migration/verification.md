---
title: "QA Verification: Docs-driven template v1.1.0 migration"
status: active
draft_status: n/a
qa_status: verified
risk: High
qa_schema: 2
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/Workflow/docs-template-v1-1-migration/decision.md"
  - "_docs/archives/plan/Workflow/docs-template-v1-1-migration/plan.md"
  - "_docs/qa/Workflow/docs-template-v1-1-migration/test-plan.md"
related_issues: []
related_prs: []
---

# QA Verification: Docs-driven template v1.1.0 migration

## Summary

Compatibility migration from pinned template `v1.0.0`
(`f71e9ab20466ea2972158334261f5ae2b2265754`) to `v1.1.0`
(`9f4503030bd42521541a951adc79fe3aa40823c3`) completed on `main` at cutoff
`P=34d9f6275127b3e2c18adc5b4de93d3b49eb5dba`. TypeScript validators/hooks are
active, project customizations were merged, superseded `.mjs` scripts are
quarantined, and the provenance lock was advanced last.

| Migration stage | Status | Boundary |
| --- | --- | --- |
| v1.1.0 compatibility migration | PASS | U files reconciled; lock equals U; docs wrapper PASS. |
| Strict schema migration | DEFERRED | Explicitly out of scope for this release. |

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
date
git rev-parse HEAD
git ls-remote --tags https://github.com/penne-0505/docs_driven_dev_template.git 'v1.0.0*' 'v1.1.0*'
./scripts/check-docs.sh
# baseline captured before import; final after lock advance
npx markdownlint-cli2 "_docs/**/*.md" "_evals/**/*.md" "README.md" \
  "AGENTS.md" "TODO.md" "QUICKSTART.md" "!_docs/archives/**/*" \
  "!_docs/standards/templates/**/*" --config .markdownlint.jsonc
deno check scripts/*.ts
```

Result:

```text
Pre-migration check-docs: FAIL on two scope fixture cases
  (DD_SCOPE_DIFF_FILTER ACMR; compatibility baseline)
Post-migration check-docs: PASS, including those scope cases
Markdownlint: PASS after TODO blank-line fix (131 files)
deno check scripts/*.ts: PASS
Lock tag/SHA match upstream v1.1.0 peel
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `./scripts/check-docs.sh` (final) | PASS | fmt, check, validators, fixtures, hooks, smoke |
| Frontmatter fixtures | PASS | Project fixture mode retained on TS validator |
| Scope / compatibility baseline fixtures | PASS | Baseline failures cleared by U `scope.ts` env sanitization |
| Hook unit + smoke | PASS | Direct `docs-template.lock.json` asserts `v1.1.0` |
| `deno check scripts/*.ts` | PASS | |
| markdownlint-cli2 live docs | PASS | |

## Manual QA Results

| Check | Result | Notes |
| --- | --- | --- |
| Path inventory completeness | PASS | 44 upstream delta paths classified |
| Customization preservation | PASS | QUICKSTART kept; ops judge/lock exception kept; frontmatter strengthen kept |
| Template-self exclusion | PASS | lifecycle-self-audit and lock.example absent |
| Quarantine of superseded `.mjs` | PASS | Quarantined during migration; owner later authorized permanent deletion |
| Agent misbehavior review | PASS | No tip pin; no blind replace of customized files; lock advanced last |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | `artifacts/path-inventory.tsv` (44 rows) |
| AC-002 | PASS | `scripts/check-docs.sh` uses `.ts`; no active `scripts/*.mjs` |
| AC-003 | PASS | frontmatter fixture PASS lines in final check-docs log |
| AC-004 | PASS | smoke asserts `docs-template.lock.json`; example lock absent |
| AC-005 | PASS | lifecycle-self-audit / lock.example absent |
| AC-006 | PASS | `.mjs` were quarantined first; owner then authorized permanent removal |
| AC-007 | PASS | lock tag/commit = `v1.1.0` / `9f4503030bd42521541a951adc79fe3aa40823c3` |
| AC-008 | PASS | inventory resolutions + lock-last order recorded here |

## Decision Conformance

| ID | Result | Notes |
| --- | --- | --- |
| DEC-001 | PASS | B/U pinned by tag + full SHA; tip not used |
| DEC-002 | PASS | customized shared paths merged, not wholesale replaced |
| DEC-003 | PASS | strict schema deferred separately |
| DEC-004 | PASS | template-self and example lock excluded |
| DEC-005 | PASS | Quarantine-first path followed; owner later authorized permanent removal of both v1.0.0 and v1.1.0 quarantine trees |
| DEC-006 | PASS | lock advanced after compatibility PASS |

## Invariant Coverage

| ID | Result | Notes |
| --- | --- | --- |
| INV-001 | PASS | lock equals integrated U; remote peel matches |
| INV-002 | PASS | docs CI path uses TypeScript entrypoints |

## Deferred / Not Covered

- Repository-wide strict schema conversion (DEC-003 / plan Non-Goal).
- Application pytest / frontend build (out of migration scope; not executed).

## Residual Risks

None

## Follow-up TODOs

None. Owner authorized permanent deletion of
`.migration-quarantine/docs-template-v1.0.0/` and
`.migration-quarantine/docs-template-v1.1.0-superseded-mjs/` on 2026-07-24;
git history remains the recovery path.
