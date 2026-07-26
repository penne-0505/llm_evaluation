---
title: "Intent: Result index integrity under concurrent access"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-26
updated_at: 2026-07-26
references:
  - "_docs/plan/Core/result-index-integrity/plan.md"
  - "_docs/qa/Core/result-index-integrity/test-plan.md"
  - "_docs/intent/Core/concurrent-evaluation-jobs/decision.md"
related_issues: []
related_prs: []
---

# Intent: Result index integrity under concurrent access

## Context

`ResultStorage` は結果一覧の高速化のため `index.json` を持つ。更新経路は 3 つあり、
いずれも `_load_index()` → 加工 → `_save_index()` の read-modify-write である。

- `save()` → `_upsert_index()`
- `delete()` → `_remove_from_index()`
- `list_summaries()` の再構築パス

これらの呼び出し元は 2 つの異なるスレッドに跨る。

- `POST /api/run` は `async def` であり、`ResultStorage.save()` を event loop thread で直接呼ぶ。
- `GET /api/results` と `DELETE /api/results/{filename}` は `def`（同期）であり、
  FastAPI はこれらを threadpool thread で実行する。server.py の同期エンドポイントは 33 個ある。

排他制御が無いため lost update が起きる。さらに `_save_index` は `open(path, "w")` で
truncate してから書くため、書き込み自体が非アトミックである。

再現実験（`_load_index` に barrier を挟み最大限に競合させた 20 回試行）:

```text
完了 run が index から消失 (履歴に出ない): 1 / 20
削除済みファイルの entry が index に残存 : 8 / 20
index.json が壊れて解析不能              : 11 / 20
整合                                     : 0 / 20
```

barrier による最悪ケースの実証であり、自然発生頻度ではない。ただし
`Core/concurrent-evaluation-jobs` で同時実行が 3 本まで許可されたことにより、
実行中の run 完了と履歴操作が重なる機会そのものは増えている。

被害の非対称性が重要である。`index.json` が壊れた場合は `_load_index` が例外を握りつぶして
`[]` を返し、`list_summaries` がファイルから再構築するため自己修復する。しかし
**index が非空のまま entry を失った場合は再構築が走らず、その run は履歴から恒久的に消える**。
結果 JSON ファイル自体はディスクに残るため、データ損失ではなく可視性の損失である。

## Decisions

### DEC-001: index の read-modify-write を `threading` のロックで直列化する

- **What**: `_upsert_index` / `_remove_from_index` / `list_summaries` の再構築を、
  load から save までロック保持下で行う。
- **Why**: 更新経路が event loop thread と threadpool thread に跨るため、両者を同じ
  排他機構で守る必要がある。ロックの範囲を load から save までにしないと、
  読んだ値が書く前に古くなるという問題自体は解けない。
- **Change freedom**: ロックの粒度、種類（`Lock` / `RLock`）、保持区間の実装は変更できる。
  「1 つの index 更新が他の更新と交錯しない」ことを保てばよい。
- **Why not**: `asyncio.Lock` は event loop に束縛されるため threadpool 側の更新を守れない。
  同時実行 run 同士（どちらも event loop thread）だけを見て「単一スレッドだから安全」と
  判断すると、同期エンドポイント経由の更新を見落とす。

### DEC-002: index の書き込みを一時ファイル + `os.replace` でアトミックにする

- **What**: `_save_index` は同一ディレクトリの一時ファイルへ書いてから `os.replace` で差し替える。
- **Why**: `open(path, "w")` は truncate してから書くため、書き込み途中の状態が他スレッドや
  プロセス異常終了に晒される。実測で 20 回中 11 回、index が解析不能になった。
  ロックだけでは、書き込み中のクラッシュによる破損を防げない。
- **Change freedom**: 一時ファイル名、`fsync` の有無、`os.replace` 以外の等価な原子的置換は変更できる。
- **Why not**: ロックのみで足りるとする案は、単一プロセス内の競合しか防げず、
  クラッシュ時の半端な書き込みを残す。

### DEC-003: 後方互換バックフィルを API 層から `ResultStorage` へ移す

- **What**: `server.py` の `list_results` にある約 170 行の欠落フィールド補完を
  `ResultStorage.list_summaries()` 側へ移し、API 層は取得と丸めだけを行う。
- **Why**: 現状 API 層が `ResultStorage._build_summary` を 2 回、`_save_index` を 1 回、
  private として直接呼んでいる。index の整合性は storage の責務であり、
  ロックを storage 側に置く以上、index を書く経路が API 層に残っていると排他が破れる。
  加えて、ファイル存在時・非存在時・例外時でデフォルト値ブロックが三重複しており、
  フィールドを 1 つ足すたび 4 箇所を触る構造になっている。
- **Change freedom**: バックフィル対象フィールドの判定方法、再保存の条件は変更できる。
- **Why not**: server 側に置いたままロックだけ足す案は、private 参照と三重複を温存し、
  index を書く経路がロックの外に残る。

### DEC-004: 単一プロセス前提を維持し、ファイルロックや DB へ移行しない

- **What**: プロセス内ロックで解決し、`fcntl` などのプロセス間ロックや DB は導入しない。
- **Why**: 本アプリは `launcher.py` と `packaging/` が示す通りローカル単一プロセスの
  デスクトップアプリであり、複数プロセスからの同時書き込みは要件にない。
  過剰な機構は移植性（Windows / Linux 双方で配布する）と保守性を下げる。
- **Change freedom**: 将来プロセス間排他が必要になった場合の実装方式は未定でよい。
- **Revisit when**: サーバを複数 worker / 複数プロセスで動かす要件が出た時。
  `_docs/intent/DevOps/code-ci-gate/decision.md` の DEC-002 と同じ前提に立っている。

## Consequences / Impact

- `ResultStorage` の index 更新は直列化される。index は小さく更新頻度も低いため、
  スループットへの実質的な影響はない。
- `server.py` の `list_results` が大幅に縮む。private 参照 3 箇所が消える。
- `list_summaries()` の戻り値は、欠落フィールドが補完済みであることを保証するようになる。
  API 層はこれに依存してよい。
- 既存の `index.json` はそのまま読める。スキーマ変更を伴わない。

## Quality Implications

- 保存に成功した結果が履歴から消えないこと。これは利用者から見て最も分かりにくい失敗である。
- `index.json` が常に単一の完全な JSON として読めること。
- バックフィルの移送が既存の一覧表示結果を変えないこと（behavior preservation）。
- ロックを追加した箇所でデッドロックを作らないこと。`save()` が内部で `list_summaries()` を
  呼ぶような入れ子が生じないか確認する。

## Intent-derived Invariants

- INV-001 (from DEC-002): `index.json` は常に単一の完全な JSON 配列として読める。
  書き込み途中の状態が観測されない。
- INV-002 (from DEC-001): 保存に成功した結果は、並行する index 操作があっても index から失われない。

## Enforced in (optional)

- `core/result_storage.py` の index 更新経路 — DEC-001 / DEC-002 / DEC-003
- `tests/test_result_index_concurrency.py` — INV-001 / INV-002

## Rollback / Follow-ups

- Rollback: ロックと atomic write は独立して戻せる。バックフィル移送を戻す場合は
  `server.py` 側の実装を復元する必要があり、単独では戻さない。
- Follow-up: `run_id` は秒精度（`server.py`）のため、同一モデルの run を同じ秒に開始すると
  衝突する。本 intent の対象外であり、Core-Bug-72 として起票した。
