---
title: "QA Verification: Result index integrity"
status: active
draft_status: n/a
qa_status: partial
risk: High
qa_schema: 2
created_at: 2026-07-26
updated_at: 2026-07-26
references:
  - "_docs/intent/Core/result-index-integrity/decision.md"
  - "_docs/plan/Core/result-index-integrity/plan.md"
  - "_docs/qa/Core/result-index-integrity/test-plan.md"
related_issues: []
related_prs: []
---

# QA Verification: `Result index integrity`

## Summary

`index.json` の lost update・非アトミック書き込み・API 層への index 書き込み経路の散在を解消した。
修正前の欠陥を再現したうえで、追加した regression test が修正前コードで落ちることを確認している。

プロセス内の排他は達成したが、多重起動した別プロセスからの更新は依然として保護されない。
この境界は DEC-004 で意図的に対象外としたものだが、`launcher.py` が空きポートへフォールバックする
ため多重起動は実際に到達可能である。この 1 点により verdict を `PARTIAL` とする。

## Verification Verdict

Verdict: PARTIAL

## Commands Run

```bash
uv run pytest -q
uv run --python 3.12 pytest -q
uv run pytest tests/test_result_index_concurrency.py -q
npm run lint --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
./scripts/check-docs.sh
```

Result:

```text
pytest-3.14=0 :: 220 passed, 23 subtests passed in 1.67s
pytest-3.12=0 :: 220 passed, 23 subtests passed in 1.64s
lint=0  fe-test=0  build=0
```

修正前の欠陥再現（`_load_index` に barrier を挟み最大限に競合させた 20 試行）:

```text
完了 run が index から消失 (履歴に出ない): 1 / 20
削除済みファイルの entry が index に残存 : 8 / 20
index.json が壊れて解析不能              : 11 / 20
整合                                     : 0 / 20
```

追加した regression test を修正前相当のコード（ロック無効化・truncate 書き込み）で実行:

```text
4 failed, 1 passed
FAILED test_concurrent_save_and_delete_stay_consistent
FAILED test_concurrent_saves_do_not_lose_entries
FAILED test_index_file_always_parses_under_concurrency
FAILED test_save_index_leaves_previous_content_on_failure
```

修正後は 5 件すべて pass する。唯一修正前でも通った
`test_failed_write_does_not_leave_temp_files` は、旧実装に一時ファイル自体が存在しないためであり、
新機構の後始末を守るためのテストである。

ロック保持区間の実測（実データ複製 3 件に対して）:

```text
list_summaries  中央値 0.078 ms / 最大 0.176 ms
_upsert_index   中央値 0.214 ms / 最大 0.352 ms
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `uv run pytest -q`（3.14 / 3.12） | PASS | 220 passed。変更前は 213 passed で、追加分 7 件 |
| `tests/test_result_index_concurrency.py` | PASS | 5 件。うち 4 件は修正前コードで落ちることを確認済み |
| `tests/test_result_storage.py` バックフィル 2 件 | PASS | 補完値が結果ファイル再構築値と一致、欠損時は既定値 |
| `npm run lint / test / build --prefix frontend` | PASS | frontend への影響なし |
| `./scripts/check-docs.sh` | PASS | exit 0 |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| 既存の結果ディレクトリで一覧出力が変わらない | PASS | 実データ（`~/.local/share/prism-llm-eval/results`）の複製に対し 3 件取得、欠落フィールド 0、スコア・コスト・strict の値が妥当 |
| 既存 `index.json` が移行なしで読める | PASS | 同上。スキーマ変更なし |
| 原本データを破壊していない | PASS | 検証は複製に対して実施し、`diff -r` で原本無変更を確認 |
| デッドロックが無い | PASS | `RLock` を使用。`save` → `_upsert_index` と `list_summaries` は入れ子にならない |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | `test_concurrent_saves_do_not_lose_entries` / `test_concurrent_save_and_delete_stay_consistent` |
| AC-002 | PASS | `test_index_file_always_parses_under_concurrency` |
| AC-003 | PASS | `test_concurrent_save_and_delete_stay_consistent` |
| AC-004 | PASS | `test_legacy_index_entries_are_backfilled_from_result_file` ほか 1 件、実データ Manual QA |
| AC-005 | PASS | `grep -n "ResultStorage\._" server.py` が 0 件。server.py は 2295 → 2125 行 |
| AC-006 | PASS | 既存 213 件が緑のまま |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | ロック保持区間が `_load_index` から `_save_index` までを覆う。`threading.RLock` のため event loop thread と threadpool thread の双方を排他できる |
| DEC-002 | PASS | `tempfile.mkstemp` + `os.replace`。一時ファイルは索引と同一ディレクトリに作り、原子的置換の前提を満たす |
| DEC-003 | PASS | バックフィルは `ResultStorage._backfill_summary` へ移送。index を書く経路が storage に集約され、API 層の private 参照が消えた |
| DEC-004 | PASS | プロセス内ロックに留め、`fcntl` や DB を導入していない。境界は残リスクとして明示し Core-Bug-73 を起票した |

## Invariant Coverage

- INV-001 (from DEC-002): PASS — 並行更新中に破損した index が観測されないこと、および書き込み失敗時に
  既存 index が保たれることを test で確認。修正前は 20 試行中 11 件で破損していた。
- INV-002 (from DEC-001): PASS — 並行 save / delete で保存済み結果が失われないことを test で確認。
  修正前コードでは同 test が落ちる。

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| 複数プロセス間の排他 | DEC-004 で意図的に対象外。`threading.RLock` はプロセス内のみ | Core-Bug-73 |
| `run_id` の秒精度衝突 | 本タスクの調査中に発見した別欠陥 | Core-Bug-72 |
| 自然スケジューリング下の競合 | test は臨界区間へ遅延を注入して競合を強制する。直列化は証明できるが、あらゆる交錯の非存在は示していない | なし（手法上の限界として明記） |

## Residual Risks

- **多重起動時の index 競合が残る。** 本タスクの排他はプロセス内ロックであり、別プロセスからの
  更新は防げない。`launcher.py` は空きポートを探してフォールバックするため多重起動は実際に可能で、
  両インスタンスが同じ `index.json` を共有する。atomic write により破損の窓は狭まっているが、
  lost update は起きうる。Core-Bug-73 として起票済み。
- `run_id` の秒精度衝突（Core-Bug-72）は未修正であり、同一モデルの同時実行で結果ファイルの
  上書きが起きうる。index の整合とは独立した経路である。

## Follow-up TODOs

- Core-Bug-73: [Bug] Multiple app instances share the results index without cross-process locking
- Core-Bug-72: [Bug] run_id collides at second resolution across concurrent jobs
