---
title: "Intent: Provider-aware reasoning effort ceiling"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-08-01
updated_at: 2026-08-01
references:
  - "_docs/plan/Core/reasoning-effort-ceiling/plan.md"
  - "_docs/qa/Core/reasoning-effort-ceiling/test-plan.md"
  - "_docs/intent/Core/model-parameter-support/decision.md"
  - "https://developers.openai.com/api/docs/guides/latest-model"
  - "https://platform.claude.com/docs/en/build-with-claude/effort"
  - "https://ai.google.dev/gemini-api/docs/openai"
  - "https://lmstudio.ai/changelog/lmstudio-v0.4.8"
  - "https://lmstudio.ai/docs/developer/rest/list"
related_issues: []
related_prs: []
---

# Intent: Provider-aware reasoning effort ceiling

## Context

2026-08-01 時点で、engine は reasoning opt-in の被験 / judge に OpenRouter 形式の
`reasoning.effort: high` を直書きする。OpenAI / Google AI Studio は Chat Completions の
`reasoning_effort`、Anthropic は Messages の `output_config.effort`、LM Studio 0.4.8 は
OpenAI-compatible Chat Completions の `reasoning_effort` を使うため、単一 shape は成立しない。

上限値も異なる。OpenAI と Anthropic の新しいモデルには `max` / `xhigh` がある一方、Gemini と
LM Studio の graded effort は `high` が上限である。product 方針は「利用可能な最上位を基本とするが、
`max` 系では `xhigh` を ceiling とする」である。

## Decisions

### DEC-001: effort ceiling は `xhigh` とし `max` を送らない

- **What**: effort の意味順を `high < xhigh < max` とみなし、送信上限を `xhigh` に固定する。
  model が `xhigh` を受理すれば `xhigh`、受理せず `high` を受理すれば `high`、effort 自体が
  非対応なら omit する。
- **Why**: 品質優先の上位設定を使いつつ、`max` 系だけはコスト・遅延がさらに増える最上段を避けるという
  product 方針を、無効値送信なしで表現できる。
- **Change freedom**: provider が新しい列挙値を追加した場合、意味順と ceiling を保つ範囲で静的表や
  capability 解析を更新できる。
- **Why not**: 全 provider へ文字列 `xhigh` を送ると、Google / LM Studio と high-only model が
  400 error になりうる。`max` への自動昇格は明示された ceiling を越える。

### DEC-002: API shape は adapter が所有する

- **What**: OpenRouter は `{"reasoning":{"effort":"xhigh"}}` を `extra_body` へ、OpenAI / Google /
  LM Studio は top-level `reasoning_effort`、Anthropic は top-level `output_config.effort` を使う。
- **Why**: engine が protocol shape を知ると被験 / judge の分岐が再び重複し、新 provider 追加時に
  片側だけ更新される。
- **Change freedom**: adapter 内の merge helper や返却 dict の生成方法は変更できる。

### DEC-003: capability は公式 static table と provider catalog から保守的に解決する

- **What**: OpenAI / Anthropic / Google は 2026-08-01 時点の公式 model family tableを使う。
  OpenRouter は既存 catalog opt-in gate、LM Studio は `/api/v1/models` の
  `capabilities.reasoning.allowed_options` を使う。能力不明時は omit する。
- **Why**: unsupported effort は request 全体を失敗させる。推測による常時送信より、既知モデルを
  明示し capability metadata を優先する方が既存評価を保全できる。
- **Change freedom**: vendor が機械可読 capability を提供した時は static table を置換できる。
- **Revisit when**: OpenAI / Anthropic の model list API が effort enum を返すようになった時。

### DEC-004: engine は被験 / judge とも adapter の単一契約だけを呼ぶ

- **What**: `LLMAdapter.reasoning_effort_params(model)` を被験通常、被験 native tools、judge で使う。
  engine 内で provider 名や effort 値を分岐しない。
- **Why**: 同じ model を被験と judge に選んだ時、役割によって effort が変わる回帰を防ぐ。
- **Change freedom**: method 名や返却型は、全呼び出し経路が同じ正典を使う限り変更できる。

### DEC-005: custom provider は明示 profile がない限り effort を推測しない

- **What**: built-in id 以外の任意 OpenAI-compatible provider と、公式対応 family に一致しない model
  では effort を omit する。
- **Why**: 同じ OpenAI-compatible protocol でも受理 enum と実装 field は一致しない。未知 endpoint
  への `reasoning_effort` 強制は既存の成功 run を失敗へ変える。
- **Change freedom**: registry に reasoning capability/profile を追加した場合は opt-in で対象化できる。

## Consequences / Impact

- OpenRouter の既存 opt-in call は `high` から `xhigh` へ上がる。
- 公式 OpenAI / Google / Anthropic は対応 model で初めて明示 effort を受け取る。
- LM Studio は graded `high` capability が公開される model だけ top-level effort を受け取る。
- 保存 JSON schema、API key、課金情報の扱いは変わらない。reasoning token 増加により実行時間と
  provider 課金は増えうる。

## Quality Implications

- provider ごとの field nesting と enum を unit test で固定する。
- subject / judge / native tool の parity を engine test で固定する。
- `max` 送信と unknown provider への推測送信を禁止する。
- static model table の `AS_OF` を vendor 更新時に見直す。

## Intent-derived Invariants

- INV-001 (from DEC-004): effort を送る全ての被験 / judge call は、役割別の値直書きではなく adapter の
  単一 effort 契約から payload を得る。
- INV-002 (from DEC-001): 送信 payload に effort 値 `max` は含まれず、DEC-002 の field shape と値は対象
  provider / model が受理する組み合わせである。

## Enforced in (optional)

- DEC-001 / DEC-003: `core/model_parameter_support.py`
- DEC-002: `adapters/openrouter_adapter.py`, `adapters/openai_compatible_adapter.py`,
  `adapters/anthropic_adapter.py`, `adapters/lmstudio_adapter.py`
- DEC-004 / INV-001: `adapters/base.py`, `core/benchmark_engine.py`

## Rollback / Follow-ups

- rollback: engine を既存 `is_reasoning_opt_in` + nested `high` に戻し、adapter の effort override を外す。
- follow-up: Core-Bug-48 で LM Studio 0.4.8+ 実サーバの `reasoning_effort: high` を live 確認する。
- follow-up: custom provider capability/profile は利用要望が出た時に registry schema として設計する。
