---
title: "Plan: User-registered OpenAI-compatible providers + Anthropic"
status: completed
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-24
references:
  - "_docs/archives/draft/Core/openai-compat-anthropic-providers/notes.md"
  - "_docs/archives/survey/Core/openai-compat-anthropic-providers/survey.md"
  - "_docs/intent/Core/openai-compat-anthropic-providers/decision.md"
  - "_docs/qa/Core/openai-compat-anthropic-providers/test-plan.md"
related_issues: []
related_prs: []
---

# Plan: User-registered OpenAI-compatible providers + Anthropic

## Overview

ユーザーが名前付きで OpenAI 互換プロバイダを複数登録でき、Anthropic もネイティブ adapter で
使えるようにする。OpenRouter は同 registry の組み込みプリセットにする。LM Studio は別枠のまま。
推定コストは `pricing_profile` 明示マップ（OpenAI / Anthropic / Google / OpenRouter）のみ。

## Scope

- Provider registry（CRUD、OpenRouter プリセット、secrets 写像）
- `openai_compatible` adapter（汎用）+ `profile=openrouter` フック
- `anthropic` adapter（subject / judge / tool-use / thinking）
- Model ID `{provider_id}/{upstream_model_id}`、既存 `openrouter/` / `or/` 互換
- Catalog を registry 動的列挙へ（lmstudio は固定枠継続）
- Settings UX（追加・編集・削除・key 更新、接続テスト任意）
- Cost: 静的価格表 + profile マップ。未知は N/A。公式 profile の OR フォールバック禁止
- Guide 文言: Google AI Studio を openai_compatible で登録する手順

## Non-Goals

- Google 公式 Gemini SDK 専用 adapter
- LM Studio の registry 吸収
- プロバイダ横断の自動最安ルーティング
- OpenRouter 管理キー UI の大規模刷新
- Anthropic prompt caching / Batches の完全パリティ
- 価格表の自動同期（初版は静的 + `as_of` 注記。更新は保守タスク）

## Requirements

1. 名前付き openai_compatible を追加し、そのモデルで subject/judge run できる。
2. OpenRouter プリセットで既存 `openrouter/...` run / preset が壊れない。
3. Anthropic 登録後、非 tool complete + tool-use + thinking が subject/judge で通る。
4. Google は openai_compatible 登録手順が Settings / guide で示せる。
5. プロバイダ削除・key 欠落時、preset / 過去 run 表示がクラッシュしない。
6. API key が結果 JSON / SSE / ログに出ない。
7. `pricing_profile` 未設定・未知モデルは推定コスト N/A（0 扱い禁止）。公式 profile で OR 価格を出さない。

## Tasks

1. **Registry store**: `id`（slug）、`display_name`、`kind`、`base_url?`、`profile?`、
   `pricing_profile`。ビルドイン seed（DEC-010）: `openrouter` / `openai` /
   `google-ai-studio` / `anthropic`。LM Studio は含めない。
2. **Secrets**: registry id 単位の key。起動時に既存 `OPENROUTER_API_KEY` / secrets
   `openrouter` をプリセットへ写像。動的 env `PROVIDER_<ID>_API_KEY`。
3. **Adapters**: `OpenAICompatibleAdapter`；OpenRouter を profile 化（または薄いラッパ）。
   `AnthropicAdapter`（Messages、tools、thinking → `api_reasoning`）。
4. **Routing**: `get_adapter_for_model` を registry 解決へ。`lmstudio/` と `openrouter/`/`or/`
   互換を維持。
5. **Catalog**: registry エントリごとに `/models` 取得（失敗時手動 ID）。Anthropic は一覧 API
   または手動 + 既知リスト。
6. **Cost**: `core/pricing_tables.py`（または同等）に openai/anthropic/google 静的表。
   `_lookup_pricing` を profile 分岐。既存 OR→他 provider フォールバックを公式 profile から除去。
7. **Server API**: registry CRUD、keys by registry id、任意 connection test、models 更新。
8. **Frontend**: Settings 追加フロー、一覧、ModelPicker を registry グルーピング、
   connectedCount = 有効 registry 数（lmstudio は別表示維持）。
9. **Tests / docs**: unit（routing、secrets migration、cost profile、Anthropic stub）、
   regression（openrouter 既存）、guide 追記。
10. **Verification**: Risk High のため完了前に verification.md。

## QA Plan

詳細は `_docs/qa/Core/openai-compat-anthropic-providers/test-plan.md`。

重点: secrets 非漏洩、`openrouter/` 互換、cost 誤表示防止、Anthropic tools/thinking、削除後 UI 耐性。

## Deployment / Rollout

- ローカルアプリ。初回起動で OpenRouter プリセット seed + key 写像。
- 既存 run JSON は読取専用互換。再実行は registry 解決に依存。
- 価格表は `as_of` 日付付き。ズレ検知は follow-up（自動同期は Non-Goal）。

## Acceptance Criteria（TODO と同一）

- AC-001 … AC-007（test-plan / TODO 参照）
