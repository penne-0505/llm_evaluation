---
title: "Plan: Cross-provider model parameter support"
status: completed
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/model-parameter-support/decision.md"
  - "_docs/qa/Core/model-parameter-support/test-plan.md"
  - "_docs/qa/Core/model-parameter-support/verification.md"
related_issues: []
related_prs: []
---

# Plan: Cross-provider model parameter support

## Overview

`openai/gpt-5.6-luna` の temperature 400 を契機に、プロバイダ横断の
「モデル×パラメータ対応」解決層を導入する。OpenRouter catalog・静的表・engine 特例を一本化する。

## Scope

- `core/model_parameter_support.py` 単一入口
- OpenAICompatible / OpenRouter / Anthropic 配線
- Gemini 3 judge omit の吸収
- temperature（必須）と max_completion_tokens 判定の共有化（可能な範囲）

## Non-Goals

- 全ベンダー網羅、live 公式 models API 自動同期、400 自動リトライ主経路、LM Studio reasoning 吸収

## Requirements

Plan 添付の AC-001..004 に従う。

## Tasks

1. Intent / QA
2. support layer + static tables
3. adapter / engine wire
4. tests + verification

## QA Plan

`_docs/qa/Core/model-parameter-support/test-plan.md`
