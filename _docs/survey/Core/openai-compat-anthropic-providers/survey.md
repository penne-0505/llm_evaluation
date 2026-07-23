---
title: "Survey: User-registered OpenAI-compatible providers + Anthropic"
status: active
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/draft/Core/openai-compat-anthropic-providers/notes.md"
  - "_docs/plan/Core/openai-compat-anthropic-providers/plan.md"
  - "_docs/intent/Core/openai-compat-anthropic-providers/decision.md"
  - "_docs/qa/Core/openai-compat-anthropic-providers/test-plan.md"
related_issues: []
related_prs: []
---

# Survey: User-registered OpenAI-compatible providers + Anthropic

## 1. Purpose

OpenRouter 経由の strict 評価コストを避け、公式 credit / 無料枠（OpenAI / Anthropic / Google AI Studio）を
subject / judge に直結させるための現状調査。draft Open Questions は会話で閉じ済み（§7）。

## 2. Current architecture

```text
Settings / Run
  → SecretsStore (固定 KEYS) + ProviderConfigStore (lmstudio base_url)
  → get_adapter_for_model(model_id)
       openrouter/* | or/*  → OpenRouterAdapter
       lmstudio/*           → LMStudioAdapter
  → UsageMetrics.provider = "openrouter" | "lmstudio"
  → cost_estimator ← OpenRouter catalog（他 provider は OR フォールバック）
```

| 領域 | 事実 |
| --- | --- |
| Routing | prefix 固定。それ以外は `None` |
| Secrets | `openai` / `anthropic` / `gemini` は KEYS にあるが UI・adapter 未配線 |
| Catalog | `PROVIDERS = ("openrouter", "lmstudio")`。`_fetch_openai/anthropic/gemini_models` は死蔵 |
| Frontend | `Provider = 'openrouter' \| 'lmstudio'`。cloud は openrouter 固定 |
| Connection test | API なし（保存成功＝接続済み） |
| SDK | `openai` 使用中、`anthropic` は依存のみ・実行未 import |

## 3. Adapter overlap

OpenRouter / LM Studio はともに OpenAI Chat Completions。共通化候補:

- `complete_with_model_result` / native tools / usage 抽出 / reasoning フィールド読取

OpenRouter 固有（分離必須）:

- 固定 `BASE_URL`、公開 `/models`、`:thinking` / catalog reasoning gate、Gemini no-support gate
- Management key / credits（`core/openrouter_admin.py`）

LM Studio 固有（v1 で別枠維持）:

- key 不要の `is_available`、`/v1` 強制、`/api/v1/models` reasoning capability

## 4. Cost estimator risk（課金感度）

`core/cost_estimator._lookup_pricing` は `provider != openrouter` でも OpenRouter カタログへ
フォールバックする。公式 API 経路で OR 価格を出すと、credit 消化の判断を誤らせる。

方針合意:

- registry エントリに明示 `pricing_profile`（`openrouter` / `openai` / `anthropic` / `google` / `none`）
- 公式 3 社は静的価格表。未知・未マップは N/A（0 にしない）
- 公式 profile では OR フォールバック禁止

一次情報源（実装時に再確認）:

- OpenAI: <https://developers.openai.com/api/docs/pricing>
- Anthropic: <https://platform.claude.com/docs/en/about-claude/pricing>
- Google Gemini OpenAI 互換: `https://generativelanguage.googleapis.com/v1beta/openai/`
  （<https://ai.google.dev/gemini-api/docs/openai>）
- Google 価格: AI Studio / Gemini pricing ページ（実装時に表へ転記）

## 5. Google path

専用 Gemini SDK は不要。openai_compatible + 上記 base_url + Gemini API key で足りる。
Preset 文言 / guide で手順を示す。

## 6. Anthropic SDK

`anthropic>=0.42.0` 既存。Messages API で complete / tool_use / thinking を実装する。
OpenRouter 経由 Claude の thinking 抽出（Core-Feat-38）とは別経路（ネイティブ Messages）。

## 7. Closed Open Questions（2026-07-23）

| Q | 決定 |
| --- | --- |
| Q1 LM Studio | 初版は別枠維持 |
| Q2 provider id | slug 自動生成 + display_name 分離（Intent DEC） |
| Q3 Anthropic 範囲 | subject + judge + tool-use + thinking |
| Q4 OpenRouter 固有 | `kind=openai_compatible` + `profile=openrouter` |
| Q5 cost | 明示 `pricing_profile` 紐付け。OpenAI/Anthropic/Google 最低限 |
| Q6 secrets env | 動的 id + 既存 `OPENROUTER_API_KEY` 写像（Intent DEC） |

## 8. Friction / touch list

高摩擦: 固定 enum（TS `Provider`、API keys、KEYS、catalog PROVIDERS、adapter prefix）、
モデル ID がルーティングキー、secrets 動的化、cost フォールバック撤去。

主タッチ: `adapters/*`、`core/secrets_store.py`、registry store、`model_catalog.py`、
`cost_estimator.py`、`server.py`、Settings / types / client、関連 tests。
