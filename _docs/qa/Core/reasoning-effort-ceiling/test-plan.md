---
title: "QA Test Plan: Provider-aware reasoning effort ceiling"
status: active
draft_status: n/a
qa_status: planned
risk: High
qa_schema: 2
created_at: 2026-08-01
updated_at: 2026-08-01
references:
  - "_docs/intent/Core/reasoning-effort-ceiling/decision.md"
  - "_docs/plan/Core/reasoning-effort-ceiling/plan.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Provider-aware reasoning effort ceiling

## Source of Intent

- TODO: `Core-Enhance-75`
- Plan: `_docs/plan/Core/reasoning-effort-ceiling/plan.md`
- Intent: `_docs/intent/Core/reasoning-effort-ceiling/decision.md`

## Quality Goal

各 provider が受理する `xhigh` 以下の最上位 effort を、被験と judge の全経路で同じ規則から送信し、
unsupported model や custom endpoint の既存成功経路を壊さない。

## Acceptance Criteria

- AC-001: 被験通常・native tool・judge が同じ adapter effort 契約を使う。
- AC-002: OpenRouter / OpenAI / Google / Anthropic / LM Studio の値と field shape が公式 API に合う。
- AC-003: `max` と unsupported / unknown provider への無効 effort を送らない。
- AC-004: regression と repository baseline suite が通る。
- AC-005: main / `v0.17.0` が remote へ反映され、release workflow と asset が確認できる。

## Decision Review Scope

- DEC-001: `xhigh` ceiling と high fallback が保たれるか。
- DEC-002: protocol shape が adapter 内に閉じるか。
- DEC-003: capability unknown を omit するか。
- DEC-004: 被験 / judge が単一契約を使うか。
- DEC-005: custom provider へ推測送信しないか。

## Intent-derived Invariants

- INV-001: effort payload は全 call role で adapter 契約から取得する。
- INV-002: `max` を送らず、provider / model が受理する値と shape のみ送る。

## Risk Assessment

- Risk level: High
- Risk rationale: 外部 API payload、課金量、全評価 run の成功可否に影響する。
- Regression risk: unsupported parameter で request が 400 になり、評価全体が失敗する。
- Data safety risk: 保存 schema 変更なし。失敗 run の部分保存挙動は既存のまま。
- Security / privacy risk: secret / prompt / result の新規永続化なし。
- UX risk: reasoning token 増加により ETA と費用が増えるが、既存 estimate は actual usage を保存する。
- Agent misbehavior risk: None（agent workflow 変更ではない）。

## Test Strategy

- Unit: static resolver、capability gate、adapter SDK kwargs / `extra_body`。
- Integration: engine の subject normal / native tools / judge payload parity。
- E2E: backend / frontend / docs baseline。
- Manual QA: official docs matrix と diff を照合し、`max` / legacy hard-coded `high` を検索する。
- Validator / static check: TODO / intent / QA / links / Markdown。
- Diff review: DEC-001..005 と INV-001..002 の逸脱、unrelated change、secret 混入を確認する。

## Test Matrix

| ID | Source | Requirement / Optional Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO / INV-001 | subject normal / native / judge parity | integration | `uv run pytest tests/test_benchmark_engine.py` | 3経路が adapter 返却 payload を保持 | verified |
| AC-002 | TODO / DEC-002 | provider 別 value / shape | unit | `uv run pytest tests/test_model_parameter_support.py tests/test_adapters.py tests/test_anthropic_adapter.py` | OR/OpenAI/Google/Anthropic/LM の kwargs が期待値一致 | verified |
| AC-003 | TODO / INV-002 | max 禁止、unsupported / custom omit | unit + static | resolver tests + `rg` | `max` payload 0件、unknown は None | verified |
| AC-004 | TODO | repository baseline | regression | `uv run pytest`; frontend lint/test/build; docs gates | 全 command exit 0 | verified |
| AC-005 | TODO | push / tag / release | remote manual | `git ls-remote`, `gh run`, `gh release view` | main/tag SHA と4 assets確認 | verified |

## Manual QA Checklist

- [x] OpenAI / Anthropic / Google / LM Studio の公式 field と enum を再照合する。
- [x] ローカル LM Studio が起動していないため live payload 受理を deferred と明記する。
- [x] `v0.17.0` の Linux / Windows workflow と checksum asset を確認する。

## Regression Checklist

- [x] preferred-host merge が reasoning payload を保持する。
- [x] reasoning 非対応 model は extra params なしで従来どおり呼べる。
- [x] native tool loop の全 step と最終 completion で effort が維持される。
- [x] temperature / max token parameter support の既存 tests が通る。

## High-risk Checklist

- [x] Rollback or recovery path is documented.
- [x] Data safety has been checked.
- [x] Security / privacy implications have been checked.
- [x] Failure mode is understood.

## Out of Scope

- Paid provider を使う live response quality 比較。
- custom provider の capability schema。
- LM Studio native endpoint への移行。

## Open Questions

- None
