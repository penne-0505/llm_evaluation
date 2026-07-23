---
title: "Plan: Fix time ROI calculation (subject vs judge timing)"
status: completed
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/time-roi-task-timing/decision.md"
  - "_docs/qa/Core/time-roi-task-timing/test-plan.md"
  - "_docs/archives/survey/Core/time-roi-task-timing/survey.md"
  - "_docs/intent/Core/task-duration-eta/decision.md"
related_issues: []
related_prs: []
---

# Plan: Fix time ROI calculation (subject vs judge timing)

## Overview

時間 ROI（平均点 / 秒）が run wall-clock（`execution_duration_ms`）や暗黙フォールバックに
依存しており、並列 judge 実行時に「モデル処理時間あたりの得点」と一致しない。`Core-Feat-34`
で整備するタスク単位 timing を正典として、run サマリー・結果詳細・ダッシュボードの時間 ROI
を subject + judge 合算定義へ統一する。

## Scope

- `Core-Feat-34` の `task_timing` フィールドを run サマリー（subject / judge / total ms）へ合算する。
- `server.py` / `cost_estimator` の run 保存 payload に timing totals を付与する（または
  `usage_summary*` との関係を Intent で固定する）。
- `ResultDetail.tsx` の `CostSection` 時間 ROI 計算を task 合算ベースへ更新する。
- `DashboardPage.tsx` の `avgExecutionTimeMs` と `formatTimeRoi` を同一定義へ更新する。
- `client.ts` 変換と summary index が timing totals を保持するよう更新する。
- 内訳欠落 run の N/A / 明示ラベル fallback 方針を実装する（DEC-003）。
- backend / frontend テストと verification 記録を追加する。

## Non-Goals

- 実行中 ETA 表示（`Core-Feat-34`）。
- コスト ROI（USD ベース）の算出式変更。
- 包括評価のみの timing をダッシュボード集計へ含めるかの全面再設計（Intent DEC-004 で最小方針
  を決定）。
- 旧 result JSON の backfill migration（欠落時は N/A 表示）。

## Requirements

- AC-001: 各タスク結果の被検・judge ms が run サマリーへ正しく合算される。
- AC-002: `ResultDetail` の時間 ROI と `DashboardPage` の時間 ROI が同一の subject+judge 合算定義を
  用い、並列 wall-clock を分母に使わない。
- AC-003: 内訳欠落 run では N/A または部分表示とし、`executionDurationMs` への暗黙フォールバックを
  廃止するか「推定（wall-clock）」と明示する。
- AC-004: `core/cost_estimator.py` の usage duration 集計との整合性がテストで検証される。

## Tasks

1. `Core-Feat-34` 完了後、`task_timing` と API / 保存形式を確認する。
2. run サマリー生成（`server.py`、必要なら `cost_estimator` helper）をタスク合算ベースに更新する。
3. `client.ts` / types に timing totals を追加し、summary index から Dashboard へ渡す。
4. `ResultDetail.tsx` の `CostSection` 時間 ROI を更新する。
5. `DashboardPage.tsx` の `buildModelAggregates` と時間 ROI 列を更新する。
6. backend / frontend テストを追加し、verification を記録する。

## QA Plan

- Risk: Medium。表示指標の定義変更は過去 run との数値比較に影響するが、保存データ migration は
  行わない。
- `AC-001` は storage / server unit test、`AC-002` は frontend unit test と diff review、
  `AC-003` は旧フォーマット fixture、`AC-004` は cost_estimator 整合 test で確認する。
- `DEC-001`〜`DEC-004` は verification で ROI 分母定義と fallback 方針を review する。

## Deployment / Rollout

- ダッシュボード時間 ROI 数値は定義変更により変わる可能性がある。利用者向けに「モデル処理時間
  ベースへ変更」と release note を検討する。
- rollback は ROI 計算と summary field 追加を戻す。`task_timing` 永続化（Feat-34）は維持可能。
