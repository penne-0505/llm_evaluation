---
title: "QA Test Plan: Task duration estimates and ETA on results"
status: active
draft_status: n/a
qa_schema: 2
qa_status: planned
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-24
references:
  - "_docs/archives/plan/Core/task-duration-eta/plan.md"
  - "_docs/plan/Core/run-eta-history-blend/plan.md"
  - "_docs/intent/Core/task-duration-eta/decision.md"
  - "_docs/archives/survey/Core/task-duration-eta/survey.md"
  - "_docs/qa/Core/task-duration-eta/verification.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Task duration estimates and ETA on results

## Source of Intent

- `_docs/intent/Core/task-duration-eta/decision.md`

## Decision Review Scope

- `DEC-001`: `task_timing` 永続化（既存）
- `DEC-002`: 残り wall-clock、実測ペース優先、履歴は弱い事前（Core-Enhance-66）
- `DEC-003`: status / ラベルで推定種別を区別

## Quality Goal

実行中 ETA が待ち時間として読め、序盤は履歴事前・完了増で実測が支配し、確定値風に見せない。
結果詳細の per-task timing は既存どおり。

## Acceptance Criteria

### Existing (task_timing / ResultDetail)

- AC-001: 各通常タスクに `task_timing` が永続化される。
- AC-003: 結果詳細で被検 / judge 内訳が表示される。

### Core-Enhance-66 (progress ETA)

- AC-010: 完了タスクがあるとき、ETA は `task_timing` 平均ではなく wall ペース
  （経過／完了数×残数）に基づく。
- AC-011: 完了 0 かつ履歴 wall があるとき `history`（step より履歴優先）。
- AC-012: 完了 0 かつ履歴も無いとき `step_fallback` または `unavailable`。
- AC-013: 完了が増えると実測寄与が履歴事前より大きくなり、十分大きければ `measured`。
- AC-014: `eta_status` が UI ラベルに反映される（measured / history_blend / history /
  step_fallback / unavailable）。
- AC-015: 残タスクがあるのに ETA 0 を measured 成功として出さない（holistic 残含む）。

## Intent-derived Invariants

None

## Risk Assessment

- Medium: wall ペースと履歴事前の合成が過大／過小 → status 明示と α 仮置き。
- Medium: 履歴読込失敗で ETA 欠落 → step / unavailable へフォールバック。
- Low: 未知 `eta_status` は frontend が unavailable 扱い。

## Test Strategy

- `tests/test_progress_eta.py` で合成・履歴優先・α を unit 確認。
- `tests/test_server_frontend.py` の ETA 呼び出しを新 API に合わせて更新。
- node: `taskTiming` ラベル。
- lint/build + pytest。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | legacy | task_timing 永続化 | unit | existing pytest | round-trip | verified |
| AC-003 | legacy | ResultDetail 内訳 | review | existing | 表示維持 | verified |
| AC-010 | Enhance-66 | wall ペース | unit | `tests/test_progress_eta.py` | timing 平均と異なる wall 式 | verified |
| AC-011 | Enhance-66 | 履歴のみ | unit | same | status=history | verified |
| AC-012 | Enhance-66 | step / unavailable | unit | same + server tests | fallback | verified |
| AC-013 | Enhance-66 | 実測が重くなる | unit | same | α 増で measured 寄り | verified |
| AC-014 | Enhance-66 | UI ラベル | node | `taskTiming.node.test.ts` | 新 status 文言 | verified |
| AC-015 | Enhance-66 | remaining>0 で 0 禁止 | unit | server / progress_eta | eta_ms≠0 | verified |
| DEC-002 | Intent | 履歴は事前・実測優先 | unit | progress_eta | blend 性質 | verified |

## Manual QA Checklist

- [ ] 通常 run で 1 タスク完了後、ETA が実測ペース寄りに動く。
- [ ] 履歴のある被検で、開始直後（完了 0）に履歴ベースの残りが出る。
- [ ] ラベルが status に応じて変わる。

## Regression Checklist

- [ ] SSE lane 集計（holistic 分離）が変わらない。
- [ ] `task_timing` 保存と ResultDetail 表示が維持される。
- [ ] pre-run 見積の挙動が本変更だけで壊れない。

## Out of Scope

- pre-run UI 再設計、定数オンライン学習、包括専用 wall モデル。

## Open Questions

None
