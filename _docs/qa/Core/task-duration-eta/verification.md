---
title: "QA Verification: Task duration estimates and ETA on results"
status: active
draft_status: n/a
qa_schema: 2
qa_status: verified
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/task-duration-eta/decision.md"
  - "_docs/qa/Core/task-duration-eta/test-plan.md"
  - "_docs/archives/plan/Core/task-duration-eta/plan.md"
  - "_docs/archives/survey/Core/task-duration-eta/survey.md"
related_issues: []
related_prs: []
---

# QA Verification: Task duration estimates and ETA on results

## Summary

各通常タスク結果に `task_timing: { subject_duration_ms, judge_duration_ms }` を永続化し、
multi-turn subject の `_merge_subject_usage` が `duration_ms` を合算するようにした。
SSE progress に `eta_ms` / `eta_status`（measured / step_fallback / unavailable）を追加し、
RunPage でラベル付き ETA、ResultDetail で per-task 被検 / judge 所要時間を表示する。
Dashboard の時間 ROI は触っていない（Enhance-41）。

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
uv run pytest tests/test_benchmark_engine.py tests/test_result_storage.py tests/test_server_frontend.py tests/test_cost_estimator.py -q
uv run pytest -q
npx --prefix frontend tsx --test frontend/src/api/client.node.test.ts frontend/src/lib/taskTiming.node.test.ts
npm run lint --prefix frontend
npm run build --prefix frontend
git diff --check
```

Result:

```text
targeted backend: 63 PASS
backend full pytest: 122 PASS (+ 23 subtests)
frontend node tests: 9 PASS（taskTiming + client 変換を含む）
frontend lint: PASS
frontend production build: PASS
git diff --check: PASS
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `test_task_result_includes_subject_and_judge_usage`（task_timing） | PASS | AC-001 / DEC-001 |
| `test_merge_subject_usage_sums_duration_ms` | PASS | AC-001 multi-turn |
| `test_build_task_timing_sums_judge_runs` | PASS | DEC-001 |
| `test_save_round_trip_preserves_task_timing` | PASS | AC-001 storage |
| `test_progress_eta_uses_completed_task_average` | PASS | AC-002 / DEC-002 |
| `test_progress_eta_step_fallback_only_when_no_completed_timings` | PASS | AC-004 / DEC-002 |
| `test_progress_eta_unavailable_without_measurements_or_steps` | PASS | AC-004 / DEC-003 |
| `test_task_timing_matches_usage_total_duration` | PASS | DEC-001 usage 整合 |
| `client.node.test.ts` task_timing 変換 | PASS | AC-003 |
| `taskTiming.node.test.ts` ラベル | PASS | AC-004 / DEC-003 |
| backend full suite | PASS | 122件 |
| frontend lint / build | PASS | RunPage / ResultDetail 型含む |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| 通常 run 実行中、1 タスク完了後に ETA が更新される | PASS（unit） | measured ETA helper + SSE payload 組み込みを確認。live run は未実施 |
| 初回（完了 0 件）では推定不可または step ベース | PASS（unit + code review） | `eta_status` ラベルを RunPage に表示 |
| 結果詳細で被検 / judge 所要時間が読める | PASS（code review + 変換 test） | TaskResultCard に内訳表示 |
| 旧フォーマット result（task_timing 欠落）でクラッシュしない | PASS（変換 test） | `taskTiming` undefined → 非表示 |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | `TaskResult.to_dict()` の `task_timing` + storage round-trip + duration 合算 |
| AC-002 | PASS | `_compute_progress_eta` + progress SSE payload + RunPage ETA 表示 |
| AC-003 | PASS | client 変換 + ResultDetail TaskResultCard 内訳 |
| AC-004 | PASS | step_fallback / unavailable と UI ラベル（確定値風にしない） |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | タスク JSON に `task_timing` を正典として追加。usage 合算と同一 fixture で一致 |
| DEC-002 | PASS | 完了タスク実測平均を優先。完了 0 のみ step 比率。不可時 unavailable |
| DEC-003 | PASS | RunPage が「推定（実測平均）」「推定（step ベース）」「推定不可」を明示 |

## Invariant Coverage

None

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| live SSE ETA 体感 | unit / code review のみ。並列 subject の体感確認は未実施 | Enhance-41 着手前の手動 smoke で可 |
| holistic 専用 ETA | Plan Non-Goals。通常 lane 完了後は remaining=0 | 必要なら follow-up |

## Residual Risks

None

## Follow-up TODOs

None

## Completion Decision

- TODO `Core-Feat-34` は Verification PASS のため完了扱い可能。エントリ削除と plan archive は parent に委ねる。
