---
title: "QA Verification: Docs-driven template v1.0.0 migration"
status: active
draft_status: n/a
qa_status: partial
risk: High
qa_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/Workflow/docs-template-v1-migration/decision.md"
  - "_docs/plan/Workflow/docs-template-v1-migration/plan.md"
  - "_docs/qa/Workflow/docs-template-v1-migration/test-plan.md"
related_issues: []
related_prs: []
---

# QA Verification: Docs-driven template v1.0.0 migration

## Summary

Compatibility integration, project preservation, inventory reconciliation,
frontend regression checks, local runtime smoke, exact lock review, scoped
documentation wrapper, and the CI-equivalent full markdownlint run have
completed. `Workflow-Chore-30` remains open for the residual repository-wide
strict migration and backend baseline work.

| Migration stage | Status | Boundary |
| --- | --- | --- |
| v1.0.0 compatibility migration | PASS | U workflow is operational with blob-pinned ACMR legacy scope. |
| Repository-wide strict schema migration | PARTIAL | Legacy semantic conversion is deferred by design. |

## Verification Verdict

Verdict: PARTIAL

## Commands Run

```bash
deno fmt scripts/*.mjs
deno run --allow-read --allow-write --allow-env --allow-run scripts/test-validators.mjs
deno run --allow-read --allow-run=git scripts/test-agent-workflow-hook.mjs
cmp .agents/skills/<skill>/SKILL.md .claude/skills/<skill>/SKILL.md
npx --yes markdownlint-cli2 ... --config .markdownlint.jsonc
uv run --with pytest python -m pytest
npm ci --prefix frontend
node --test frontend/src/api/client.node.test.ts frontend/src/store/runStore.node.test.ts
npm run lint --prefix frontend
npm run build --prefix frontend
uv run prism-llm-eval --no-browser --port 8765
curl --fail --silent --show-error http://127.0.0.1:8765/api/resources
DD_SCOPE_PATHS="<migration paths>" ./scripts/check-docs.sh
DD_SCOPE_BASE=d309974a77c736b6d333819a38460edaeb21e57e \
  DD_SCOPE_DIFF_FILTER=ACMR ./scripts/check-docs.sh
DD_SCOPE_BASE=d309974a77c736b6d333819a38460edaeb21e57e \
  DD_SCOPE_DIFF_FILTER=ACMR \
  DD_SCOPE_COMPATIBILITY_BASELINE=_docs/qa/Workflow/docs-template-v1-migration/artifacts/markdownlint-compatibility-baseline.tsv \
  ./scripts/check-docs.sh
```

Result:

```text
Validator fixtures: PASS, including frontmatter unknown/wrong-type/duplicate/type markers
Hook unit tests: PASS
Paired skills: PASS
Markdownlint: PASS, 110 files, 0 errors without migration-local lint exemptions
Backend: 71 passed, 2 pre-existing strict-mode expectation failures
Frontend Node tests: 2 passed
Frontend lint/build: PASS
Launcher/API smoke: PASS, clean SIGINT shutdown
Scoped docs wrapper and hook smoke: PASS
P...HEAD ACMR wrapper with the exact 29-blob compatibility baseline: PASS
Changed blob probe and unknown path/blob/malformed manifest probes: fail closed
```

