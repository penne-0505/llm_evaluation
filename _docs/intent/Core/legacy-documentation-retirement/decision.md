---
title: "Decision: Retire legacy Core temporary documentation"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/Workflow/docs-template-v1-migration/decision.md"
  - "_docs/qa/Workflow/docs-template-v1-migration/test-plan.md"
  - "_docs/archives/draft/Core/legacy-documentation-retirement/judge_sys_instruction.md"
  - "_docs/archives/draft/Core/legacy-documentation-retirement/requirements.md"
  - "_docs/archives/plan/Core/legacy-documentation-retirement/benchmark-execution-performance-optimization.md"
  - "_docs/archives/plan/Core/legacy-documentation-retirement/grounding-corpus-pipeline.md"
  - "_docs/archives/plan/Core/legacy-documentation-retirement/judge-rubric-reliability.md"
  - "_docs/archives/plan/Core/legacy-documentation-retirement/llm_benchmark_app.md"
  - "_docs/archives/plan/Core/legacy-documentation-retirement/lmstudio-local-provider-support.md"
  - "_docs/archives/plan/Core/legacy-documentation-retirement/local-search-tool-use-runtime.md"
  - "_docs/archives/plan/Core/legacy-documentation-retirement/model-selection-from-api.md"
  - "_docs/archives/plan/Core/legacy-documentation-retirement/resource-embedding-packaging.md"
  - "_docs/archives/plan/Core/legacy-documentation-retirement/streamlit-secrets-api-keys.md"
  - "_docs/archives/plan/Core/legacy-documentation-retirement/strict-mode-leaderboard.md"
related_issues: []
related_prs: []
---

# Decision: Retire legacy Core temporary documentation

## Context

Core drafts and plans accumulated across the original Streamlit application,
the React/FastAPI rebuild, and later feature work. None except the holistic-run
plan is referenced by active TODO work. Several describe completed behavior;
others are unscheduled proposals or historical requirements.

## Decisions

### DEC-001: Preserve historical Core documents outside live planning paths

- **What**: Archive the referenced Core drafts and plans without rewriting
  their historical requirements or implementation descriptions.
- **Why**: Leaving them live makes abandoned proposals and completed work appear
  actionable, while rewriting them would erase the distinction between original
  intent and current implementation.
- **Change freedom**: A document may return to a live plan only through a new or
  active TODO that revalidates its scope and QA requirements.

## Consequences / Impact

- Current behavior remains documented by README, guides, references, active
  intents, QA records, implementation, and tests.
- Archived proposals remain searchable but no longer compete with TODO as the
  work source of truth.

## Quality Implications

- Archive links and the absence of live duplicates are validated unscoped.
- Historical body content is preserved except for metadata and reference repair.

## Intent-derived Invariants

- INV-001 (from DEC-001): Referenced Core temporary documents exist only under
  canonical archive paths while this decision remains active.

## Enforced in (optional)

- `_docs/archives/{draft,plan}/Core/legacy-documentation-retirement/`
- `_docs/qa/Workflow/docs-template-v1-migration/verification.md`

## Rollback / Follow-ups

- Restore only the specific document needed by an approved TODO; do not bulk
  restore the retired planning shelf.
