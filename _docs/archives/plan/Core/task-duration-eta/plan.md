---
title: "Plan: Task duration estimates and ETA on results"
status: completed
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/task-duration-eta/decision.md"
  - "_docs/qa/Core/task-duration-eta/test-plan.md"
  - "_docs/archives/survey/Core/task-duration-eta/survey.md"
  - "_docs/qa/Core/task-duration-eta/verification.md"
related_issues: []
related_prs: []
---

# Plan: Task duration estimates and ETA on results

## Overview

ベンチマーク実行中および結果画面で、タスク単位の所要時間（被検 / judge 内訳）と残り時間予測
（ETA）を利用者が確認できるようにする。現状は run 全体の `execution_duration_ms`
（wall-clock）のみが保存され、タスク粒度の timing や進行中の ETA は未提供である。

本変更は timing 計測の永続化と ETA 表示にスコープを限定する。時間 ROI の算出式修正は
`Core-Enhance-41` に委ね、本タスクでは ROI 分母の再利用可能な timing フィールドを整備する。

## Scope

- 各通常タスク完了時に被検・judge の `duration_ms` をタスク結果 JSON へ永続化する。
- `TaskResult.to_dict()`、`ResultStorage` 保存 JSON、API 変換（`client.ts`）に timing フィールドを
  追加する。
- `server.py` の SSE progress payload に ETA 計算結果を載せる。
- `RunPage` 実行中 UI に残り時間見積もりを表示する。
- `ResultDetail` のタスクカードに per-task duration（被検 / judge 内訳）を表示する。
- 初回実行・実測不足時の ETA フォールバック（推定不可 / step ベース）を実装する。
- backend / frontend 回帰テストと docs validator を実行する。

## Non-Goals

- ダッシュボードや `CostSection` の時間 ROI 算出式の変更（`Core-Enhance-41`）。
- 包括評価タスクの ETA を通常 lane と同一ロジックへ統合すること（別表示または除外でよい）。
- 過去 run を横断した履歴ベース ETA（本 run 内の完了タスク実測のみを正典とする）。
- adapter レベルの計測方式変更（既存 `UsageMetrics.duration_ms` を再利用する）。

## Requirements

- AC-001: 各通常タスク結果 JSON に `subject_duration_ms` と `judge_duration_ms`（または同等の
  `task_timing` オブジェクト）が含まれ、run 全体の `execution_duration_ms` だけに依存しない。
- AC-002: SSE progress で完了済みタスク実測に基づく ETA が frontend に届き、Run 画面で表示される。
- AC-003: 結果詳細画面でタスクごとの所要時間目安（被検 / judge 内訳）が読める。
- AC-004: 実測が不足する初回実行では ETA が「推定不可」または step ベースのフォールバックとなり、
  誤った確定値を示さない。

## Tasks

1. `BenchmarkEngine` と `cost_estimator` の usage 集計経路を調査し、タスク単位 timing 抽出関数を
   追加する（judge runs の usage 合算、subject multi-turn の duration 合算を含む）。
2. `TaskResult.to_dict()` と保存 JSON schema に `task_timing` を追加する。
3. `server.py` progress event builder に ETA 計算（完了タスク平均 × 残タスク、または step 比率）を
   組み込む。
4. frontend types / `client.ts` / `runStore` / `RunPage` に ETA 表示を接続する。
5. `ResultDetail` の `TaskResultCard` に per-task duration 表示を追加する。
6. 保存 JSON・ETA フォールバック・usage 整合の unit / node test を追加する。

## QA Plan

- Risk: Medium。保存 JSON schema 追加と SSE payload 拡張が対象。評価 engine の採点意味論は対象外。
- `AC-001` は engine / storage unit test、`AC-002` は server progress builder test と RunPage 表示
  review、`AC-003` は client 変換 test と ResultDetail review、`AC-004` は ETA helper test で確認する。
- `DEC-001`〜`DEC-003` は verification で Intent の change freedom と fallback 方針を review する。

## Deployment / Rollout

- SSE progress への additive field のため段階 rollout は不要。旧 frontend は未知 field を無視できる。
- 保存 JSON への additive field のため既存 result ファイルの migration は不要。欠落時は UI が
  N/A 表示する。
- rollback は timing field 追加、ETA 計算、UI 表示を同時に戻せばよい。
