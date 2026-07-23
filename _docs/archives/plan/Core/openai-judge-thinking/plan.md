---
title: "Plan: OpenAI judge reasoning and thinking capture"
status: completed
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/survey/Core/openai-judge-thinking/survey.md"
  - "_docs/intent/Core/openai-judge-thinking/decision.md"
  - "_docs/qa/Core/openai-judge-thinking/test-plan.md"
related_issues: []
related_prs: []
---

# Plan: OpenAI judge reasoning and thinking capture

## Overview

OpenAI 系 judge（OpenRouter 経由の o-series / reasoning モデル）について、API が返す thinking /
reasoning トークンを抽出し、judge 採点 JSON の `reasoning`（採点根拠）とは別フィールドとして
永続化・結果画面に表示する。Survey で確認したとおり、現行は `reasoning.effort` の送信のみで
レスポンス thinking は破棄されている。

## Scope

- `CompletionResult` に optional な API thinking ペイロードを追加する（Core-Feat-38 と同型）。
- `OpenRouterAdapter.complete_with_model_result` で Chat Completions レスポンスから
  `message.reasoning` / `message.reasoning_details` を抽出する。
- content 内 `<thinking>...</thinking>`（および OpenRouter が返す類似パターン）の fallback 抽出と、
  judge JSON パース前の content 正規化。
- `BenchmarkEngine._run_judge_evaluation` が judge run dict に `api_reasoning`（名称は Intent 準拠）
  をマージする。
- frontend `client.ts` / `ResultDetail.tsx` で API thinking を採点根拠 `reasoningSamples` と
  ラベル分離して折りたたみ表示する。
- OpenAI / OpenRouter 向け stub テストと engine 回帰テストを追加する。

## Non-Goals

- Anthropic / Gemini judge の thinking 抽出（Core-Feat-38）。
- Responses API Beta への judge パイプライン全面移行（Intent DEC-002 で defer）。
- 被験 subject LLM の thinking 表示（judge 呼び出しにスコープ限定）。
- reasoning トークン課金の UI 内訳表示（usage 拡張は将来）。
- 保存済み run の backfill / migration。

## Requirements

- AC-001: OpenAI / OpenRouter reasoning 対応 judge で API thinking が adapter から返る。
- AC-002: thinking は run JSON に永続化され、judge JSON `reasoning` とキーが衝突しない。
- AC-003: frontend で API thinking 専用の折りたたみ UI があり、`reasoningSamples` と混同しない。
- AC-004: 非対応・欠落・抽出失敗時も judge スコア取得は従来どおり成功する。
- AC-005: Chat Completions vs Responses API vs タグ抽出の採否が Intent に記録されている。

## Tasks

1. Survey / Intent の DEC を確認し、フィールド名（`api_reasoning`）と UI ラベルを固定する。
2. `CompletionResult` と adapter 抽出ヘルパを実装する（OpenRouter Chat Completions 優先）。
3. engine が parsed run に thinking をマージする。パース入力は thinking strip 済み text を使う。
4. frontend 型・変換・`ResultDetail` UI を更新する。
5. stub テスト（reasoning あり/なし/タグのみ/o-series 空）と QA Test Matrix を実行する。

## QA Plan

- Risk: **High**（外部 API 契約・保存 JSON  additive 変更・採点パース境界）。
- High-risk Checklist（rollback、data safety、privacy、failure mode）を test-plan で確認する。
- 全 AC を Test Matrix に 1 行以上割り当てる。

## Deployment / Rollout

- 保存 JSON は additive フィールドのため旧 frontend は未知キーを無視できる。
- rollback は adapter 抽出と UI を戻すのみ。既存 `reasoning` / `reasoningSamples` は unchanged。
- Responses API 採用時は別タスクで Intent を更新してから実装する。
