---
title: "QA Test Plan: Provider-native output token limits"
status: active
draft_status: n/a
qa_status: in-progress
risk: High
qa_schema: 2
created_at: 2026-08-05
updated_at: 2026-08-05
references:
  - "_docs/intent/Core/provider-native-output-limits/decision.md"
  - "_docs/archives/plan/Core/provider-native-output-limits/plan.md"
  - "_docs/intent/Core/model-parameter-support/decision.md"
  - "_docs/intent/Core/holistic-context-overflow/decision.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Provider-native output token limits

## Source of Intent

- TODO: `Core-Enhance-77`
- Plan: `_docs/archives/plan/Core/provider-native-output-limits/plan.md`
- Intent: `_docs/intent/Core/provider-native-output-limits/decision.md`

## Quality Goal

評価role/protocolの違いにかかわらずapp固定capを除き、optional providerではfield省略、Anthropicでは
実model metadataのnative maximumを使い、metadata不明を隠さない。

## Acceptance Criteria

- AC-001: 全subject評価経路がNoneを渡す。
- AC-002: 全judge評価経路がNoneを渡す。
- AC-003: optional adapterはNoneをomitしexplicit値を維持する。
- AC-004: Anthropicはcatalog/live model maximumを使いfallbackしない。
- AC-005: holistic reserveはrequest capから分離される。
- AC-006: baseline suiteがすべて成功する。

## Decision Review Scope

- DEC-001: engineが数値capを所有しない。
- DEC-002: optional protocolはfieldをomitする。
- DEC-003: Anthropic required limitはprovider metadataから解決する。
- DEC-004: holistic reserveとrequest capを別責務にする。
- model-parameter-support DEC-001/004: request parameter shapingを共有契約へ寄せる。
- holistic-context-overflow DEC-001: input budget heuristicの目的を維持する。

## Intent-derived Invariants

- INV-001: subject/judge評価call siteは数値capを渡さない。
- INV-002: Anthropic metadata不明時は固定値fallback requestを送らない。

## Risk Assessment

- Risk level: High
- Risk rationale: 外部API request shape、latency、cost、context overflowに影響する。
- Regression risk: Optional型変更でadapter/stub/tool call経路の一部だけ旧defaultが残る可能性がある。
- Data safety risk: 結果schemaと保存dataは変更しない。
- Security / privacy risk: Models APIは既存credentialを使い、keyやresponseをlog/cacheへ追加しない。
- UX risk: 長い生成で待ち時間/費用が増え、metadata不明custom endpointは明示errorになる。
- Agent misbehavior risk: paid live completionを自動verificationに含めず、mock/SDK schemaで確認する。

## Test Strategy

- Unit: adapter kwargs、catalog metadata、Anthropic resolver/cache/error。
- Integration: BenchmarkEngine subject/judge/tool/holistic call records。
- E2E: backend/frontend/docs baseline。
- Manual QA: official docs、installed SDK signatures、static cap scan。
- Validator / static check: docs validators、Markdown lint、`rg`。
- Diff review: explicit probe limitを誤って消していないことを確認する。

## Test Matrix

| ID | Source | Requirement / Optional Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 / INV-001 | TODO / DEC-001 | subject text/native/finalはNone | integration | `tests/test_benchmark_engine.py` | 全recordがNone | verified |
| AC-002 / INV-001 | TODO / DEC-001 | judge standard/holisticはNone | integration | `tests/test_benchmark_engine.py` | 全recordがNone | verified |
| AC-003 | TODO | optional adapter omit + explicit互換 | unit | `tests/test_adapters.py`, `tests/test_model_parameter_support.py` | Noneでmax fieldなし、integerでfieldあり | verified |
| AC-004 / INV-002 | TODO / DEC-003 | Anthropic metadata resolver | unit | `tests/test_anthropic_adapter.py`, `tests/test_model_catalog.py` | catalog/live/cache/error分岐 | verified |
| AC-005 | TODO | holistic reserve分離 | unit/static | `core/benchmark_engine.py`, engine tests | reserve名がmax requestに使われない | verified |
| AC-006 | TODO | full regression | baseline | backend/frontend/docs commands | 全exit 0 | verified |

## Manual QA Checklist

- [x] Anthropic official docsのModels API `max_tokens` とMessages required fieldを照合する。
- [x] installed SDKの`models.retrieve` / `messages.create` signatureを照合する。
- [x] 評価call siteに`16384`または別の数値capが残っていない。

## Regression Checklist

- [x] connection probeの明示`max_tokens=8`は維持される。
- [x] preferred host retry / reasoning effort / temperature shapingが変わらない。
- [x] holistic overflow metadataと非overflow formatが変わらない。

## High-risk Checklist

- [x] Rollback or recovery path is documented.
- [x] Data safety has been checked.
- [x] Security / privacy implications have been checked.
- [x] Failure mode is understood.

## Out of Scope

- provider native maximumそのものの解除。
- paid live completion、UI max token setting、Batches beta。

## Open Questions

- None
