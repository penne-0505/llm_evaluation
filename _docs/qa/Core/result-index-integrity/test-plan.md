---
title: "QA Test Plan: Result index integrity"
status: active
draft_status: n/a
qa_status: planned
risk: High
qa_schema: 2
created_at: 2026-07-26
updated_at: 2026-07-26
references:
  - "_docs/intent/Core/result-index-integrity/decision.md"
  - "_docs/plan/Core/result-index-integrity/plan.md"
related_issues: []
related_prs: []
---

# QA Test Plan: `Result index integrity`

## Source of Intent

- TODO: Core-Bug-71
- Plan: `_docs/plan/Core/result-index-integrity/plan.md`
- Intent: `_docs/intent/Core/result-index-integrity/decision.md`

## Quality Goal

保存に成功した評価結果が履歴から消えないこと、および `index.json` が常に
解析可能な状態に保たれること。あわせて、バックフィルの移送が既存の一覧表示結果を変えないこと。

## Acceptance Criteria

- AC-001: `save` と `delete` を別スレッドから同時実行しても、保存済み結果が index から失われない。
- AC-002: 同条件で `index.json` が常に完全な JSON として解析できる。
- AC-003: 削除した結果の entry が index に残らない。
- AC-004: バックフィル移送前後で、欠落フィールドを含む既存 index に対する一覧出力が同値である。
- AC-005: `server.py` から `ResultStorage` の private 参照（`_build_summary` / `_save_index`）が無くなる。
- AC-006: 既存の backend テストが緑のままである（behavior preservation）。

## Decision Review Scope

- DEC-001: ロックの保持区間が load から save までを覆っているか。
- DEC-002: 書き込みが原子的置換になっているか。
- DEC-003: index を書く経路が `ResultStorage` に集約されたか。
- DEC-004: プロセス内解決に留まり、プロセス間機構を導入していないか。

## Intent-derived Invariants

- INV-001 (from DEC-002): `index.json` は常に単一の完全な JSON 配列として読める。
- INV-002 (from DEC-001): 保存に成功した結果は、並行する index 操作があっても失われない。

## Risk Assessment

- Risk level: High
- Risk rationale: 評価結果の可視性に関わる。失敗すると利用者は「実行したはずの結果が無い」という
  最も原因を追いにくい形で影響を受ける。
- Regression risk: バックフィル移送は約 170 行の挙動を別モジュールへ動かす。
  欠落フィールドの補完結果が変わると、一覧表示のスコア・コストが変化しうる。
- Data safety risk: 結果 JSON 本体は変更しない。index のみを対象とする。
  移送・ロック導入のいずれも既存ファイルの書き換えを伴わない。
- Security / privacy risk: なし。secret を扱わず、外部入力の解釈も変えない。
- UX risk: 一覧取得がロック待ちで遅くなる可能性。index は小さく更新頻度も低いため影響は限定的。
- Agent misbehavior risk: 「並行実行は event loop 単一スレッドだから安全」という誤った一般化で
  排他を外すこと。同期エンドポイントが threadpool で走る事実を intent に明記して防ぐ。

## Test Strategy

- Unit: `_save_index` の原子性、バックフィル出力の同値性
- Integration: 複数スレッドからの `save` / `delete` 同時実行（barrier で競合を強制）
- E2E: 対象外
- Manual QA: 欠落フィールドを含む既存 index を読み込み、一覧出力を移送前と比較
- Validator / static check: `uv run pytest -q`、`./scripts/check-docs.sh`
- Diff review: `server.py` の private 参照が消えていること

## Test Matrix

| ID | Source | Requirement / Optional Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | 保存済み結果が失われない | integration | `tests/test_result_index_concurrency.py` | 全試行で保存 run が index に存在 | planned |
| AC-002 | TODO | index が常に解析可能 | integration | `tests/test_result_index_concurrency.py` | 全試行で JSON 解析成功 | planned |
| AC-003 | TODO | 削除 entry が残らない | integration | `tests/test_result_index_concurrency.py` | 削除対象が index に不在 | planned |
| AC-004 | TODO | バックフィル同値性 | unit | `tests/test_result_storage.py` | 移送前後で同一の summary | planned |
| AC-005 | TODO | private 参照の除去 | diff review | `server.py` | `ResultStorage._` の参照 0 件 | planned |
| AC-006 | TODO | 既存テスト緑 | unit | `uv run pytest -q` | 全 pass | planned |
| INV-001 | DEC-002 | 完全な JSON として読める | integration | `tests/test_result_index_concurrency.py` | 破損 0 件 | planned |
| INV-002 | DEC-001 | 保存結果が失われない | integration | `tests/test_result_index_concurrency.py` | lost update 0 件 | planned |

## Manual QA Checklist

- [ ] 欠落フィールドを含む既存 index から一覧を取得し、移送前と同じ結果になる。
- [ ] 既存の `index.json` が移行なしで読める。

## Regression Checklist

- [ ] `uv run pytest -q` が緑。
- [ ] `list_summaries` に入れ子ロックによるデッドロックが無い。
- [ ] 一覧取得の応答が体感で変わらない。

## High-risk Checklist

Use this section only for Risk High / Critical.

- [ ] Rollback or recovery path is documented.（ロックと atomic write は独立して revert 可能）
- [ ] Data safety has been checked.（結果 JSON 本体は不変。index のみ対象）
- [ ] Security / privacy implications have been checked.（secret・外部入力を扱わない）
- [ ] Failure mode is understood.（lost update / 破損 / stale entry の 3 種を再現済み）

## Out of Scope

- プロセス間排他および DB 移行（DEC-004）。
- `run_id` の秒精度衝突（Core-Bug-72）。
- `/api/run` の抽出。
- 同期エンドポイントの async 化。

## Open Questions

- 一覧取得の再保存（reindex）をロック内で行うか、必要時のみに絞るか。
