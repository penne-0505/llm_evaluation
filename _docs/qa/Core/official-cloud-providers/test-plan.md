---
title: "QA Test Plan: Ollama Cloud and OpenCode Go official providers"
status: active
draft_status: n/a
qa_status: in-progress
risk: High
qa_schema: 2
created_at: 2026-08-05
updated_at: 2026-08-05
references:
  - "_docs/intent/Core/official-cloud-providers/decision.md"
  - "_docs/intent/Core/openai-compat-anthropic-providers/decision.md"
  - "_docs/plan/Core/official-cloud-providers/plan.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Ollama Cloud and OpenCode Go official providers

## Source of Intent

- TODO: `Core-Enhance-76`
- Plan: `_docs/plan/Core/official-cloud-providers/plan.md`
- Intent: `_docs/intent/Core/official-cloud-providers/decision.md`
- Related intent: `_docs/intent/Core/openai-compat-anthropic-providers/decision.md`

## Quality Goal

ユーザーが base URL や環境変数名を推測せず両 provider を設定でき、既存 registry / adapter / secret
境界を壊さずにモデル取得と評価 routing へ到達できることを保証する。

## Acceptance Criteria

- AC-001: 2 provider が公式 base URL を持つ builtin として常駐する。
- AC-002: 公式 API key 名と UI 保存先が一致し、secret が出力へ露出しない。
- AC-003: model catalog と Chat Completions routing が provider prefix / upstream id を正しく扱う。
- AC-004: 既存 registry が欠損・旧 custom entry を含む場合も安全に official entry へ収束する。
- AC-005: 利用者向け docs / Settings help が key 入力と価格推定境界を説明する。
- AC-006: baseline suite がすべて成功する。

## Decision Review Scope

- official-cloud-providers DEC-001: official URL / key alias を一組の contract として固定する。
- official-cloud-providers DEC-002: protocol kind を増やさず既存 OpenAI-compatible adapter を再利用する。
- official-cloud-providers DEC-003: 両 provider を `pricing_profile=none` とし、他社の価格へ誤 fallback しない。
- official-cloud-providers DEC-004: official provider id を予約し、同名旧 custom entry を安全に正規化する。
- openai-compat-anthropic-providers DEC-001 / DEC-008 / DEC-010: adapter / secret / builtin registry の既存境界を維持する。

## Intent-derived Invariants

- INV-001 (from openai-compat-anthropic-providers DEC-007): 両 provider の価格不明 usage をゼロまたは OpenRouter catalog 価格として表示しない。
- INV-002 (from openai-compat-anthropic-providers DEC-008): run 結果 JSON、SSE イベント、catalog キャッシュに API key 文字列を書き出さない。

## Risk Assessment

- Risk level: High
- Risk rationale: 認証 secret と外部 API endpoint、release 配布に関わる。
- Regression risk: builtin ordering、既存 registry migration、model catalog の missing key 表示が変わる。
- Data safety risk: registry file 全体を再生成すると custom entry を失うため、既存 merge を維持する。
- Security / privacy risk: secret value の API response / log / cache 混入を禁止する。
- UX risk: generic provider と official provider が重複したり、誤 URL を修正できず接続不能になったりする。
- Agent misbehavior risk: 実 credential の探索や課金 completion を baseline verification に含めない。

## Test Strategy

- Unit: ProviderRegistry / SecretsStore / adapter request mock。
- Integration: ModelCatalog の OpenAI-compatible fetch と server provider serialization。
- E2E: frontend provider label/help の build と API contract tests。
- Manual QA: official docs、公開 `/models`、認証なし POST の error contract を確認する。
- Validator / static check: `./scripts/check-docs.sh` と全 baseline suite。
- Diff review: `.env` / secret 値が追加されず、URL と alias だけが変更されていることを確認する。

## Test Matrix

| ID | Source | Requirement / Optional Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | official builtin ids / URLs / order | unit | `tests/test_provider_registry.py` | seed と reseed が2 providerを公式値で返す | verified |
| AC-002 | TODO | official environment aliases | unit | `tests/test_secrets_store.py` | save/load/env lookup が公式 key 名へ写像される | verified |
| AC-003 | TODO | catalog prefix と upstream request | unit/integration | `tests/test_model_catalog.py`, `tests/test_model_parameter_support.py` | provider prefix と request URL/model が一致する | verified |
| AC-004 | TODO | existing registry convergence | unit | `tests/test_provider_registry.py` | custom entriesを保持し同名旧entryだけ正規化する | verified |
| AC-005 | TODO | setup guidance | static/manual | `README.md`, `.env.example`, `frontend/src/pages/SettingsPage.tsx` | key名・URL・価格境界を読める | verified |
| AC-006 | TODO | full regression | baseline | `uv run pytest`; frontend lint/test/build; docs check | 全 command exit 0 | verified |
| INV-001 | DEC-007 | unknown price is not zero / OR price | unit | `tests/test_cost_estimator.py` | `pricing_profile=none` は推定不可 | verified |
| INV-002 | DEC-008 | secret is not serialized | unit/diff | provider API / catalog tests + diff review | key value が応答・cache・diffにない | verified |

## Manual QA Checklist

- [x] Ollama 公式 docs の `https://ollama.com/v1` / `OLLAMA_API_KEY` と実装値が一致する。
- [x] OpenCode 公式 docs / models.dev の `https://opencode.ai/zen/go/v1` / `OPENCODE_API_KEY` と実装値が一致する。
- [x] 両 `/models` が HTTP 200 で OpenAI-compatible list を返す。
- [x] credential なし Chat Completions request が secret を要求する明示 error を返し、endpoint が存在する。

## Regression Checklist

- [x] 既存 builtin 4件の id / URL / pricing profile / order が変わらない。
- [x] custom provider の作成・削除・key 保存が変わらない。
- [x] OpenRouter / LM Studio の専用 adapter と catalog path が変わらない。

## High-risk Checklist

- [x] Rollback or recovery path is documented.
- [x] Data safety has been checked.
- [x] Security / privacy implications have been checked.
- [x] Failure mode is understood.

## Out of Scope

- 課金 credential を使う live completion。
- OpenCode Zen、Ollama local、provider 固有価格表。

## Open Questions

- None
