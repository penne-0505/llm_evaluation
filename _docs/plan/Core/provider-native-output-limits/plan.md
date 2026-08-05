---
title: "Plan: Provider-native output token limits"
status: active
draft_status: n/a
created_at: 2026-08-05
updated_at: 2026-08-05
references:
  - "_docs/intent/Core/provider-native-output-limits/decision.md"
  - "_docs/intent/Core/model-parameter-support/decision.md"
  - "_docs/intent/Core/holistic-context-overflow/decision.md"
  - "_docs/qa/Core/provider-native-output-limits/test-plan.md"
related_issues: []
related_prs: []
---

# Plan: Provider-native output token limits

## Overview

被験・judge の全評価 request に一律送信している `16,384` token cap を廃止する。optional な
OpenAI Chat Completions-compatible protocol では上限 field 自体を省略する。必須 field を持つ
Anthropic Messages API では、公式 Models API のモデル別 `max_tokens` を provider native limit として送る。

公式仕様の根拠:

- [Anthropic Messages API](https://platform.claude.com/docs/en/api/messages/create): `max_tokens` は
  生成前に指定する絶対上限。
- [Anthropic models overview](https://platform.claude.com/docs/en/about-claude/models/overview):
  Models API は `max_input_tokens` / `max_tokens` を返し、同期 Messages API のモデル別最大出力を示す。

## Scope

- `LLMAdapter` の `max_tokens` を `Optional[int]` にし、`None` を application cap なしと定義する。
- BenchmarkEngine の被験 text/native/final と judge standard/holistic が `None` を渡す。
- OpenRouter / OpenAI-compatible / LM Studio が `None` のとき max output field を省略する。
- Anthropic catalog metadata と Models API lookup で required `max_tokens` を解決・cacheする。
- holistic input budget の output reserve を request cap と別名・別責務にする。

## Non-Goals

- provider 自身の context window / maximum output token 制約を解除しない。
- UI に任意の max output token 設定を追加しない。
- connection probe など明示的な小さい `max_tokens` を持つ非評価 request を変更しない。
- Anthropic Message Batches の 300k beta header を導入しない。

## Requirements

- **Functional**: 評価 role と tool mode に関係なく、アプリ固定 cap が adapter request に残らない。
- **Functional**: Anthropic required limit は provider metadata から決まり、同じ adapter/model では再照会しない。
- **Non-Functional**: metadata 不明時に固定値へ戻らず、どのモデルの limit を解決できなかったかを示す。
- **Non-Functional**: explicit `max_tokens` caller の後方互換を維持する。

## Tasks

1. adapter interface と4 adapter の optional max token request shaping を更新する。
2. ModelCatalog が Anthropic の `max_tokens` / `max_input_tokens` を保持するようにする。
3. AnthropicAdapter に cache-first / Models API fallback resolver を追加する。
4. BenchmarkEngine の固定 cap constants / call sites を削除し、holistic reserve を分離する。
5. regression / error / cache tests と baseline verification を実施する。

## QA Plan

- QA document: `_docs/qa/Core/provider-native-output-limits/test-plan.md`
- Risk level: High
- Test strategy:
  - Unit: adapter kwargs、Anthropic metadata resolver、cache normalization。
  - Integration: subject/judge/tool engine call records。
  - E2E: backend/frontend/docs baseline。
  - Manual QA: SDK signature と公式 Models API schema の照合。
  - Validator / static check: `16,384` request cap / max field assignment scan。
- AC-001..006 と Intent INV-001..002 を test matrix へ対応付ける。
- DEC-001..004 と既存 model-parameter-support DEC-001/004、holistic-context-overflow DEC-001 の
  Why / Change freedom を review する。
- rollback は optional contract を旧 integer contract に戻す。結果 schema / user data migration はない。

## Deployment / Rollout

local baseline と independent review 後に implementation commit を `main` へ pushする。version tag は
remote CI と change scope を確認してから決め、provider release `v0.18.0` とは別 commit 境界を保つ。
