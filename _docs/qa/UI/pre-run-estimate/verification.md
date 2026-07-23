---
title: "QA Verification: Pre-run cost and duration estimate"
status: active
draft_status: n/a
qa_schema: 2
qa_status: verified
risk: Medium
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/UI/pre-run-estimate/decision.md"
  - "_docs/qa/UI/pre-run-estimate/test-plan.md"
  - "_docs/plan/UI/pre-run-estimate/plan.md"
related_issues: []
related_prs: []
---

# QA Verification: Pre-run cost and duration estimate

## Summary

RunPage idle に履歴優先・構成補正補助の実行前見積（コスト / wall-clock 所要）を追加した。
helper は `frontend/src/lib/preRunEstimate.ts`。不明コストは null（INV-001）。

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
npx --prefix frontend tsx --test frontend/src/lib/preRunEstimate.node.test.ts
npm run lint --prefix frontend
npm run build --prefix frontend
```

Result: 8 PASS, lint PASS, build PASS.

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| history unscaled | PASS | AC-001 |
| distance + newer tie-break | PASS | DEC-001 |
| taskCount scale | PASS | AC-002 |
| judgeRunCount scale | PASS | AC-002 / DEC-003 |
| no history heuristic + null cost | PASS | AC-003 / INV-001 |
| other subject ignored | PASS | DEC-001 |
| missing cost stays null while duration scales | PASS | INV-001 |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| idle 見積カード | PASS（diff） | RunPage idle に接続 |
| 実行中 ETA 非変更 | PASS（diff） | formatEtaDisplay 経路維持 |
| 事後 CostSection 非変更 | PASS（diff） | ResultDetail 未変更 |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | unit |
| AC-002 | PASS | unit |
| AC-003 | PASS | unit |
| AC-004 | PASS | RunPage idle card |
| AC-005 | PASS | diff review |

## Decision Conformance

| ID | Result | Why aligned |
| --- | --- | --- |
| DEC-001 | PASS | subject 必須 + distance |
| DEC-002 | PASS | executionDurationMs |
| DEC-003 | PASS | load ratio scale |
| DEC-004 | PASS | heuristic duration / null cost |
| DEC-005 | PASS | idle + labels |
| INV-001 | PASS | costUsd null when unknown |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | unit: unknown cost stays null (not 0) |

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| live 目視 | unit + diff で十分と判断 | 任意 |
| 包括評価精密見積 | Non-Goal | 別 TODO |
| summary への run 回数 | Intent follow-up。履歴の実 judge_runs≠1 で補正がずれる既知制約 | 別 TODO |

## Residual Risks

None

## Follow-up TODOs

None

## Completion Decision

- TODO `UI-Feat-62` は Verification PASS で閉じられる。
