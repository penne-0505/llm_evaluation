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
  - "_docs/reference/UI/pre-run-estimate/reference.md"
related_issues: []
related_prs: []
---

# QA Verification: Pre-run cost and duration estimate

## Summary

実行前見積を単一最近傍から、複数履歴の類似度重み付きプール（被験コスト硬ゲート・
wall 薄い横断・単位レート×計画負荷）へ置換した。計算仕様は reference。不明コストは
null（INV-001）。別被験の被験コストは混入しない（INV-002）。

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
npx --prefix frontend tsx --test frontend/src/lib/preRunEstimate.node.test.ts
npm run lint --prefix frontend
npm run build --prefix frontend
```

Result: 11 PASS, lint PASS, build PASS.

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| identical shape history | PASS | AC-001 |
| closer outweighs farther | PASS | AC-001 / DEC-001 |
| taskCount / judgeRunCount scale | PASS | AC-002 / DEC-003 |
| no history heuristic + null cost | PASS | AC-003 / INV-001 |
| other-subject only | PASS | AC-006 / INV-002 |
| mixed subjects asymmetric gates | PASS | AC-007 / DEC-006 |
| legacy total-only cost | PASS | same-subject fallback |
| missing cost + scaled duration | PASS | INV-001 |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| idle 見積カード | PASS（diff） | RunPage idle・文言更新 |
| 実行中 ETA 非変更 | PASS（diff） | ETA helpers 未変更 |
| 事後 CostSection 非変更 | PASS（diff） | ResultDetail 未変更 |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | unit: multi-run weighted |
| AC-002 | PASS | unit: load unitize + scale label |
| AC-003 | PASS | unit: heuristic / null cost |
| AC-004 | PASS | RunPage idle card |
| AC-005 | PASS | diff review |
| AC-006 | PASS | unit: other-subject only |
| AC-007 | PASS | unit: mixed subjects |

## Decision Conformance

| ID | Result | Why aligned |
| --- | --- | --- |
| DEC-001 | PASS | multi-run similarity weights; closer dominates |
| DEC-002 | PASS | duration primary from `executionDurationMs` |
| DEC-003 | PASS | unit rate then × L_plan |
| DEC-004 | PASS | null cost / heuristic duration |
| DEC-005 | PASS | idle + source labels |
| DEC-006 | PASS | subject_cost gate 0; wall γ>0; judge soft β |
| INV-001 | PASS | costUsd null when unknown |
| INV-002 | PASS | subjectGate / AC-006·007 |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | unit: unknown cost stays null (not 0) |
| INV-002 | PASS | unit: other-subject subject cost excluded |

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| live 目視 | unit + diff で十分と判断 | 任意 |
| `judge_time` 補助チャネル | reference 上 optional。wall 欠落時は heuristic を採用（DEC-002） | 必要なら reference 更新のうえ追加 |
| 定数較正 | Intent Change freedom / reference 仮置き。極端な単位レートの薄い寄与は定数で調整可 | 実履歴で較正する別 TODO |
| summary の run 回数・judge id | 既知制約 | 別 TODO |
| 別被験 wall の薄い寄与 | Intent DEC-006 上許容。同一被験が増えれば相対寄与は落ちる | 不要なら γ を reference で調整 |

## Residual Risks

None

## Follow-up TODOs

None

## Completion Decision

- TODO `UI-Enhance-64` は Verification PASS で閉じられる。
