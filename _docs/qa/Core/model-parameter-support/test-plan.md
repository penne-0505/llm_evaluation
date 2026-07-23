---
title: "QA Test Plan: Cross-provider model parameter support"
status: active
draft_status: n/a
qa_schema: 2
qa_status: planned
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/model-parameter-support/decision.md"
  - "_docs/archives/plan/Core/model-parameter-support/plan.md"
  - "_docs/qa/Core/model-parameter-support/verification.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Cross-provider model parameter support

## Source of Intent

- `_docs/intent/Core/model-parameter-support/decision.md`

## Decision Review Scope

- DEC-001 … DEC-004
- INV-001 (from DEC-001)

## Quality Goal

非対応モデルへ temperature を送らず評価を落とさない。OpenRouter / Gemini 3 の既存省略挙動を壊さない。

## Acceptance Criteria

- AC-001: `openai/gpt-5.6-luna`（同族含む）で subject_temp≠1 でも temperature を送らない。
- AC-002: OpenRouter catalog ベースの omit/send が既存テストで維持される。
- AC-003: Gemini 3 judge の temperature omit が共有層経由でも維持される。
- AC-004: 判定根拠が静的表または catalog 経由であり、adapter 散在ヒューリスティックだけに依存しない。

## Intent-derived Invariants

- INV-001 (from DEC-001): allows False のとき kwargs に temperature を含めない。

## Risk Assessment

- Medium: リクエスト shape 変更。unknown=omit で UI 温度が効かないモデルが増え得る。

## Test Strategy

- Unit: support layer、OpenAICompatibleAdapter stub、OpenRouter 既存、engine Gemini 3。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 / INV-001 | TODO | gpt-5.6-luna omit | unit | `tests/test_model_parameter_support.py` / adapters | kwargs に temperature なし | verified |
| AC-002 | TODO | OpenRouter catalog | unit | `tests/test_adapters.py` | 既存 omit/send 維持 | verified |
| AC-003 | TODO | Gemini 3 judge | unit | `tests/test_benchmark_engine.py` | temperature None | verified |
| AC-004 | Intent | 共有層利用 | diff review | adapters / engine | 散在決め打ち削除 | verified |

## Manual QA Checklist

- [ ] ローカルで `openai/gpt-5.6-luna` 短 run が 400 にならない（任意・unit で AC-001 充足）

## Regression Checklist

- [x] OpenRouter temperature catalog テスト
- [x] Gemini 3 judge omit
- [x] gpt-4o 系は temperature 送信可

## Out of Scope

- live 全モデル網羅、LM Studio 吸収

## Open Questions

None
