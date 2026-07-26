---
title: "Plan: Run identity collision"
status: proposed
draft_status: n/a
created_at: 2026-07-26
updated_at: 2026-07-26
references:
  - "_docs/intent/Core/result-index-integrity/decision.md"
  - "_docs/qa/Core/result-index-integrity/test-plan.md"
related_issues: []
related_prs: []
---

# Plan: Run identity collision

## Overview

`run_id` が秒精度のため、同一モデルの評価を同じ秒に開始すると識別子が衝突する（Core-Bug-72）。
本 plan は着手前の検討範囲を定める。実装方式は未決であり、決定は着手時に Intent へ記録する。

## Scope

- `run_id` の生成方式。
- `ActiveRunRegistry.try_start` が重複 `run_id` を受けたときの意味論。
- `_cancel_flags` の分離。
- `ResultStorage.save` の結果ファイル名衝突。

## Non-Goals

- index の排他制御（Core-Bug-71 で対応済み）。
- 複数プロセス間の排他（Core-Bug-73）。

## Requirements

- **Functional**: 同時実行される run が一意に識別され、キャンセルと完了が互いに干渉しない。
  同じ秒に完了した同一モデルの結果ファイルが上書きされない。
- **Non-Functional**: `run_id` はログと結果 JSON に現れるため、人が読んで実行を特定できる形を保つ。

## Requirements の検討軸（未決）

| 論点 | 候補 | 判断基準 |
| --- | --- | --- |
| `run_id` 生成 | 秒精度 + 短い乱数/ 連番サフィックス、UUID、開始時刻のミリ秒化 | 可読性を保ちつつ一意。既存 run_id 形式に依存する箇所の互換 |
| `try_start` 重複時 | `False` を返す、例外、常に一意 ID 前提にして分岐を削除 | 同時上限の計上が正しくなること |
| 結果ファイル名 | `run_id` 由来にする、衝突時にサフィックス付与 | 既存ファイルを上書きしない |

`run_id` は結果 JSON の `run_id` フィールドと履歴 UI に現れるため、形式変更の影響範囲を
着手時に洗い出す。既存の結果ファイルを再解釈しない方針を優先する。

## Tasks

1. [ ] `run_id` に依存している箇所を洗い出す（server / core / frontend / 保存済み JSON）
2. [ ] 生成方式と `try_start` の意味論を決め、Intent へ記録する
3. [ ] 実装し、同一秒・同一モデルの並行 run で regression test を追加する

## QA Plan

- QA document: 着手時に `_docs/qa/Core/run-identity-collision/test-plan.md` を作成する
- Risk level: High
- Test strategy:
  - Unit: `run_id` 生成の一意性、`try_start` の重複時挙動
  - Integration: 同一モデル・同一秒に開始した 2 run の完了とキャンセルの独立性
  - Manual QA: 既存の履歴が引き続き表示されること
  - Validator / static check: `uv run pytest`
- Category Bug のため regression test を必須とする。
- Risk High のため rollback / recovery / data safety / security の観点を含める。

## Deployment / Rollout

- Rollout: 内部識別子の変更であり利用者操作は不要。既存の結果ファイルは読み替えない。
- Rollback: 生成方式の変更は単独で revert できる。
