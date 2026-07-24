---
title: "Plan: Concurrent evaluation jobs with provider rate limits"
status: active
draft_status: n/a
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/Core/concurrent-evaluation-jobs/decision.md"
  - "_docs/qa/Core/concurrent-evaluation-jobs/test-plan.md"
  - "_docs/intent/UI/run-presence-observation/decision.md"
related_issues: []
related_prs: []
---

# Plan: Concurrent evaluation jobs with provider rate limits

## Overview

現状の評価 UI / store は「進行中の評価は 1 本」前提である。設定の異なる評価を
**同時に最大 3 本**まで走らせ、Run 画面では現行の進行ボード一式を **1 ジョブ** として
縦に積む。あわせて、同時実行時に同一プロバイダへリクエストが集中しないよう、
プロセス全体で共有する **プロバイダ別レート制限** を初版から入れる。制限値は
Settings で編集でき、プロバイダごとの推奨デフォルトを内蔵する。

## Scope

- サーバ側 active run 登録と同時実行上限（既定 3、サーバ強制）。
- プロセス全体共有のプロバイダ別レート制限（adapter 呼び出し直前で待機）。
- 制限設定の永続化 API と Settings UI（推奨デフォルト + 上書き）。
- フロントの multi-job store / Run 画面のジョブ縦積み（各ジョブが現行進行ボードを内包）。
- ジョブ単位のキャンセル・完了導線・上限到達時の開始拒否。
- 既存 1 本実行・SSE 契約・結果保存の後方互換（単一ジョブ時は現行体験を維持）。

## Non-Goals

- 永続ジョブキュー、プロセス再起動後の再開、優先度、失敗自動リトライ。
- モデル単位・エンドポイント単位の細粒度クォータ、従量課金プラン連動の自動調整。
- ブラウザ複数タブ間の分散ロック（同一プロセス内の同時実行が対象）。
- 逐次専用キュー UI（「終わったら次」専用モード）。必要なら後続。
- UI-Feat-61（presence observation）の演出仕様そのものの再設計。ただしジョブ縦積み後も
  カード局所 presence が載る前提で干渉を避ける。

## Requirements

- **Functional**
  - AC-001: 最大 3 本まで設定違いの評価を同時起動でき、4 本目はサーバが拒否する。
  - AC-002: Run 画面で各ジョブが進行ボード一式として縦積み表示され、個別キャンセルできる。
  - AC-003: 全ジョブの LLM 呼び出しがプロバイダ別レート制限を共有し、窓内上限を超えて
    発行しない。
  - AC-004: Settings でプロバイダごとに制限を編集・保存でき、未設定時は推奨デフォルト。
  - AC-005: ジョブ 1 本のみのとき、進行ボード体験は現行と同等（回帰なし）。
- **Non-Functional**
  - レート待ちはキャンセル可能である。
  - 制限設定はサーバ側に永続化し、実際の発行制御と一致する。
  - 推奨デフォルトは builtin / 既知プロバイダに対して明示し、未知プロバイダは保守的既定。

## Tasks

1. Intent / QA を確定する（本 Plan と同時）。
2. `ProviderRateLimiter`（仮）を実装し、adapter complete 経路で `acquire(provider_id)` する。
3. レート制限設定ストア + GET/PUT API + 推奨デフォルト表を追加する。
4. active run registry と同時上限 3 の強制を `/run` 開始時に入れる。
5. frontend multi-job store と Run 画面のジョブ縦積み UI を実装する。
6. Settings にプロバイダ別レート制限編集 UI を追加する。
7. unit / API / frontend テストと Manual QA を行い verification を残す。

## QA Plan

- Risk: High（同時実行・共有レート制限・コスト stampede・UI 構造変更）。
- High-risk Checklist と Test Matrix は
  `_docs/qa/Core/concurrent-evaluation-jobs/test-plan.md` に記載する。
- 1 ジョブ回帰、3 ジョブ同時、4 本目拒否、同一プロバイダ共有待ち、Settings 永続化を必須にする。

## Deployment / Rollout

- 既定は max concurrent 3、レート制限は推奨デフォルトで有効。
- 既存クライアントが単一 SSE のままなら、1 ジョブとして従来どおり動く。
- rollback は registry / limiter / multi-job UI を戻す。保存済み結果 JSON の破壊は不要。
