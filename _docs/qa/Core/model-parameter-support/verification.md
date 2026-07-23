---
title: "QA Verification: Cross-provider model parameter support"
status: active
draft_status: n/a
qa_schema: 2
qa_status: verified
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/model-parameter-support/decision.md"
  - "_docs/archives/plan/Core/model-parameter-support/plan.md"
  - "_docs/qa/Core/model-parameter-support/test-plan.md"
related_issues: []
related_prs: []
---

# QA Verification: Cross-provider model parameter support

## Summary

`core/model_parameter_support` を導入し、OpenAICompatible / OpenRouter / Anthropic と
engine の Gemini 3 temperature omit を共有層に寄せた。`openai/gpt-5.6-luna` は
temperature を送らない。engine は model 名推定ではなく `adapter.PROVIDER` を使う。

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
uv run pytest tests/test_model_parameter_support.py tests/test_adapters.py \
  tests/test_benchmark_engine.py::TestBenchmarkEngine::test_gemini_3_judge_omits_temperature \
  tests/test_benchmark_engine.py::TestBenchmarkEngine::test_judge_temperature_uses_adapter_provider_not_model_prefix -q
```

Result: PASS（model_parameter_support + adapters 回帰 + Gemini 3 + adapter.PROVIDER）

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `tests/test_model_parameter_support.py` | PASS | gpt-5.6-luna omit、gpt-4o send、OR catalog、gemini-3 |
| `tests/test_adapters.py` OpenRouter temperature | PASS | 既存 omit 維持 |
| `test_gemini_3_judge_omits_temperature` | PASS | 共有層経由、PROVIDER=openrouter |
| `test_judge_temperature_uses_adapter_provider_not_model_prefix` | PASS | google-ai-studio + bare model id |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| ローカル `openai/gpt-5.6-luna` 短 run | deferred | サーバー再起動後にユーザー再試行 |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | adapter stub: kwargs に temperature なし |
| AC-002 | PASS | OpenRouter catalog tests |
| AC-003 | PASS | Gemini 3 engine test |
| AC-004 | PASS | adapters は `apply_temperature` / `allows` 経由 |
| AC-005 | PASS | regression commands above |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | 単一入口 `allows` / `apply_temperature` |
| DEC-002 | PASS | OR catalog → static → unknown omit |
| DEC-003 | PASS | engine は `adapter.PROVIDER` + 共有層 |
| DEC-004 | PASS | max_completion_tokens も共有ヘルパ |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | gpt-5.6-luna unit |

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| Live re-run | ユーザー環境の key / 課金 | Settings で同モデル再実行 |
| OpenRouter catalog 未取得時 omit | DEC-002 意図（旧実装は送信） | 静的表拡充・catalog 監視 |
| 静的表漏れで UI 温度が効かない | Intent Consequences | 表追記 |

## Residual Risks

None

## Follow-up TODOs

None
