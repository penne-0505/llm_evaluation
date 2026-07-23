---
title: "Plan: Subject multi-run judge batch evaluation"
status: completed
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/survey/Core/subject-multi-run-judge-batch/survey.md"
  - "_docs/intent/Core/subject-multi-run-judge-batch/decision.md"
  - "_docs/qa/Core/subject-multi-run-judge-batch/test-plan.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# Plan: Subject multi-run judge batch evaluation

## Overview

通常タスクは現状 **被験 1 回 → judge `judge_runs` 回** で実行される。被験側の出力ばらつきを
judge に渡す手段がなく、安定性評価や best-effort 推定ができない。

本変更は `subject_runs`（被験実行回数）を Run 設定に追加し、指定回数だけ被験を実行したのち、
各 run の `response`（および必要なら `tool_trace`）を **1 回の judge 評価入力** として束ねる。
評価セマンティクスは Survey で比較した方式のうち **list-eval bundled** を採用する
（Intent DEC-001）。holistic の `_build_bundled_responses` パターンを同一 task 内 multi-run へ
拡張する。

## Scope

- `RunRequest` / `ExecutionPresetConfig` / Run UI / Settings に `subject_runs`（default 1）を追加。
- `BenchmarkEngine.run_task` を N 回被験実行 + bundled judge 入力対応に拡張する。
- judge system / rubric 契約に「複数被験試行」の評価指示を追加（`subject_runs=1` は現行同等）。
- 結果 JSON に run 別被験出力・usage・合算メタデータを保存する。
- frontend 結果画面で複数 run と usage / cost / 時間を表示する。
- `subject_runs` と `judge_runs` の独立性を engine / server / UI で保証する。
- backend / frontend / プロンプト契約のテストを追加する。

## Non-Goals

- best-of 自動選択、被験 run 別の個別 judge スコア平均（per-run judge）は初版対象外。
- holistic bundled（複数 **task** 横断）の schema や strict mode hash 契約を変更しない。
- 被験 run 間の並列実行最適化（初版は直列または既存 `subject_parallel` 方針に従う）。
- 動的コンテキスト分割（超長回答の自動 truncate / 分割 judge）は初版対象外。

## Requirements

- **Functional**
  - AC-001: UI / API から `subject_runs >= 1` を指定できる。
  - AC-002: `run_task` が N 回被験し、出力を judge 1 入力に束ねる。`judge_runs` と独立。
  - AC-003: プロンプト契約が複数出力評価を明示。`subject_runs=1` で後方互換。
  - AC-004: 結果に run 別データと usage 追跡。
  - AC-005: コスト・時間・コンテキスト影響を Intent に記録し QA で代表ケース検証。
- **Non-Functional**
  - `subject_runs` に上限（Intent 定義、例: 5）を設ける。
  - 保存 JSON は旧 consumer が単一 `response` を読める後方互換を保つ。

## Tasks

1. Survey / Intent で list-eval bundled と Non-Goals を確定する（完了）。
2. `_build_bundled_subject_runs`（仮）を holistic bundler と共通化可能な形で実装する。
3. `run_task` を multi-subject loop + bundled `subject_response` に変更する。
4. `RunRequest` / preset / settings / RunPage UI に `subject_runs` を配線する。
5. judge プロンプト（system + rubric 注記）を更新する。
6. 結果保存 schema と ResultDetail 表示を更新する。
7. usage 集計（`summarize_subject_usage` 等）を multi-run 対応する。
8. QA test-plan に従い検証し、`verification.md` に verdict を残す。

## QA Plan

- Risk: High。評価意味論変更、API コスト増、コンテキスト上限が該当。
- High-risk Checklist を `_docs/qa/Core/subject-multi-run-judge-batch/test-plan.md` に記載する。
- Test Matrix で 1 run / N run / エラー混在 / 上限 clamp をカバーする。

## Deployment / Rollout

- `subject_runs` default 1 のため既存 run 挙動は維持される。
- 新 field は additive。旧 frontend は `subject_runs` 未送信 → backend default 1。
- rollback は multi-run 分岐と UI を戻す。保存済み multi-run 結果は読取専用表示を維持するか
  Intent DEC-003 に従う。
