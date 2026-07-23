---
title: "Plan: Holistic bundled_responses context overflow handling"
status: completed
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/holistic-context-overflow/decision.md"
  - "_docs/qa/Core/holistic-context-overflow/test-plan.md"
  - "_docs/archives/survey/Core/holistic-context-overflow/survey.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# Plan: Holistic bundled_responses context overflow handling

## Overview

包括評価は被験 LLM を呼ばず、通常タスクの全出力を `BenchmarkEngine._build_bundled_responses`
で1テキストに連結して judge に渡す。タスク数やレスポンス長が増えると、judge LLM の
コンテキストウィンドウを超え、API エラー（context length exceeded）で run が失敗する。
本変更は超過を事前検知し、切り詰めで安全に評価を完走させ、処理内容を結果メタデータと
ログへ残す。

## Scope

- `_build_bundled_responses` および `run_holistic_task` から judge user prompt 組み立てまでの
  入力サイズ見積もりと上限チェックを追加する。
- judge モデルごとの利用可能コンテキスト予算を解決する（adapter / 設定 / 保守的デフォルト）。
- 超過時は v1 として単一 judge 呼び出し内での切り詰めを適用する（Intent `DEC-002`）。
- truncation / overflow メタデータを holistic `TaskResult`（または同等の結果 JSON フィールド）へ
  付与する。
- 通常規模の bundled_responses では従来と同一の judge 入力形式を維持する。
- 超過・非超過の unit test を追加する。
- `_docs/reference/Core/holistic-evaluation.md` に overflow 処理とメタデータ契約を追記する。

## Non-Goals

- 分割評価（複数 judge 呼び出し）と chunk 間スコア集約（Intent 再検討時まで defer）。
- 要約バンドルや段階評価（中間要約 LLM 呼び出し）の導入。
- adapter への context window 自動取得 API の全面整備（v1 は設定 + 保守的デフォルトで足りる）。
- 通常 per-task judge 入力への同様の overflow 処理（holistic bundled 入力に限定）。
- UI 専用の truncation 警告コンポーネント（v1 は結果 JSON / ログ / 既存 Result 画面での
  メタデータ表示で足りる場合は最小限）。

## Requirements

- 推定サイズが judge 予算を超える場合、API 呼び出し前に明示的な overflow 処理を適用する。
- 切り詰めは rubric・eval prompt・trust envelope を優先し、bundled subject answer を調整する。
- overflow 処理が発生した run では、judge 結果または holistic task メタデータから
  truncation が検知できる。
- 非超過ケースでは `_build_bundled_responses` の出力形式（タスク見出し・区切り）を変えない。
- context length exceeded による judge サイレント失敗を避け、テストで再現する。

## Tasks

1. `_build_bundled_responses` と `_build_judge_user_prompt` 経由の holistic 入力組み立てを
   survey どおり整理し、固定 overhead（system prompt、rubric、eval prompt、envelope）を見積もる。
2. judge モデル名 → コンテキスト上限の解決関数を追加する（adapter 拡張、設定 map、
   未解決時の conservative default）。
3. bundled subject answer に対する truncation 戦略を実装する（task 境界を保ち、末尾から削る
   または response body を per-task で truncate）。
4. `run_holistic_task` が truncation メタデータ（例: `bundling_metadata`）を `TaskResult.to_dict()`
   に含めるよう拡張する。
5. 超過シナリオ・非超過シナリオ・メタデータ記録の unit test を `tests/test_benchmark_engine.py`
   等へ追加する。
6. reference と QA test-plan に従い verification を行う。

## QA Plan

- Risk: Medium。judge 入力サイズと結果メタデータが対象で、採点方式そのものは v1 では変えない。
- `AC-001` は engine unit test で budget check と truncation 適用を確認する。
- `AC-002` は `TaskResult.to_dict()` とログ出力の review でメタデータを確認する。
- `AC-003` は既存 holistic 相当サイズの fixture で byte-level または normalized diff を確認する。
- `AC-004` は synthetic oversized bundle で API エラーに到達しないことを unit test する。
- `DEC-001`〜`DEC-004` は verification で change freedom と fallback 方針を review する。

## Deployment / Rollout

- API / 結果 JSON への additive metadata 追加であり、旧 consumer は未知フィールドを無視できる。
- rollback は overflow guard と metadata 付与を戻すだけでよく、保存済み results の migration は
  不要である。
