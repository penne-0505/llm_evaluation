---
title: "Plan: Separate judge model for holistic evaluation"
status: completed
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/holistic-judge-model/decision.md"
  - "_docs/qa/Core/holistic-judge-model/test-plan.md"
  - "_docs/archives/survey/Core/holistic-judge-model/survey.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# Plan: Separate judge model for holistic evaluation

## Overview

現状 `RunRequest.judge_models` が通常タスク judge と包括評価（`run_holistic_task`）の両方に
使われる。`ExecutionPresetConfig` にも holistic 専用 judge フィールドはない。本変更は
holistic 専用 judge モデルを Run 設定・preset・backend 実行・結果保存・UI 表示まで
一貫して分離し、未指定時は従来どおり `judge_models` を holistic にも使う（後方互換）。

## Scope

- `RunRequest` に optional `holistic_judge_models: List[str]` を追加する（名称は Intent で確定）。
- `server.py` で standard judge adapters と holistic judge adapters を別解決し、
  `BenchmarkEngine` へ holistic 実行時のみ holistic 用 adapter セットを渡す。
- holistic 未実行（`run_holistic=false`）時は holistic judge 設定を無視する。
- 保存結果 JSON に `holistic_judge_models`（または同等キー）を記録する。
- frontend: `ExecutionPresetConfig`、`captureExecutionPresetConfig` / `resolveExecutionPresetConfig`、
  Run フロー（`buildRunRequestBody`、RunPage 設定 UI）を拡張する。
- 結果画面（`ResultDetail` 等）で通常 judge と holistic judge を区別表示する。
- strict mode との整合方針を Intent `DEC-005` に従い実装する。
- unit / node test と reference 更新を行う。

## Non-Goals

- holistic judge の temperature / system prompt 分離（v1 は model 選択のみ）。
- strict preset への holistic judge 固定（official strict は per-task judge のみ検証対象）。
- adapter usage 集計 UI の全面再設計（holistic judge モデル名の記録と表示が最低限）。
- holistic context overflow 処理（Core-Enhance-35 別タスク）。

## Requirements

- Run / preset で holistic judge を通常 judge とは別に指定できる。未指定時 fallback は
  `judge_models`。
- `engine.run_holistic_task` は holistic 用 adapter セット、`judge_runs`、並列設定の影響を
  受ける。
- 結果 JSON と UI で holistic judge 情報が通常 judge と区別できる。
- preset 保存・復元が holistic judge 設定を含む。
- Intent に設計理由 DEC が残り、QA で通常のみ / holistic のみ / 両方別指定を検証する。

## Tasks

1. API スキーマ確定: `holistic_judge_models` を backend `RunRequest` と frontend `RunParams` /
   `ExecutionPresetConfig` へ追加する。
2. `settingsStore` に `holisticJudgeModelIds`（または同等 state）を追加し、RunPage UI に
   holistic judge 選択を配置する（Run ページまたは既存 judge セクション内の sub-section）。
3. `server.py` で `get_available_judge_adapters(req.holistic_judge_models or req.judge_models)`
   を holistic ブロック専用に解決し、engine へ holistic 実行時だけ渡す。
4. `BenchmarkEngine` に holistic judge adapters を注入する方法を決める（コンストラクタ分離、
   `run_holistic_task` 引数、または run 時 override）。
5. `benchmark_result` に `holistic_judge_models` を保存し、`client.ts` converter と
   `ResultDetail` 表示を更新する。
6. `captureExecutionPresetConfig` / `resolveExecutionPresetConfig` と node test を更新する。
7. QA test-plan に従い verification を行う。

## QA Plan

- Risk: Medium。adapter 解決、並列制御、usage 集計、strict mode 境界が絡む。
- `AC-001` は RunRequest / preset capture の schema test と UI review で確認する。
- `AC-002` は server holistic path と engine mock で adapter 分離を確認する。
- `AC-003` は saved JSON と ResultDetail diff で確認する。
- `AC-004` は `executionPresets.node.test.ts` / `settingsStore.node.test.ts` で確認する。
- `AC-005` は Intent DEC review と 3 パターン integration test で確認する。
- `DEC-001`〜`DEC-005` を verification で review する。

## Deployment / Rollout

- API への optional field 追加と結果 JSON additive key のため、旧 frontend / 旧 results は
  fallback で動作する。
- rollback は field と UI を戻すだけでよく、migration は不要である。
