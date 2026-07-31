---
title: "Plan: Provider-aware reasoning effort ceiling"
status: active
draft_status: n/a
created_at: 2026-08-01
updated_at: 2026-08-01
references:
  - "_docs/intent/Core/reasoning-effort-ceiling/decision.md"
  - "_docs/qa/Core/reasoning-effort-ceiling/test-plan.md"
  - "_docs/intent/Core/model-parameter-support/decision.md"
related_issues: []
related_prs: []
---

# Plan: Provider-aware reasoning effort ceiling

## Overview

被験と judge の全呼び出しで同じ reasoning effort 方針を使い、provider / model が受理する
`xhigh` 以下の最上位値を実際の API フィールドへ変換する。engine の値直書きを廃止し、adapter が
provider 固有 payload を返す。

## Scope

- 被験の通常 completion、native tool loop、final completion。
- judge の retry / preferred-host 経路。
- built-in OpenRouter、OpenAI、Google AI Studio、Anthropic と LM Studio。
- OpenRouter `reasoning.effort`、OpenAI-compatible `reasoning_effort`、Anthropic
  `output_config.effort` の形状差。
- model / capability による `xhigh`、`high`、omit の解決。
- unit / engine regression、baseline、docs gate、`v0.17.0` release verification。

## Non-Goals

- `max` effort の送信。
- Responses API / Gemini native API / LM Studio native `/api/v1/chat` への移行。
- 能力 metadata を持たない任意 OpenAI-compatible endpoint への推測送信。
- effort 非対応モデルで reasoning を強制的に有効化すること。
- paid live API を自動テストに組み込むこと。

## Requirements

- **Functional**: provider / model ごとに有効な effort と payload shape を一箇所で解決する。
- **Functional**: 被験と judge は adapter が返した同一 payload を変更せず送る。
- **Functional**: `max` 対応系でも `xhigh` が利用可能なら `xhigh`、利用不可なら `high` を使う。
- **Functional**: Google AI Studio と graded reasoning 対応 LM Studio は `high` を使う。
- **Non-Functional**: capability 不明時は omit し、未知 provider の既存成功経路を壊さない。
- **Non-Functional**: reasoning 以外の extra params と preferred-host merge を維持する。

## Tasks

1. `LLMAdapter` に provider-aware effort payload の契約を追加する。
2. OpenRouter / OpenAI-compatible / Anthropic / LM Studio で契約を実装する。
3. engine 3 箇所の hard-coded `high` を契約呼び出しに置き換える。
4. model support table と payload forwarding の regression test を追加・更新する。
5. QA verification を作成し、baseline と release workflow を確認する。

## QA Plan

- QA document: `_docs/qa/Core/reasoning-effort-ceiling/test-plan.md`
- Risk level: High
- Test strategy:
  - Unit: provider / model effort 解決、SDK kwargs / extra body の形状。
  - Integration: engine の被験通常・native tool・judge が同じ adapter payload を使う。
  - E2E: baseline backend / frontend / docs gate。
  - Manual QA: diff 上で `max` と hard-coded legacy `high` が残らないことを確認する。
  - Validator / static check: docs validators、Markdown lint、`rg` による送信箇所監査。
- AC-001..004 と INV-001..002 を test matrix へ対応付ける。
- DEC-001..005 の ceiling、protocol shape、safe omission、single ownership、release 境界を review する。
- rollback は adapter 契約と engine 呼び出しを旧 opt-in nested payload に戻す。結果データ schema の
  migration はない。

## Deployment / Rollout

1. local baseline を通し、implementation / verification 前半を main へ push する。
2. implementation commit に annotated `v0.17.0` tag を作成して push する。
3. Linux AppImage / Windows ZIP workflow と release assets / checksum を確認する。
4. remote evidence を verification に追記し、TODO を完了処理して main へ push する。
