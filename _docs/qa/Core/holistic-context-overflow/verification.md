---
title: "QA Verification: Holistic bundled_responses context overflow handling"
status: active
draft_status: n/a
qa_schema: 2
qa_status: verified
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/holistic-context-overflow/decision.md"
  - "_docs/qa/Core/holistic-context-overflow/test-plan.md"
  - "_docs/archives/plan/Core/holistic-context-overflow/plan.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# QA Verification: Holistic bundled_responses context overflow handling

## Summary

`run_holistic_task` に固定 overhead 差引の文字予算チェックと、末尾 task 優先 drop /
単一 task 回答本文 truncate を実装した。overflow の有無は holistic `TaskResult.bundling_metadata`
と engine warning ログで追跡できる。通常規模の `_build_bundled_responses` 形式は不変。
frontend の ResultDetail / Dashboard は触っていない（Plan Non-Goals: JSON / ログで足りる）。

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
uv run --with pytest python -m pytest tests/test_benchmark_engine.py -k 'holistic or bundling_metadata or build_bundled or overflow or fit_bundled or resolve_judge_context' -v
uv run --with pytest python -m pytest tests/test_benchmark_engine.py -q
```

Result:

```text
overflow-related tests: 6 PASS
test_benchmark_engine.py full: 17 PASS
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `test_build_bundled_responses_preserves_task_heading_format` | PASS | AC-003 / INV-001 |
| `test_fit_bundled_responses_drops_trailing_tasks_first` | PASS | AC-001 / DEC-003 |
| `test_fit_bundled_responses_truncates_oversized_single_response` | PASS | AC-001 / DEC-003 |
| `test_resolve_judge_context_limit_uses_conservative_default` | PASS | DEC-001 |
| `test_holistic_overflow_records_bundling_metadata_and_bounds_judge_prompt` | PASS | AC-002 / AC-004 / INV-002 |
| `test_holistic_task_result_includes_explicit_empty_subject_prompt` | PASS | Core-Bug-36 回帰 + `action: none` metadata |
| `tests/test_benchmark_engine.py` full | PASS | 17件 |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| 多数タスク・長文の live run | Deferred | unit で oversized fixture をカバー。live provider smoke は Out of Scope |
| Result 画面での metadata 表示 | Deferred | Plan Non-Goals。結果 JSON / ログで検知可能 |
| 通常規模で `truncated: false` | PASS | unit: `test_holistic_task_result_includes_explicit_empty_subject_prompt` |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | `_fit_bundled_responses_to_budget` の drop / truncate unit test |
| AC-002 | PASS | `bundling_metadata` が `TaskResult.to_dict()` に入り、warning ログも出力 |
| AC-003 | PASS | `_build_bundled_responses` の byte-level 形式一致 test |
| AC-004 | PASS | oversized holistic run で mock が raw oversized bundle を受け取らず、aggregated が残る |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | overhead（system + empty user envelope + safety + capped output reserve）差引。未知 model は 32,768 token default |
| DEC-002 | PASS | split / aggregate ループなし。単一 `_run_judge_evaluation` のまま |
| DEC-003 | PASS | 末尾 task drop → 残 task の回答本文のみ truncate。見出し・入力プロンプト維持 |
| DEC-004 | PASS | `bundling_metadata` に truncated / action / dropped_tasks / sizes / limit を記録 |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | 非超過時の `### タスク:` / `---` 形式維持 test |
| INV-002 | PASS | overflow 分岐で `bundling_metadata.truncated === true` を assert |

## Deferred / Not Covered

- live provider による context window 取得と smoke（Plan / QA Out of Scope）
- frontend 専用 truncation 警告 UI（Plan Non-Goals）
- 分割評価と chunk スコア集約（Intent follow-up）
- 文字数 heuristic（4 chars/token）は tokenizer より粗い。adapter が信頼できる token 上限を返す時点で DEC-001 revisit。
- 複数 judge がある場合は最厳 context を共有 bundled に適用するため、広い window の judge にも同じ切り詰めが掛かる。

## Residual Risks

None

## Follow-up TODOs

None
