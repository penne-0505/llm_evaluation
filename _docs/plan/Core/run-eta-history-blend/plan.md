---
title: "Plan: Progress ETA wall-clock with history prior"
status: active
draft_status: n/a
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/Core/task-duration-eta/decision.md"
  - "_docs/reference/UI/pre-run-estimate/reference.md"
related_issues: []
related_prs: []
---

# Plan: Progress ETA wall-clock with history prior

## Overview

実行中の推定残り時間を、処理時間合算ベースから **残り待ち時間（wall-clock）** へ切り替え、
pre-run と同系の履歴類似度プールを弱い事前として backend SSE の `eta_ms` に載せる。
同一 run の実測ペースは完了が増えるほど強く支配する。

TODO: `Core-Enhance-66`

## Scope

- `server.py`（または `core/` の ETA helper）の `_compute_progress_eta` を置き換える。
- 実行開始時に `ResultStorage.list_summaries()` から履歴を読み、run 中はキャッシュして使う。
- 履歴 wall 事前は `_docs/reference/UI/pre-run-estimate/reference.md` と同系の距離・減衰・被験ゲート
  （所要チャネルは薄い横断可）を Python 側に持つ。
- SSE `eta_status` を拡張し、frontend のラベルを追従させる。
- Intent（`Core/task-duration-eta` の DEC-002 改訂）と QA は **実装と並行** で書く。
- 単体テスト（backend）と必要なら frontend の status ラベル test。

## Non-Goals

- pre-run UI の再設計。
- フロントだけで履歴と ETA を合成する経路（backend 正典）。
- `task_timing` 永続化や ROI 定義の変更。
- 履歴定数のオンライン学習。
- 包括フェーズ専用の精密 wall モデル（既存どおり remaining に holistic 残を足す範囲は維持）。

## Requirements

- 正典は残り wall-clock。主値に `task_timing` 平均×残タスクを使わない。
- 実測: `経過 / 完了負荷 × 残負荷`（完了 0 では使わない）。
- 履歴事前: 類似度重み付き wall 単位レート × 残負荷（または総見積 − 経過の同等物）。
- 合成: `α(完了数)` で実測をかなり重く。仮置きは Plan 実装時に reference へ定数として固定。
- 完了 0: 履歴事前があればそれ、無ければ現行の step 比率、どちらも無ければ unavailable。
- ラベルで measured 寄り / history blend / step_fallback / unavailable を区別する。
- 不明・不能時に確定値風の 0 残りを出さない（残タスクがあるのに 0 にしない既存制約は維持）。

## Tasks

1. Plan を固定し TODO を切る（本ドキュメント）。
2. Intent DEC-002 を「wall 残り＋実測優先＋履歴弱い事前」へ改訂（実装と並行）。
3. QA test-plan を書く（実装と並行）。
4. Python に履歴 wall 事前＋合成 ETA helper を実装し、SSE 接続する。
5. frontend `EtaStatus` / ラベルを拡張する。
6. テストと verification を残す。

## QA Plan

実装と並行で `_docs/qa/Core/task-duration-eta/test-plan.md` を更新する
（または本施策用に追記）。verification は完了前に必須。

## Deployment / Rollout

backend + frontend。既存 result スキーマ変更なし。SSE に未知 `eta_status` が来ても
frontend はフォールバック表示できなければならない。

## Open Design Notes (locked in implementation)

- 完了負荷: **タスク件数**（`completed_task_count` / `remaining_task_count`）。履歴側は pre-run と同じ L ユニットで単位化し、残タスク×(L_plan/taskCount) へ掛ける。
- `α(n) = n / (n + 0.1)`。合成時は履歴事前を実測の 1/4〜4 倍にクランプ。
- `eta_status`: `measured` / `history_blend` / `history` / `step_fallback` / `unavailable`。
