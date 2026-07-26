---
title: "Plan: Result index integrity"
status: active
draft_status: n/a
created_at: 2026-07-26
updated_at: 2026-07-26
references:
  - "_docs/intent/Core/result-index-integrity/decision.md"
  - "_docs/qa/Core/result-index-integrity/test-plan.md"
related_issues: []
related_prs: []
---

# Plan: Result index integrity

## Overview

`index.json` の read-modify-write 競合と非アトミック書き込みを解消し、
API 層に残っている index 書き込み経路を `ResultStorage` へ集約する。

前提として `Code CI` gate（`_docs/intent/DevOps/code-ci-gate/decision.md`）が緑であり、
behavior preservation を機械的に確認できる状態にある。

## Scope

- index 更新経路（`_upsert_index` / `_remove_from_index` / `list_summaries` 再構築）の直列化。
- `_save_index` の atomic write 化。
- `server.py` の `list_results` にある後方互換バックフィルの `ResultStorage` への移送。
- 上記を検証する並行テストの追加。

## Non-Goals

- プロセス間排他（`fcntl` 等）や DB への移行。intent の DEC-004 を参照。
- `run_id` の秒精度衝突（Core-Bug-72 として別途起票済み）。
- `server.py` の `/api/run` 抽出。これは別タスクであり、本タスクの完了後に行う。
- 同期エンドポイント 33 個を async へ変える作業。実行コンテキストの前提は変えない。

## Requirements

- **Functional**: 保存に成功した結果が履歴一覧から失われない。削除した結果の entry が残らない。
  `index.json` が常に完全な JSON として読める。
- **Non-Functional**: 一覧取得の応答が実用的な範囲に留まる。既存 `index.json` を移行なしで読める。

## Tasks

1. [ ] `ResultStorage` に index 用ロックを導入し、3 つの更新経路を保持区間で包む
2. [ ] `_save_index` を一時ファイル + `os.replace` へ変更
3. [ ] バックフィルを `list_summaries()` へ移送し、`server.py` の private 参照を除去
4. [ ] 並行テストを追加（lost update / 破損の双方）
5. [ ] 既存テストが緑であることを確認し、verification を残す

## QA Plan

- QA document: `_docs/qa/Core/result-index-integrity/test-plan.md`
- Risk level: High
- Test strategy:
  - Unit: `_save_index` の atomic 性、バックフィルの出力同値性
  - Integration: 複数スレッドからの `save` / `delete` / `list_summaries` 同時実行
  - E2E: 対象外
  - Manual QA: 既存の結果ディレクトリを読み込み、一覧表示が変わらないことを確認
  - Validator / static check: `uv run pytest`、`./scripts/check-docs.sh`
- AC と INV は test-plan の Test Matrix で確認手段へ割り当てる。
- 影響する DEC は DEC-001 から DEC-004。verification の Decision Conformance で review する。
- Category Bug のため regression test を必須とする。Category Refactor の側面
  （バックフィル移送）については behavior-preservation checks を必須とする。
- Risk High のため rollback / recovery / data safety / security の観点を含める。

## Deployment / Rollout

- Rollout: ライブラリ内部の変更であり、利用者側の操作は不要。既存 `index.json` はそのまま読める。
- Rollback: ロックと atomic write は独立して revert できる。バックフィル移送は
  `server.py` 側の復元を伴うため単独では戻さない。
- 監視: 一覧表示の欠落・重複が報告されないこと。
