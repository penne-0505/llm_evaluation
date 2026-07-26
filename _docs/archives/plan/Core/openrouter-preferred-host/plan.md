---
title: "Plan: OpenRouter preferred host selection"
status: archived
draft_status: n/a
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/Core/openrouter-preferred-host/decision.md"
  - "_docs/qa/Core/openrouter-preferred-host/test-plan.md"
related_issues: []
related_prs: []
---

# Plan: OpenRouter preferred host selection

## Overview

OpenRouter 経由モデルで upstream ホストが複数あるとき、ホストを優先指定できるようにする。
優先ホストへアプリ側で最大 3 回試し、失敗後はホスト指定なしでフォールバックする。
設定はモデル単位で永続し、実行プリセットにも含める。UI はモデルピッカーとは別のホストピッカー
（常時表示、ホスト数 2 以上で enabled）とし、judge は共有ピッカー＋チップで編集対象を切り替える。

## Scope

- OpenRouter endpoints 一覧 API（backend proxy）
- Run 時の preferred host → `provider.only` + `allow_fallbacks: false`、3 回後に unrestricted
- Settings / execution preset の `preferredHosts` マップ
- Subject / judge / holistic のホストピッカー UI（指標: tps p50, input/M, output/M, cache read/M）

## Non-Goals

- ハードピン（フォールバック禁止）の恒久固定
- OpenRouter 以外のプロバイダのホスト選択
- ホスト別コスト集計の結果画面改修
- endpoints のオフライン完全キャッシュ（セッション内取得で足りる）

## Requirements

1. OpenRouter モデルかつ endpoints ≥ 2 のときホストピッカーが enabled。1 以下は disabled（非表示にしない）。
2. 選択はモデル ID → host slug のマップとして Settings とプリセットに保存される。
3. Run リクエストに `preferred_hosts` を渡し、被験・judge・holistic 呼び出しに適用する。
4. 優先ホスト失敗を最大 3 回リトライし、その後ホスト指定なしで再試行する。
5. ホストリスト要素に tps(p50)、input/M、output/M、cache read/M を表示する（欠落は —）。

## Tasks

1. Intent / QA を確定する
2. endpoints proxy と preferred-host 呼び出しヘルパを実装する
3. BenchmarkEngine / RunRequest に preferred_hosts を接続する
4. Settings・プリセット・HostPicker UI を実装する
5. テストと verification を残す

## QA Plan

`_docs/qa/Core/openrouter-preferred-host/test-plan.md`

## Deployment / Rollout

ローカル設定のみ。既存プリセットは `preferredHosts` 欠落を空マップとして扱う後方互換。
