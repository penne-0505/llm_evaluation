---
title: "Plan: Cross-process index safety"
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

# Plan: Cross-process index safety

## Overview

Core-Bug-71 で導入した排他は `threading.RLock` によるプロセス内ロックであり、
多重起動した別プロセスからの `index.json` 更新は防げない（DEC-004 の境界）。
`launcher.py` は空きポートへフォールバックするため多重起動は実際に到達可能である。
本 plan は着手前の検討範囲を定める。方式は未決であり、決定は着手時に Intent へ記録する。

## Scope

- 多重起動時の結果 index の整合性。
- 多重起動そのものを許すかどうかの方針。

## Non-Goals

- サーバの複数 worker 対応（要件として存在しない）。
- 結果保存先を DB へ移す設計。
- `run_id` の衝突（Core-Bug-72）。

## Requirements

- **Functional**: 2 つのインスタンスが同時に保存・削除しても index が壊れず、entry が失われない。
  または、そもそも 2 つ目のインスタンスが起動しない。
- **Non-Functional**: Windows と Linux の双方で配布するため、移植性のある機構に限る。

## 方式の検討軸（未決）

| 候補 | 利点 | 懸念 |
| --- | --- | --- |
| 単一インスタンス化（ポートまたはロックファイルで検出し、既存ウィンドウを開く） | 競合の原因自体を除去。利用者の期待にも近い | 異常終了後のロック残留の扱い。既存の空きポートフォールバック仕様の変更 |
| プロセス間ロック（ロックファイル） | 多重起動を許したまま整合性を得る | Windows / Linux で挙動差。stale lock の回収が必要 |
| 楽観的整合（書き込み前に mtime / ハッシュを検証し再試行） | 追加の OS 依存が無い | 実装が複雑化。完全な直列化にはならない |

atomic write（DEC-002）により破損の窓は既に狭い。残る主問題は lost update である点を
判断材料にする。単一インスタンス化が最も単純だが、`launcher.py` の既存仕様変更を伴う。

## Tasks

1. [ ] 多重起動が実際にどこまで許容されているか（launcher の仕様と利用者の期待）を確認する
2. [ ] 方式を決め、Intent（DEC-004 の Revisit）へ記録する
3. [ ] 実装し、2 プロセスを模した regression test を追加する

## QA Plan

- QA document: 着手時に `_docs/qa/Core/cross-process-index-safety/test-plan.md` を作成する
- Risk level: High
- Test strategy:
  - Unit: ロック取得・解放、stale lock の回収（方式による）
  - Integration: 子プロセスを 2 つ起動し、同時に保存・削除させて index を検証する
  - Manual QA: 実際にアプリを 2 回起動して挙動を確認する
  - Validator / static check: `uv run pytest`
- Category Bug のため regression test を必須とする。
- Risk High のため rollback / recovery / data safety / security の観点を含める。
  とくに、ロック残留でアプリが起動不能になる失敗モードを検討する。

## Deployment / Rollout

- Rollout: 方式により利用者への影響が変わる。単一インスタンス化を選ぶ場合は挙動変更を guide へ記す。
- Rollback: プロセス内ロックと atomic write は残したまま、プロセス間機構だけを外せる構成にする。
