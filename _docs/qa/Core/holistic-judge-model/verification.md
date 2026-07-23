---
title: "QA Verification: Separate judge model for holistic evaluation"
status: active
draft_status: n/a
qa_schema: 2
qa_status: verified
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/holistic-judge-model/decision.md"
  - "_docs/qa/Core/holistic-judge-model/test-plan.md"
  - "_docs/archives/plan/Core/holistic-judge-model/plan.md"
  - "_docs/archives/survey/Core/holistic-judge-model/survey.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# QA Verification: Separate judge model for holistic evaluation

## Summary

`RunRequest.holistic_judge_models`（optional、空は `judge_models` fallback）を追加し、
holistic 実行時のみ別 adapter セットを `run_holistic_task(..., judge_adapters=...)` で注入する。
結果 JSON は `holistic_judge_models` を `judge_models` と別キーで記録し、preset /
Settings / Run / ResultDetail まで一貫して分離できる。strict 検証は従来どおり
per-task `judge_models` のみ。

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
uv run --with pytest python -m pytest tests/test_server_frontend.py::TestHolisticJudgeModels tests/test_benchmark_engine.py::TestBenchmarkEngine::test_run_holistic_task_uses_override_judge_adapters tests/test_benchmark_engine.py::TestBenchmarkEngine::test_holistic_task_result_includes_explicit_empty_subject_prompt -q --tb=short
npx --prefix frontend tsx --test frontend/src/lib/executionPresets.node.test.ts frontend/src/api/client.node.test.ts frontend/src/store/settingsStore.node.test.ts
npm run lint --prefix frontend
npm run build --prefix frontend
```

Result:

```text
pytest (Feat-46 focused): 5 PASS
frontend node tests: 13 PASS
frontend lint: PASS
frontend build: PASS
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `TestHolisticJudgeModels` (3 tests) | PASS | AC-001 / AC-005 / INV-001 / INV-002 / DEC-001 |
| `test_run_holistic_task_uses_override_judge_adapters` | PASS | AC-002 / DEC-002 |
| `test_holistic_task_result_includes_explicit_empty_subject_prompt` | PASS | Enhance-35 / Bug-36 回帰 |
| `executionPresets.node.test.ts` (holistic round-trip含む) | PASS | AC-004 / DEC-004 |
| `client.node.test.ts` (`holistic_judge_models` + 3-pattern body) | PASS | AC-003 / AC-005 |
| `settingsStore.node.test.ts` | PASS | preset schema with `holisticJudgeModels` |
| `npm run lint --prefix frontend` | PASS | |
| `npm run build --prefix frontend` | PASS | |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| Run 画面で holistic judge を別指定して live run | Deferred | live provider smoke は Out of Scope。unit / node で request・adapter 分離をカバー |
| holistic judge 未指定の fallback 完走 | Deferred | `_effective_holistic_judge_models` + body 3-pattern で意味論を検証 |
| preset 保存 → 復元 | PASS | node: capture → resolve round-trip（空 = fallback 含む） |
| strict ON で holistic override 可能 | PASS | review: `build_strict_mode_metadata` は `judge_models` のみ。Settings HolisticSection は strict 非ロック |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | `RunRequest.holistic_judge_models`、`ExecutionPresetConfig.holisticJudgeModels`、Settings HolisticSection UI、RunPage → `buildRunRequestBody` |
| AC-002 | PASS | server holistic ブロックで別解決 + `run_holistic_task(judge_adapters=...)`。engine override unit |
| AC-003 | PASS | `benchmark_result["holistic_judge_models"]`、`convertBenchmarkResult`、ResultDetail「包括評価モデル」表示 |
| AC-004 | PASS | capture / resolve / settingsStore apply / persist に `holisticJudgeModels` |
| AC-005 | PASS | Intent DEC-001..005 維持。通常のみ / holistic override / 両方の 3 パターン test |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | optional field + 空配列 fallback。backend / frontend / preset で一致 |
| DEC-002 | PASS | standard path の engine adapters は不変。holistic のみ override 注入 |
| DEC-003 | PASS | 結果 JSON に別キー。`judge_models` を上書きしない |
| DEC-004 | PASS | preset capture/resolve に含め、空 = fallback |
| DEC-005 | PASS | 同一継続は空 fallback で維持。strict は per-task のみ照合 |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | `_effective_holistic_judge_models(["judge-a"], []) == ["judge-a"]` |
| INV-002 | PASS | `run_holistic=false` 時は server holistic ブロック（adapter 解決）に入らない gate |

## Deferred / Not Covered

- live provider smoke（QA Out of Scope）
- holistic 専用 temperature / system prompt（Plan Non-Goals）
- strict official holistic judge preset（DEC-005 Why not）

## Residual Risks

None

## Follow-up TODOs

None
