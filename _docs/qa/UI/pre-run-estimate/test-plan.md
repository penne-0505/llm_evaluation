---
title: "QA Test Plan: Pre-run cost and duration estimate"
status: active
draft_status: n/a
qa_schema: 2
qa_status: planned
risk: Medium
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/plan/UI/pre-run-estimate/plan.md"
  - "_docs/intent/UI/pre-run-estimate/decision.md"
  - "_docs/reference/UI/pre-run-estimate/reference.md"
  - "_docs/qa/UI/pre-run-estimate/verification.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Pre-run cost and duration estimate

## Source of Intent

- `_docs/intent/UI/pre-run-estimate/decision.md`

## Decision Review Scope

- `DEC-001` … `DEC-006`
- `INV-001`, `INV-002`

## Quality Goal

実行前見積が複数履歴の近さに応じた合成から出る。被験コストは別被験で汚さず、所要は薄い
横断を許す。不明コストを 0 埋めしない。実行中 ETA・事後コストと混同しない。

## Acceptance Criteria

- AC-001: 同一被検の複数過去 run があるとき、見積は単一最近傍固定ではなく複数履歴の合成に
  なる（近い履歴の影響が大きい）。
- AC-002: 構成が違う履歴を使うとき、構成無視の平均ではなく単位化してから計画構成へ戻す。
- AC-003: 使える履歴コストが無いとき所要は粗い推定可、コストは unavailable（0 でない）。
- AC-004: idle に見積 UI と確度ラベルが出る。
- AC-005: 実行中 ETA / 事後 CostSection の既存定義を変えない。
- AC-006: 別被験履歴だけしか無いとき、被験コストは混入しない。wall 所要は薄い寄与で
  出得る。
- AC-007: 同一被験と別被験が混在するとき、被験コストは同一被験のみ、所要は別被験も薄い
  寄与を持ち得る。

## Intent-derived Invariants

- INV-001: 不明コストを 0 として成功表示しない。
- INV-002: 被験コスト推定に別被験履歴を含めない。

## Risk Assessment

- **Medium**: 低いコスト見積で課金判断を誤る → INV-001 / INV-002 と確度ラベル。
- **Medium**: 別被験 wall の薄い寄与によるバイアス → Intent 上許容。同一被験が増えれば
  相対寄与は落ちる想定。
- **Low**: reference 定数の較正不足 → Intent 契約外。reference / 実装で調整。

## Test Strategy

- node unit: Intent 結果（合成・単位化・不明コスト・被験コスト非横断）と、現行 reference 式の
  回帰。
- diff review: RunPage idle のみ。ETA / CostSection 非変更。
- build: `npm run build --prefix frontend`。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | 複数履歴合成 | node | `preRunEstimate.node.test.ts` | 近い履歴が強く効く合成 | verified |
| AC-002 | TODO | 構成の単位化 | node | same | 構成無視平均と異なる／負荷に応じた値 | verified |
| AC-003 | TODO | 履歴無し | node | same | duration heuristic, cost null | verified |
| AC-004 | TODO | idle UI | diff review | `RunPage.tsx` | 見積カードとラベル | verified |
| AC-005 | TODO | 非回帰 | diff review | ResultDetail / ETA helpers | 未変更または無関係 | verified |
| AC-006 | TODO | 別被験のみ | node | same | 被験コスト非混入 | verified |
| AC-007 | TODO | 混在時の非対称 | node | same | コストは同一被験、所要は薄い横断 | verified |
| INV-001 | Intent | 0 埋め禁止 | node | same | costUsd null when unavailable | verified |
| INV-002 | Intent | 被験コスト非横断 | node | same | 別被験の被験コスト寄与なし | verified |

## Manual QA Checklist

- [ ] 履歴が複数ある被検で idle にコストと所要が出る。
- [ ] タスク数を変えると数値が構成に応じて動く。
- [ ] 未実行の被検ではコスト N/A（または judge 分のみ）、所要は粗い推定か薄い横断。

## Regression Checklist

- [ ] 実行中 ETA 表示が従来どおり。
- [ ] 結果の推定コスト表示が従来どおり。

## Out of Scope

- 包括評価の精密見積、単価 API、定数の自動較正。

## Open Questions

None
