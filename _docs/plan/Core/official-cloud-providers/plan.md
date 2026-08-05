---
title: "Plan: Ollama Cloud and OpenCode Go official providers"
status: active
draft_status: n/a
created_at: 2026-08-05
updated_at: 2026-08-05
references:
  - "_docs/intent/Core/official-cloud-providers/decision.md"
  - "_docs/intent/Core/openai-compat-anthropic-providers/decision.md"
  - "_docs/qa/Core/official-cloud-providers/test-plan.md"
related_issues: []
related_prs: []
---

# Plan: Ollama Cloud and OpenCode Go official providers

## Overview

Ollama Cloud と OpenCode Go を provider registry の組み込み entry に追加し、公式 base URL と
API key 環境変数名をアプリの設定契約へ固定する。両者は OpenAI Chat Completions-compatible endpoint
を提供するため、既存 `OpenAICompatibleAdapter` と model catalog fetch を再利用する。

公式仕様の根拠:

- [Ollama Cloud](https://docs.ollama.com/cloud): `OLLAMA_API_KEY` と direct cloud API。
- [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility): `/v1/models` と
  `/v1/chat/completions`。
- [OpenCode Go](https://opencode.ai/docs/go/): `https://opencode.ai/zen/go/v1`、`/models`、
  Chat Completions endpoint、`opencode-go/<model-id>`。
- [OpenCode providers](https://opencode.ai/docs/providers/): OpenCode Go API key の発行・入力手順。

## Scope

- `ollama-cloud` / `opencode-go` を builtin / reserved provider id として追加する。
- 公式 base URL と `pricing_profile=none` を seed / migration で保つ。
- `OLLAMA_API_KEY` / `OPENCODE_API_KEY` を UI 保存と環境変数読込の正典にする。
- Settings、README、`.env.example` に key の発行元と入力方法を記載する。
- registry、secret mapping、catalog prefix、adapter request shape を自動テストする。

## Non-Goals

- Ollama local endpoint を registry へ統合しない。local runtime は LM Studio と同様に別の接続課題とする。
- OpenCode Zen を追加しない。今回の対象は subscription provider の OpenCode Go に限定する。
- Ollama Cloud / OpenCode Go の変動価格を静的表へ複製しない。価格不明は推定不可として扱う。
- ユーザーの実 API key を読み取ったり、課金を伴う completion を自動実行したりしない。

## Requirements

- **Functional**: 初回起動と既存 registry の双方で2 provider が現れ、key 保存後に model catalog と評価 routing が使える。
- **Non-Functional**: secret は既存 `SecretsStore` 境界を越えず、公式 URL は mock / public endpoint で回帰検出できる。

## Tasks

1. Provider constants、reserved IDs、builtin seed、existing entry normalization を実装する。
2. SecretsStore の公式 environment alias と `.env.example` を更新する。
3. Settings の provider-specific help と frontend label を更新する。
4. README の公式 provider setup を更新する。
5. unit / integration / docs baseline suite を実行し QA verification を残す。

## QA Plan

- QA document: `_docs/qa/Core/official-cloud-providers/test-plan.md`
- Risk level: High
- Test strategy:
  - Unit: builtin / reseed / alias / request normalization。
  - Integration: model catalog の prefix と provider API serialization。
  - E2E: Settings/API の既存 provider 一覧 contract。
  - Manual QA: 公式 docs、公開 `/models`、無認証 error contract の照合。
  - Validator / static check: baseline suite と secret-bearing diff の確認。
- AC-001..005 を個別テストまたは manual contract check に割り当て、INV-002 の secret 非露出を既存と追加テストで確認する。
- official-cloud-providers DEC-001..004 と、既存 provider intent の DEC-001 / DEC-008 / DEC-010 の
  Why / Change freedom に沿い、adapter kind を増やさず official alias と seed を追加できているか review する。
- Rollback は2 provider の seed / alias / UI help を戻す。既存 user registry ファイルには他 provider を含むため、ファイル削除や全体再生成を行わない。

## Deployment / Rollout

baseline suite がすべて緑になった commit を `main` へ push し、provider 機能追加として次の minor tag を付ける。
tag-triggered Docs CI / Code CI / Linux AppImage / Windows ZIP と release asset を確認する。
