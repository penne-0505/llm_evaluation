---
title: "QA Verification: Fix time ROI calculation (subject vs judge timing)"
status: active
draft_status: n/a
qa_schema: 2
qa_status: verified
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-24
references:
  - "_docs/intent/Core/time-roi-task-timing/decision.md"
  - "_docs/qa/Core/time-roi-task-timing/test-plan.md"
  - "_docs/archives/plan/Core/time-roi-task-timing/plan.md"
  - "_docs/archives/survey/Core/time-roi-task-timing/survey.md"
related_issues: []
related_prs: []
---

# QA Verification: Fix time ROI calculation (subject vs judge timing)

## Summary

時間 ROI の分母を run wall-clock（`execution_duration_ms`）から、通常タスク
`task_timing` の subject + judge 合算へ統一した。run payload / summary index に
`timing_summary` を付与し、ResultDetail `CostSection` と Dashboard
`buildModelAggregates` / `formatTimeRoi` が同一定義を参照する。欠落時は N/A
（暗黙 wall-clock フォールバックなし）。

2026-07-24（DEC-005）: 分子を `averageScore × taskCount`（Σscore）、単位を **点/分** に
変更。平均点÷合計秒（点/秒）は廃止。長時間 run で 0.0 → `—` になる不具合を解消。

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
uv run pytest tests/test_result_storage.py tests/test_cost_estimator.py tests/test_server_frontend.py -q
uv run pytest -q
npx --prefix frontend tsx --test frontend/src/lib/timeRoi.node.test.ts frontend/src/api/client.node.test.ts frontend/src/lib/taskTiming.node.test.ts
npm run lint --prefix frontend
npm run build --prefix frontend
git diff --check
```

Result:

```text
targeted backend: 43 PASS
backend full pytest: 129 PASS (+ 23 subtests)
frontend node tests: 13 PASS（timeRoi / client / taskTiming）
frontend lint: PASS
frontend production build: PASS
git diff --check: PASS
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `test_summary_includes_timing_summary_from_task_timing` | PASS | AC-001 / DEC-002 |
| `test_summary_timing_none_when_task_timing_missing` | PASS | AC-003 |
| `test_summarize_task_timing_matches_usage_and_rejects_partial` | PASS | AC-004 |
| `test_task_timing_matches_usage_total_duration` | PASS | AC-004 既存整合 |
| `timeRoi.node.test.ts` shared denominator | PASS | AC-002 / DEC-001 |
| `timeRoi.node.test.ts` legacy N/A | PASS | AC-003 / DEC-003 |
| `timeRoi.node.test.ts` DEC-005 点/分・多タスク | PASS | 2026-07-24 re-check |
| `client.node.test.ts` timing_summary map | PASS | DEC-002 |
| backend full suite | PASS | 129件 |
| frontend lint / build | PASS | |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| judge 並列 ON で ROI が wall-clock 誤用しない | PASS（unit） | parallel-like fixture: wall-clock > timing total でも ROI 分母は timing |
| ResultDetail と Dashboard が同一定義 | PASS（unit） | `timeRoi.ts` 共有 helper |
| 旧 result で時間 ROI が N/A | PASS（unit） | timing 欠落 → N/A、executionDurationMs 未使用 |
| 被検 / judge タブが各内訳 ms を分母に使う | PASS（unit） | `resolveTimeRoiDenominator` |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | `summarize_task_timing` + ResultStorage summary + server save |
| AC-002 | PASS | ResultDetail / Dashboard が `timeRoi.ts` の subject+judge 合算を使用 |
| AC-003 | PASS | 欠落時 N/A 固定。wall-clock ラベル経路は採用せず |
| AC-004 | PASS | `summarize_task_timing` total == usage `total_duration_ms` |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | ROI 分母は `task_timing` 合算。`execution_duration_ms` はメタデータとして残すのみ |
| DEC-002 | PASS | `timing_summary` を result + summary index に付与 |
| DEC-003 | PASS | 欠落時は完全 N/A（implementation で 1 方針に固定） |
| DEC-004 | PASS | Dashboard `runProcessingDurationMs` が wall-clock を除外 |
| DEC-005 | PASS | Σscore/処理分 → 点/分。unit test で多タスク同効率・直近 run 規模を確認 |

## Invariant Coverage

None

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| live Dashboard / Detail 目視 | unit + code review で定義一致を確認。live smoke は未実施 | 任意 |
| holistic timing の Dashboard 算入 | Intent Non-Goals / follow-up | 必要なら別 TODO |
| 旧 result の時間 ROI | `task_timing` 欠落時は N/A（意図的）。過去 run との数値比較は不可 | None |
| Dashboard 数値の定義変更 | wall-clock 時代と処理時間ベースで値が変わる（意図的） | release note 任意 |
| 2026-07-24 点/秒→点/分・Σscore | DEC-005。コスト ROI（点/$）と単位パターンを揃えた | None |

## Residual Risks

None

## Follow-up TODOs

None

## Completion Decision

- TODO `Core-Enhance-41` は Verification PASS。エントリ削除と plan/survey archive は parent に委ねる。
