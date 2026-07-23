---
title: "Intent: Cross-provider model parameter support"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/plan/Core/model-parameter-support/plan.md"
  - "_docs/qa/Core/model-parameter-support/test-plan.md"
related_issues: []
related_prs: []
---

# Intent: Cross-provider model parameter support

## Context

公式 OpenAI 経路の `gpt-5.6-luna` に UI の subject temperature を送ると 400
（default 1 以外非対応）になる。OpenRouter は catalog `supported_parameters` で省略できるが、
`OpenAICompatibleAdapter` は常送し、engine は Gemini 3 judge だけ別特例で omit していた。
短期ヒューリスティックや 400 リトライより、長期で保守できる単一契約を優先する。

## Decisions

### DEC-001: パラメータ可否は単一入口 `model_parameter_support.allows`

- **What**: `core/model_parameter_support.allows(provider, model, parameter) -> bool` を正典とし、
  adapters / engine はここに問い合わせてから kwargs を組み立てる。
- **Why**: 散在 if / モデル名決め打ちが増えると、次の非対応パラメータで同じ事故が起きる。
- **Change freedom**: 内部の情報源実装（cache・表の分割）は変更可。公開シグネチャの意味は維持。

### DEC-002: 情報源は OpenRouter catalog → 公式静的表 → 安全側 default

- **What**: (1) openrouter は catalog / OR models cache の `supported_parameters`。
  (2) openai / anthropic / google / google-ai-studio は `as_of` 付き静的表（族マッチ可）。
  (3) 不明モデルの `temperature` は **omit（送らない）**。
- **Why**: 誤送信の 400 で評価が死ぬより、UI 温度が効かない側に倒す方が長期安定。
- **Change freedom**: 表への行追加、族マッチ規則。自動同期は別タスク。
- **Why not**: adapter 内 `gpt-5*` 決め打ちだけ — catalog と二重化し、Gemini 特例も残る。

### DEC-003: engine の Gemini 3 temperature 特例を共有層へ吸収

- **What**: `gemini-3` 文字列ハードコード omit をやめ、`allows(...)`（または同等の共有判定）に寄せる。
- **Why**: 同一契約の二重実装を避ける。
- **Change freedom**: engine が `allows` を呼ぶか、adapter に None を渡して adapter 側で落とすかは可。

### DEC-004: 初版必須は temperature。max_completion_tokens は同層へ寄せられる範囲で

- **What**: temperature を必須。OpenAI 系の max_completion_tokens 選択も同モジュールのヘルパに寄せる。
- **Why**: リクエスト整形ポリシーを一箇所に集める。
- **Change freedom**: 他パラメータ（tools 等）の追加時期。

## Consequences / Impact

- Strict の `subject_temperature` 記録値と、非対応モデルへの実送信が一致しない場合がある（意図的）。
- 表漏れの旧モデルでは温度が効かない側に倒れる。

## Quality Implications

- gpt-5.6-luna omit の unit、OpenRouter / Gemini 3 回帰必須。

## Intent-derived Invariants

- INV-001 (from DEC-001): `allows(provider, model, "temperature")` が False のとき、当該 complete
  リクエストの kwargs に `temperature` キーを含めない。

## Rollback / Follow-ups

- rollback: adapters を常送 temperature に戻し、engine の gemini-3 特例を復活させる。
- follow-up: 静的表の拡充、live models API 同期、LM Studio capability 吸収。
