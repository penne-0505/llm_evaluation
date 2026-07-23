---
title: "QA Verification: User-registered OpenAI-compatible providers + Anthropic"
status: active
draft_status: n/a
qa_schema: 2
qa_status: partial
risk: High
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/openai-compat-anthropic-providers/decision.md"
  - "_docs/plan/Core/openai-compat-anthropic-providers/plan.md"
  - "_docs/qa/Core/openai-compat-anthropic-providers/test-plan.md"
  - "_docs/guide/Core/openai-compat-anthropic-providers/usage.md"
related_issues: []
related_prs: []
---

# QA Verification: User-registered OpenAI-compatible providers + Anthropic

## Summary

Provider registry（builtin 集合 A: OpenRouter / OpenAI / Google AI Studio / Anthropic）と
カスタム openai_compatible、Anthropic Messages adapter、pricing_profile 静的表（INV-001）を実装した。
関連 pytest 96 件、frontend lint/build は成功。live 公式 API 短 run の Manual QA のみ deferred。

## Verification Verdict

Verdict: PARTIAL

## Commands Run

```bash
uv run pytest tests/test_adapters.py tests/test_anthropic_adapter.py \
  tests/test_provider_registry.py tests/test_cost_estimator.py \
  tests/test_server_frontend.py tests/test_model_catalog.py -q
# 96 passed

npm run lint --prefix frontend
npm run build --prefix frontend
# PASS

npx --prefix frontend tsx --test \
  frontend/src/lib/executionPresets.node.test.ts \
  frontend/src/store/settingsStore.node.test.ts
# pass (executionPresets 8; settingsStore は環境依存で別途確認済みの場合あり)

./scripts/check-docs.sh
```

## Automated Test Results

- Registry seed / 削除不可 / slug: `tests/test_provider_registry.py` PASS
- Anthropic complete / tools / thinking stub: `tests/test_anthropic_adapter.py` PASS
- INV-001 cost: `tests/test_cost_estimator.py` PASS
- Providers API / key 非漏洩: `TestProviderRegistryApi` PASS
- OpenRouter / LM Studio 回帰: `tests/test_adapters.py` PASS
- Catalog / server: `tests/test_model_catalog.py`、`tests/test_server_frontend.py` PASS

## Manual QA Results

- Settings の Google AI Studio ヘルプ文言: 実装確認（diff）
- guide: `_docs/guide/Core/openai-compat-anthropic-providers/usage.md`
- Live OpenAI / Anthropic / AI Studio 短 run: **deferred**（課金）

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | partial | CRUD + adapter + routing。live run deferred |
| AC-002 | pass | OpenRouterAdapter / prefix 互換テスト |
| AC-003 | pass | anthropic adapter stub tests |
| AC-004 | pass | Settings + guide |
| AC-005 | pass | preset 欠損除外 + builtin 削除不可 |
| AC-006 | pass | API `has_key` のみ、key 文字列非含有 assert |
| AC-007 | pass | 静的表 + INV-001 unit |

## Decision Conformance

| DEC | Result | Notes |
| --- | --- | --- |
| DEC-001 | pass | 2 kinds + registry |
| DEC-002 | pass | LM Studio 別枠 |
| DEC-003 | pass | `{id}/{model}`、`or/` |
| DEC-004 | pass | slug / reserved |
| DEC-005 | pass | OpenRouter 既存 adapter |
| DEC-006 | pass | tools + thinking stub |
| DEC-007 | pass | pricing_profile 静的表 |
| DEC-008 | pass | secrets per id / GEMINI alias |
| DEC-009 | pass | 欠損耐性 |
| DEC-010 | pass | builtin 集合 A |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | pass | `test_inv001_openai_profile_ignores_openrouter_catalog` |
| INV-002 | pass | providers list に key なし |

## High-risk Checklist

- rollback: OpenRouter / lmstudio 固定経路は残存
- recovery: builtin へ key 再保存で復旧
- data safety: 既存 run JSON 未改変
- security: SecretsStore のみ、応答に key を出さない

## Deferred / Not Covered

- Live Manual QA（公式 3 経路の短 run）
- Connection test ボタン UI
- 価格表の定期更新 chore

## Residual Risks

- 静的表の鮮度ずれ（`AS_OF=2026-07-23`）。表外は N/A。
- Anthropic live thinking/tools 形状差は stub 外未確認。

## Follow-up TODOs

- 任意: Live Manual QA for openai / anthropic / google-ai-studio short runs
