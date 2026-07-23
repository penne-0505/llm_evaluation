---
title: "Plan: Claude and Gemini judge reasoning capture"
status: completed
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/survey/Core/claude-gemini-judge-thinking/survey.md"
  - "_docs/intent/Core/claude-gemini-judge-thinking/decision.md"
  - "_docs/qa/Core/claude-gemini-judge-thinking/test-plan.md"
  - "_docs/qa/Core/claude-gemini-judge-thinking/verification.md"
  - "_docs/archives/survey/Core/openai-judge-thinking/survey.md"
related_issues: []
related_prs: []
---

# Plan: Claude and Gemini judge reasoning capture

## Overview

Anthropic Claude および Google Gemini を judge に使った run について、OpenRouter 経由で返る
API thinking / reasoning を抽出し、judge 採点 JSON の `reasoning` とは別に永続化・表示する。
OpenAI 系（Core-Feat-37）と `CompletionResult.api_reasoning` および `ResultDetail` の API thinking
UI 契約を共有するが、本 Plan は provider 別抽出とテストにスコープを限定する。

## Scope

- `OpenRouterAdapter` に Anthropic / Gemini 向け reasoning 正規化（`message.reasoning`、
  `reasoning_details` → string）を実装する。37 実装済みなら同ヘルパを共有。
- `:thinking` suffix（effort 未送信）と opt-in（effort high 送信）の両方でレスポンス thinking を
  抽出する。
- Gemini thinking モデルで取得、非 thinking モデルで no-support（空）を Intent に記録。
- engine run dict への `api_reasoning` マージ（37 と同一契約）。
- frontend は 37 で導入した API thinking 表示をそのまま利用（38 単独では UI 差分最小）。
- provider 別 stub テスト（Claude thinking ブロック相当、Gemini あり/なし）。

## Non-Goals

- OpenAI o-series 固有の Responses API / タグ fallback（Core-Feat-37）。
- Anthropic / Google ネイティブ SDK 直叩き（OpenRouter 経由に限定）。
- 被験 subject の thinking 表示。
- LM Studio ローカル judge（別 provider）。

## Requirements

- AC-001: Anthropic Messages API 相当の thinking が OpenRouter レスポンスから adapter で抽出される。
- AC-002: Gemini thinking 取得可否が調査され、可能なら実装、不可なら Intent に no-support rationale。
- AC-003: 抽出結果は judge JSON `reasoning` と区別して run JSON に保存される。
- AC-004: `:thinking` と opt-in の両方で thinking 取得または graceful skip がテストされる。
- AC-005: thinking 取得失敗時も judge スコア集計は従来どおり完了する。

## Tasks

1. Survey / Intent を読み、Gemini no-support 境界を確定する。
2. adapter 抽出（Claude / Gemini stub）を追加する。
3. engine マージが provider 非依存で動くことを確認する。
4. 37 UI 契約で frontend 表示を確認（未マージなら 38 QA で backend のみ PARTIAL 明示）。
5. provider 別 Test Matrix を実行する。

## QA Plan

- Risk: **Medium**（外部 API・保存 JSON additive。37 と比べ Responses API 移行は対象外）。
- 全 AC を Test Matrix に割り当てる。
- High-risk Checklist は Risk Medium のため N/A（template 準拠）。

## Deployment / Rollout

- 37 と同一 additive JSON。rollback は adapter provider 分岐の削除。
- 37 UI 未完了時は 38 backend 先行可。verification で UI AC の依存を明記する。
