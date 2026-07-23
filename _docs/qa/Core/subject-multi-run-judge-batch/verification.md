---
title: "QA Verification: Subject multi-run judge batch evaluation"
status: active
draft_status: n/a
qa_schema: 2
qa_status: partial
risk: High
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/subject-multi-run-judge-batch/decision.md"
  - "_docs/qa/Core/subject-multi-run-judge-batch/test-plan.md"
  - "_docs/archives/plan/Core/subject-multi-run-judge-batch/plan.md"
  - "_docs/archives/survey/Core/subject-multi-run-judge-batch/survey.md"
related_issues: []
related_prs: []
---

# QA Verification: Subject multi-run judge batch evaluation

## Summary

`subject_runs`（1–5）を RunRequest / preset / Settings / Run UI に追加し、
`BenchmarkEngine.run_task` が被験を N 回実行して list-eval 用に束ね、judge へ 1 入力として渡す。
holistic の `_build_bundled_responses` とは別の `_build_bundled_subject_runs` を使用（INV-002）。
`judge_runs` は独立（INV-001）。結果 JSON は `subject_runs[]` + 代表 `response`（DEC-003）。
部分失敗は `[ERROR]` 列挙で judge 続行、N>1 全失敗は task fail（DEC-004）。
backend / frontend 自動テストは成功。live API 目視と ResultDetail multi-run 専用 node assert は未実施。

## Verification Verdict

Verdict: PARTIAL

## Commands Run

```bash
uv run pytest tests/test_benchmark_engine.py tests/test_prompt_contracts.py \
  tests/test_server_frontend.py tests/test_cost_estimator.py tests/test_result_storage.py -q
uv run pytest -q
npx --prefix frontend tsx --test \
  frontend/src/lib/executionPresets.node.test.ts \
  frontend/src/api/client.node.test.ts
npm run lint --prefix frontend
npm run build --prefix frontend
deno run --allow-read --allow-env --allow-run=git scripts/validate-qa.mjs
deno run --allow-read --allow-env --allow-run=git scripts/validate-intent.mjs
```

Result:

```text
targeted backend: 90 PASS (+ subtests)
backend full pytest: 151 PASS (+ 23 subtests)
frontend node tests: 14 PASS
frontend lint: PASS
frontend production build: PASS
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `test_subject_runs_n_batches_to_one_judge_input` | PASS | AC-002 / DEC-001 / INV-001 |
| `test_subject_runs_one_keeps_plain_judge_answer` | PASS | AC-003 / INV-003 |
| `test_partial_subject_failure_includes_error_and_continues` | PASS | DEC-004 |
| `test_all_subject_failures_raise_when_n_gt_one` | PASS | DEC-004 |
| `test_subject_bundler_is_separate_from_holistic_bundler` | PASS | INV-002 |
| `test_build_bundled_subject_runs_extreme_length_does_not_raise` | PASS | AC-005 |
| `test_clamp_subject_runs` / RunRequest clamp | PASS | DEC-005 / AC-005 |
| `test_prompt_contracts` multi-run 指示 | PASS | AC-003 |
| `test_save_preserves_subject_runs_array` | PASS | AC-004 / DEC-003 |
| `test_summarize_subject_usage_prefers_subject_runs_array` | PASS | AC-004 |
| `executionPresets.node.test.ts` subjectRunCount | PASS | AC-001 |
| `client.node.test.ts` subject_runs body/convert | PASS | AC-001 / AC-004 |
| backend full suite | PASS | 151件 |
| frontend lint / build | PASS | |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| `subject_runs=1` で従来同等に完了 | PASS（unit） | N=1 plain judge answer |
| `subject_runs=3` で被験 progress 識別 | PASS（unit） | progress メッセージ `被験LLM i/N` |
| 結果画面に run #1..#N | PASS（convert + code review） | `client.node.test` が `subjectRuns` 変換を検証。ResultDetail 試行タブは diff review（専用 node assert なし） |
| usage / コストが run 数に応じて増 | PASS（unit） | `test_summarize_subject_usage_prefers_subject_runs_array` |
| エラー混在で judge 続行 | PASS（unit） | `[ERROR]` 列挙 |
| live API smoke | DEFERRED | Out of Scope（外部モデル依存） |

## High-risk Checklist

- [x] Rollback: `subject_runs` 配線・`_build_bundled_subject_runs`・UI slider を戻すのみ。旧 JSON（配列なし）は単一 `response` として読める
- [x] Data safety: additive schema（`subject_runs[]` / `subject_run_count`）。既存 run 削除・上書きなし。`test_save_preserves_subject_runs_array` で round-trip
- [x] Security / privacy: bundled 本文は既存 untrusted envelope 内。新権限・secret 経路なし（Intent / Plan 記載どおり）
- [x] Failure mode: 部分失敗は `[ERROR]` 列挙で judge 続行、N>1 全失敗は raise（engine unit）。極端長は builder 例外なし（sanity）。コストは最大 5 倍に clamp（DEC-005）

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | RunRequest / preset / Settings slider / RunPage / buildRunRequestBody |
| AC-002 | PASS | N 被験 + bundled judge、judge_runs 独立 |
| AC-003 | PASS | system prompt multi-run 指示、N=1 後方互換 |
| AC-004 | PARTIAL | subject_runs[] 保存・usage 合算は unit。UI 表示は convert + ResultDetail code review（専用 ResultDetail node assert は未追加） |
| AC-005 | PASS | Intent DEC-005/006、clamp、1/N/エラー混在 tests |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | list-eval bundled、1 スコアセット、別 builder |
| DEC-002 | PASS | `subject_runs` / `judge_runs` 独立フィールド |
| DEC-003 | PASS | run 配列 + 代表 `response` + `subject_run_count` |
| DEC-004 | PASS | 部分 `[ERROR]` 続行、N>1 全失敗 raise |
| DEC-005 | PASS | max 5 clamp、コスト比例を Intent に記録 |
| DEC-006 | PASS | strict は subject_runs を固定しない |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | subject=3, judge_runs=2 → judge.call_count=2 |
| INV-002 | PASS | `_build_bundled_subject_runs` ≠ `_build_bundled_responses` |
| INV-003 | PASS | N=1 は見出しなし単一回答 |

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| live API smoke | Out of Scope（外部モデル依存） | 運用時任意 |
| Manual live N=3 目視 | unit / code review で代替 | 任意 |

## Residual Risks

- live API での N=3 目視・progress・ResultDetail 試行タブの視覚確認は未実施（unit / convert / code review で代替）。
- 極端に長い被験回答 × N=5 で judge コンテキスト上限に当たる実 API 挙動は、builder 例外なし sanity のみ。truncate は Out of Scope。
- ResultDetail の multi-run UI に専用 node test が無いため、表示回帰は convert 契約と lint/build に依存する。

## Follow-up TODOs

- 任意: ResultDetail 試行タブの node assert（N run 見出し・error run）を追加すると AC-004 UI 証跡が自動テスト単独で閉じる。
- live smoke は運用時任意（Out of Scope 維持）。

## Completion Decision

- TODO `Core-Feat-44` 実装核は Intent 整合。Verification は live 目視 / ResultDetail multi-run node 欠落により PARTIAL。
  High-risk Checklist は unit 証跡で記録済み。エントリ削除は parent に委ねる。
