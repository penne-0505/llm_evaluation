---
title: "Guide: Provider registry (OpenAI-compatible + Anthropic)"
status: active
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/openai-compat-anthropic-providers/decision.md"
  - "_docs/plan/Core/openai-compat-anthropic-providers/plan.md"
  - "_docs/qa/Core/openai-compat-anthropic-providers/test-plan.md"
  - "_docs/intent/Core/model-parameter-support/decision.md"
related_issues: []
related_prs: []
---

# Guide: Provider registry (OpenAI-compatible + Anthropic)

## 概要

Settings のクラウドプロバイダは、名前付き **provider registry** です。組み込みプリセットに
API キーを設定するか、独自の OpenAI 互換 endpoint を追加して、subject / judge に使えます。
LM Studio は従来どおり別カードです。

## 組み込みプリセット

| 表示名 | モデル ID 例 | 備考 |
| --- | --- | --- |
| OpenRouter | `openrouter/openai/gpt-4o` | 既存 ID・`or/` エイリアス互換 |
| OpenAI | `openai/gpt-4o` | 公式 `api.openai.com/v1` |
| Google AI Studio | `google-ai-studio/gemini-2.5-flash` | OpenAI 互換 endpoint 固定。Gemini API キーを設定 |
| Anthropic | `anthropic/claude-sonnet-4-5` | Messages API（tool-use / thinking 対応） |

組み込みは削除できません。キーのクリアのみ可能です。

## Google AI Studio の設定手順

1. [Google AI Studio](https://aistudio.google.com/) で API キーを発行する。
2. Settings → **Google AI Studio** にキーを貼り付けて保存する（base URL は組み込み済み）。
3. モデル一覧を再取得する。失敗時は手動で `google-ai-studio/<model_id>` を入力できる。

専用 Gemini SDK は不要です（OpenAI 互換で足りる）。

## カスタム OpenAI 互換の追加

1. Settings で kind = OpenAI compatible、表示名、base URL、API キーを入力して追加する。
2. 推定コストは既定で `none`（N/A）。OpenAI / Google 公式 URL の場合は `pricing_profile` が自動推定されることがある。
3. モデル ID は `{provider_id}/{upstream_model_id}`。

## 推定コスト

- `pricing_profile=openrouter` → OpenRouter カタログ
- `openai` / `anthropic` / `google` → 静的表（鮮度は `core/pricing_tables.py` の `AS_OF`）
- 表に無いモデルや `none` → 推定不可（0 円表示にはしない）

## Temperature と非対応モデル

gpt-5 / o1 系など temperature を受け付けないモデルでは、UI の温度値を API に送らず
ベンダー既定に委ねます（`core/model_parameter_support`）。preset 上の `subject_temperature`
記録はそのまま残ります。

## トラブルシューティング

- **モデルが選べない**: キー未設定、または catalog 取得失敗。手動 ID 入力を試す。
- **過去の preset で欠損表示**: プロバイダ削除後も UI は落ちない。再実行には再登録が必要。
- **OpenRouter だけ使いたい**: 従来どおり OpenRouter にキーを設定すればよい。
- **temperature 400**: 対応表漏れの可能性。ログに送付 kwargs を確認し、静的表へ追記する。
