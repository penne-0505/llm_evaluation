---
title: "QA Verification: Docs-driven template v1.0.0 migration"
status: active
draft_status: n/a
qa_status: verified
risk: High
qa_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/Workflow/docs-template-v1-migration/decision.md"
  - "_docs/archives/plan/Workflow/docs-template-v1-migration/plan.md"
  - "_docs/qa/Workflow/docs-template-v1-migration/test-plan.md"
related_issues: []
related_prs: []
---

# QA Verification: Docs-driven template v1.0.0 migration

## Summary

The v1.0.0 compatibility migration and its owner-approved strict closure are
complete. Historical temporary docs were preserved under canonical archives
without rewriting their body content as current design. Area-level retirement
intents make every archive discoverable, and only plans required by active TODO
work remain live.

| Migration stage | Status | Boundary |
| --- | --- | --- |
| v1.0.0 compatibility migration | PASS | U provenance, lock, inventory, and project preservation remain verified. |
| Repository-wide strict schema migration | PASS | Unscoped validators pass; CI no longer sets compatibility scope. |
| Temporary-doc retirement | PASS | Live drafts/surveys are empty and only two active TODO plans remain live. |
| Project check reproducibility | PASS | `uv sync` installs project-local pytest; canonical backend tests pass. |

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
./scripts/check-docs.sh
npx markdownlint-cli2 "_docs/**/*.md" "_evals/**/*.md" "README.md" \
  "AGENTS.md" "TODO.md" "QUICKSTART.md" "!_docs/archives/**/*" \
  "!_docs/standards/templates/**/*" --config .markdownlint.jsonc
uv sync
uv run which pytest
uv run pytest
npm run lint --prefix frontend
npm run build --prefix frontend
# Start `uv run prism-llm-eval --no-browser --host 127.0.0.1 --port 8768`
curl --fail --silent http://127.0.0.1:8768/api/resources
uv run --with pyyaml python <docs workflow YAML assertion>
find _docs/plan -type f -name '*.md'
find _docs/draft _docs/survey -type f -name '*.md'
git diff --check
```

Result:

```text
Unscoped docs wrapper: PASS, including validators, fixtures, hooks, paired skills
Markdownlint: PASS, 85 live files, 0 issues
Backend: 90 passed
Project-local pytest: PASS (`.venv/bin/pytest`)
Frontend lint/build: PASS; known missing-font warning is tracked by UI-Bug-33
Launcher/API smoke: PASS
Docs workflow YAML: PASS, no compatibility env
Live temporary inventory: 1 active plan, 0 drafts, 0 surveys
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| Unscoped docs wrapper | PASS | Frontmatter, TODO, links, intent, QA, fixtures, hooks, and skill checks pass. |
| Full live-doc markdownlint | PASS | 85 files, 0 issues; archives stay historical and outside lint scope. |
| Backend pytest | PASS | 90 tests pass through project-local `.venv/bin/pytest`. |
| Frontend ESLint / TypeScript / Vite build | PASS | Known font warnings are isolated in `UI-Bug-33`. |
| Launcher HTTP smoke | PASS | `/api/resources` responds from the documented local launcher. |
| Archive inventory | PASS | Retirement intents reference every archived temporary document; no live duplicates. |
| Docs workflow review | PASS | Compatibility env is absent; wrapper runs unscoped. |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| Historical content preservation | PASS | Body content was not rewritten into current architecture; only metadata/references changed. |
| Active planning shelf | PASS | Holistic progress and migration closure are the only live plans before final archival. |
| Root runtime prompt boundary | PASS | `judge_system_prompt.md` is explicitly excluded from coding-agent guidance. |
| Compatibility retirement | PASS | Baseline artifact remains historical, but CI no longer references it. |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | B tree identity and U tag/full SHA recorded. |
| AC-002 | PASS | Three raw artifacts and mechanical coverage check. |
| AC-003 | PASS | Application diff empty; checkpointed component hash matches. |
| AC-004 | PASS | Historical scoped evidence remains preserved; current unscoped wrapper passes. |
| AC-005 | PASS | Five negative and two valid frontmatter fixtures added. |
| AC-006 | PASS | Full lint, fixtures, hook unit/smoke, and paired skills pass; `artifacts/markdownlint-remediation.tsv` records all 29 project-local fixes. |
| AC-007 | PASS | Canonical project-local backend suite passes 90 tests; frontend and launcher smoke pass. |
| AC-008 | PASS | Active-reference scan clean; exact quarantine manifest retained. |
| AC-009 | PASS | Lock tag/full SHA match U after reconciliation. |
| AC-010 | PASS | Canonical retirement intents, archive links, and live inventory pass unscoped validation. |
| AC-011 | PASS | Docs CI configuration has no compatibility env; unscoped wrapper passes. |
| AC-012 | PASS | `uv sync` installs `.venv/bin/pytest`; root prompt exception is explicit. |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | B/U are proven and the downstream lock is exact. |
| DEC-002 | PASS | Raw union coverage and project/runtime preservation are explicit. |
| DEC-003 | PASS | Compatibility evidence remains distinct, and the authorized strict closure is now complete. |
| DEC-004 | PASS | Only operational U content is active; stale guidance is quarantined. |
| DEC-005 | PASS | Historical temporary docs are archived without body modernization. |
| DEC-006 | PASS | Compatibility scope was removed only after unscoped validators passed. |
| DEC-007 | PASS | Canonical checks are project-local and runtime prompt guidance is explicit. |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | `v1.0.0` resolves to the full commit recorded by the lock. |
| INV-002 | PASS | Inventory coverage reports zero missing or duplicate paths. |
| INV-003 | PASS | Runtime diff is empty and ResultDetail blob matches P. |
| INV-004 | PASS | Archive validator confirms intent links and no live/archive duplicates. |
| INV-005 | PASS | Docs workflow has no compatibility env and runs the unscoped wrapper. |
| INV-006 | PASS | `uv run which pytest` resolves `.venv/bin/pytest`; 90 tests pass. |

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| UI font asset contract | Requires a product choice between restoring bundled TTF files and formalizing system fallback. | `UI-Bug-33` |
| Live provider calls | External credentials and network behavior are outside documentation migration scope. | Existing provider integration workflow |

## Residual Risks

None

## Follow-up TODOs

- `UI-Bug-33`: align CSS font references, shipped assets, README, and regression
  coverage.