The initial `uv run pytest` and frontend commands failed because pytest and
worktree-local Node dependencies were unavailable in those execution contexts.
The dependency-complete commands above supersede those environment failures.

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| Frontmatter/TODO/Intent/QA fixtures | PASS | Negative frontmatter fixture families fail as expected. |
| Hook unit and paired skills | PASS | Deletion guard self-test avoids PreToolUse false positive. |
| Full markdownlint | PASS | Exact `markdownlint-cli2@0.13.0` command linted 110 files with 0 errors under the U-derived 12-rule policy and no local exemptions. |
| Scoped docs wrapper | PASS | Explicit migration paths and post-commit P...HEAD ACMR both pass. |
| Backend pytest | PARTIAL | 71 pass; 2 P-existing strict mode preset/expectation mismatches. |
| Frontend Node tests | PASS | 2 tests passed. |
| Frontend ESLint / TypeScript / Vite build | PASS | Build warnings only for runtime-resolved font files. |
| Launcher HTTP smoke | PASS | `/api/resources` responded; shutdown completed. |
| Application/runtime diff from P | PASS | Empty over source, tests, assets, runtime/build inputs. |
| ResultDetail blob | PASS | P and worktree blob `9911a4a67ad80ffaa7bc89795407116f9b83cdd8`. |
| Raw inventory coverage | PASS | Zero missing, duplicate, invalid resolution, or empty disposition rows. |
| U-exact apply paths | PASS | Every `reconciled-from-U` blob matches U. |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| Customized shared root files | PASS | Project README/commands/Inbox preserved. |
| Lifecycle/template-self exclusions | PASS | History, archive packager, and lock example are absent. |
| Legacy active guidance | PASS | Seven exact paths moved to non-operational quarantine. |
| Parallel/post-cutoff isolation | PASS | Worktree remains based on owner-approved P. |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | B tree identity and U tag/full SHA recorded. |
| AC-002 | PASS | Three raw artifacts and mechanical coverage check. |
| AC-003 | PASS | Application diff empty; checkpointed component hash matches. |
| AC-004 | PARTIAL | Scoped wrapper passes with the 29 exact blob-pinned markdownlint-only legacy docs excluded; changed blobs and invalid manifests fail closed. Unscoped strict schema/link/intent failures remain separate residual work. |
| AC-005 | PASS | Five negative and two valid frontmatter fixtures added. |
| AC-006 | PASS | Full lint, fixtures, hook unit/smoke, and paired skills pass; `artifacts/markdownlint-remediation.tsv` records all 29 project-local fixes. |
| AC-007 | PARTIAL | Available suites executed; two baseline failures are unchanged by the migration but remain to be diagnosed. |
| AC-008 | PASS | Active-reference scan clean; exact quarantine manifest retained. |
| AC-009 | PASS | Lock tag/full SHA match U after reconciliation. |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | B/U are proven and the downstream lock is exact. |
| DEC-002 | PASS | Raw union coverage and project/runtime preservation are explicit. |
| DEC-003 | PARTIAL | Blob-pinned compatibility scope and strict unscoped failures are separate; the unscoped migration remains open. |
| DEC-004 | PASS | Only operational U content is active; stale guidance is quarantined. |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | `v1.0.0` resolves to the full commit recorded by the lock. |
| INV-002 | PASS | Inventory coverage reports zero missing or duplicate paths. |
| INV-003 | PASS | Runtime diff is empty and ResultDetail blob matches P. |

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| Strict schema/link/intent migration | Unscoped validation retains legacy frontmatter/stale, path/archive contract, link, and intent failures. These require semantic review. | Workflow-Chore-30: perform an owner-approved repository-wide strict migration with its own inventory and QA plan. |
| Backend strict-mode baseline | Two tests expect `0.60` while current P preset reports `0.45`. | Workflow-Chore-30: diagnose and split the behavior correction into a project task without changing this template migration. |
| Live provider calls | External credentials and network behavior are outside migration scope. | Existing provider integration workflow. |

## Residual Risks

- Repository-wide strict schema/link/intent validation is not yet clean. The
  scoped ACMR compatibility result does not establish strict-schema readiness.
- The compatibility scope starts with paths added, copied, modified, or renamed
  from P `d309974a77c736b6d333819a38460edaeb21e57e` while
  `DD_SCOPE_DIFF_FILTER=ACMR` remains configured. The checked-in
  `artifacts/markdownlint-compatibility-baseline.tsv` excludes only its 29
  listed legacy paths while each working-tree Git blob exactly matches the
  recorded post-remediation blob. Any content change, rename, deletion, or
  malformed/unknown manifest row re-enters validation or stops it fail closed.
  The support horizon ends only when an owner-approved strict
  frontmatter/link/intent migration records a PASS and explicitly replaces this
  policy. It does not turn the remaining unscoped strict result into a PASS.
- Two backend strict-mode tests remain failing at the P baseline; unchanged
  migration diffs classify them as independent, but not resolved.

## Follow-up TODOs

- `Workflow-Chore-30`: complete the owner-approved strict schema/link/intent
  migration, preserving semantic review and a separate inventory/QA plan.
- `Workflow-Chore-30`: replace the blob-pinned compatibility baseline only as
  part of that strict migration; do not add future substantive legacy edits to
  the baseline.
- `Workflow-Chore-30`: diagnose the two strict-mode preset/expectation baseline
  failures and create a focused project behavior task if the correction scope
  is distinct.
