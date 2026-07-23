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
related_issues: []
related_prs: []
---

# QA Test Plan: Pre-run cost and duration estimate

## Source of Intent

- `_docs/intent/UI/pre-run-estimate/decision.md`

## Decision Review Scope

- `DEC-001` … `DEC-005`
- `INV-001`

## Quality Goal

実行前に履歴優先のコスト／所要見積が出せ、構成差は補正ラベル付きで扱い、不明コストを
0 埋めしない。実行中 ETA・事後コストと混同しない。

## Acceptance Criteria

- AC-001: 同一被検の過去 run があるとき、コストと所要の主見積が履歴から出る。
- AC-002: タスク数・judge 数・run 回数が違うとき構成補正がかかり `history_scaled` 相当になる。
- AC-003: 履歴が無いとき所要は heuristic、コストは単価不明なら unavailable（0 でない）。
- AC-004: idle に見積 UI と確度ラベルが出る。
- AC-005: 実行中 ETA / 事後 CostSection の既存定義を変えない。

## Intent-derived Invariants

- INV-001: 不明コストを 0 として成功表示しない。

## Risk Assessment

- **Medium**: 過大に低いコスト見積で課金判断を誤る → 0 埋め禁止と確度ラベル。
- **Medium**: 誤マッチ（同名別構成）→ 被検必須 + 距離スコア。

## Test Strategy

- node unit: `preRunEstimate.ts`（マッチ、補正、heuristic、INV-001）。
- diff review: RunPage idle のみ、running CostSection 非変更。
- build: `npm run build --prefix frontend`。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | 履歴主見積 | node | `preRunEstimate.node.test.ts` | source=history | verified |
| AC-002 | TODO | 構成補正 | node | same | source=history_scaled | verified |
| AC-003 | TODO | 履歴無し | node | same | duration heuristic, cost null | verified |
| AC-004 | TODO | idle UI | diff review | `RunPage.tsx` | 見積カード | verified |
| AC-005 | TODO | 非回帰 | diff review | ResultDetail / ETA helpers | 未変更または無関係 | verified |
| INV-001 | Intent | 0 埋め禁止 | node | same | costUsd null when unavailable | verified |

## Manual QA Checklist

- [ ] 履歴のある被検で idle にコストと所要が出る。
- [ ] タスク数を変えると補正ラベルになる。
- [ ] 未実行の被検ではコスト N/A、所要は粗い推定。

## Regression Checklist

- [ ] 実行中 ETA 表示が従来どおり。
- [ ] 結果の推定コスト表示が従来どおり。

## Out of Scope

- 包括評価の精密見積、単価 API。

## Open Questions

None
