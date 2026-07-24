---
title: "QA Verification: Task duration estimates and ETA on results"
status: active
draft_status: n/a
qa_schema: 2
qa_status: verified
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-24
references:
  - "_docs/intent/Core/task-duration-eta/decision.md"
  - "_docs/qa/Core/task-duration-eta/test-plan.md"
  - "_docs/plan/Core/run-eta-history-blend/plan.md"
  - "_docs/archives/plan/Core/task-duration-eta/plan.md"
related_issues: []
related_prs: []
---

# QA Verification: Task duration estimates and ETA on results

## Summary

Core-Enhance-66: 実行中 ETA を wall-clock 残りへ切り替え、履歴類似度事前を SSE に載せ、
同一 run の実測ペースを強く支配させた。`task_timing` 永続化・ResultDetail 表示は維持。

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
uv run pytest tests/test_progress_eta.py tests/test_server_frontend.py -k 'progress_eta or remaining_task_count or ProgressEta' -q
npx --prefix frontend tsx --test frontend/src/lib/taskTiming.node.test.ts
npm run lint --prefix frontend
npm run build --prefix frontend
```

Result: 12 pytest PASS (37 deselected), 3 node PASS, lint PASS, build PASS.

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| wall pace vs timing | PASS | AC-010 |
| history at start | PASS | AC-011 |
| step / unavailable | PASS | AC-012 |
| measured dominates + clamp | PASS | AC-013 |
| status labels | PASS | AC-014 |
| remaining>0 no zero | PASS | AC-015 / holistic |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| live run 目視 | deferred | unit で十分と判断 |
| ResultDetail timing | PASS（regression） | 未変更経路 |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 / AC-003 | PASS | prior verification + 非変更 |
| AC-010–015 | PASS | unit / node |

## Decision Conformance

| ID | Result | Why aligned |
| --- | --- | --- |
| DEC-001 | PASS | task_timing 維持 |
| DEC-002 | PASS | wall remaining + measured heavy + history prior on SSE |
| DEC-003 | PASS | status ラベル拡張 |

## Invariant Coverage

None

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| live 目視 | unit で十分 | 任意 |
| 定数較正 | reference 仮置き | 実運用で調整可 |

## Residual Risks

None

## Follow-up TODOs

None

## Completion Decision

- TODO `Core-Enhance-66` は Verification PASS で閉じられる。
