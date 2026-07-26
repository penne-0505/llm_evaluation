---
title: "Intent: Code CI gate for backend and frontend"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-26
updated_at: 2026-07-26
references:
  - "_docs/plan/DevOps/code-ci-gate/plan.md"
  - "_docs/qa/DevOps/code-ci-gate/test-plan.md"
  - "_docs/qa/DevOps/code-ci-gate/verification.md"
  - "_docs/standards/quality_assurance.md"
related_issues: []
related_prs: []
---

# Intent: Code CI gate for backend and frontend

## Context

本リポジトリは docs 側に `Docs CI`（markdownlint + `check-docs.sh`）を持ち、全 push / PR で
自動 gate していた。一方でコード側には自動 gate が存在せず、`grep -rn "pytest" .github/ scripts/`
は 0 件だった。release build の 2 workflow は tag push でのみ動き、テストを実行しない。

結果として、`uv run pytest` は `1 failed, 212 passed` の状態で放置されていた。
失敗は `_docs/qa/Core/concurrent-evaluation-jobs/verification.md` に `PARTIAL` として
記録されていたが、赤を報告する仕組みが無いため、次に誰かが手元実行を怠れば気づかれない。

原因を切り分けたところ、`ProviderRateLimiter._timestamps` がクラス変数としてテスト間で
蓄積し、provider id `unknown`（既定 20 req per 60s）の窓を埋めていた。
`tests/test_benchmark_engine.py` 単独実行でも再現したため、ファイル間漏れではなく
ファイル内蓄積と確定した。テストは遅かったのではなく、実際にレート待ちしていた。

## Decisions

### DEC-001: コード CI を新設し、gate 対象を release build と同じコマンド一式にする

- **What**: `Code CI` workflow を追加し、push（main / dev）と PR（main）で
  backend test と frontend lint / test / build を実行する。
- **Why**: リファクタは「振る舞いを変えずに構造を変える」作業であり、振る舞いが変わっていないことを
  機械的に確認する手段が無ければ、保守性の問題を正当性の問題に変換してしまう。
  docs だけを gate している状態は、検証の重心がコードから離れていることを意味する。
- **Change freedom**: trigger branch、job 分割、concurrency 設定、runner は変更できる。
  「push / PR でコードの自動 gate が存在する」ことを保つ限り、構成は変えてよい。
- **Why not**: pre-commit hook だけでは、hook 未導入の環境や `--no-verify` を素通りする。
  gate は共有された場所に置く必要がある。

### DEC-002: テスト間のプロセス共有状態リセットは conftest へ集約し、本番シングルトンは変えない

- **What**: `tests/conftest.py` の autouse fixture で `ProviderRateLimiter`・
  `ActiveRunRegistry`・`RateLimitStore.FILE_PATH` を各テストの前後に既定へ戻す。
  `core` 側の classmethod シングルトン設計そのものは変更しない。
- **Why**: 本アプリは `launcher.py` と `packaging/` が示す通りローカル単一プロセスの
  デスクトップアプリであり、プロセス内シングルトンは設計として妥当である。
  問題はシングルトンではなく、テストプロセスに全テストが同居する場合の分離シームが無いことだった。
  正当な設計を不安だけで作り替えると、長期的な安定性はむしろ下がる。
- **Change freedom**: リセット対象の追加、fixture の scope、リセット実装（`reset_for_tests` か
  個別代入か）は変更できる。将来インスタンス注入へ移行する場合も、
  「テストが共有状態を持ち越さない」ことを保てばよい。
- **Why not**: `core` 全体を脱シングルトン化する案は、151 箇所の classmethod を巻き込む大改修に
  なる一方、解決するのはテスト分離という限定的な問題でしかない。費用と影響が釣り合わない。
- **Revisit when**: サーバを複数 worker / 複数プロセスで動かす要件が出た時。
  その時はシングルトン前提そのものを再検討する。

### DEC-003: frontend node test のランナーを `tsx` に固定する

- **What**: `tsx` を devDependency として固定し、`npm run test --prefix frontend` を正典の
  実行手段にする。個別ファイルを `npx tsx --test` で列挙する運用をやめる。
- **Why**: 13 個の node test に実行 entrypoint が無く、QA doc 内の手動コマンドとしてのみ存在していた。
  単一 script にしないと CI へ載せられず、テストの存在が実質的に任意参加になる。
- **Change freedom**: ランナー（`tsx` / bundler ベースの test runner 等）と glob は変更できる。
  「全 node test が単一コマンドで実行される」ことを保てばよい。
- **Why not**: native `node --test` は依存を増やさないが、2 ファイルが読み込み失敗する。
  原因はテストではなく本番ソースの拡張子なし相対 import であり、実測で本番ソース 26 箇所すべてが
  拡張子なし・`.ts` 付きは 0 件だった。これは bundler 前提の標準規約であって誤りではない。
  規約側を全書き換えする案は、変更範囲が広い上に、それを強制する lint rule が無いため
  次の拡張子なし import で再び壊れる。

### DEC-004: backend を Python 3.12 / 3.14 の matrix で gate する

- **What**: release build が使う 3.12 と、`.python-version` が指す開発版 3.14 の両方でテストする。
- **Why**: 出荷物は 3.12 でビルドされ、開発は 3.14 で行われている。片方だけを gate すると、
  「手元では通るが出荷版で落ちる」か「出荷版は通るが開発を止める」のどちらかを見逃す。
- **Change freedom**: 対象バージョンは、出荷版と開発版が一致すれば単一化してよい。
- **Revisit when**: `.python-version` と release build のバージョンが揃った時。

### DEC-005: `PARTIAL` は未確認だけを表し、赤い suite で `PASS` を出さない

- **What**: `quality_assurance.md` に baseline suite 節を追加し、full suite に失敗が残る状態で
  verdict を `PASS` にしないこと、既知の失敗として先へ進む場合は TODO へ起票して ID を
  verification に記載することを規範化する。
- **Why**: 落ちているテストは「未確認項目」ではなく「再現済みの既知欠陥」である。両者を同じ verdict へ
  畳むと、suite が二値の信号として機能しなくなり、以後「この赤は既知か新規退行か」を毎回人間が
  判定することになる。テストスイートはこの経路で死ぬ。
- **Change freedom**: 節の配置、対象コマンドの列挙方法は変更できる。
- **Why not**: validator で機械強制する案は、verification 本文と suite 実行結果を CI が突き合わせる
  必要があり、実行環境差で誤検知しやすい。まず規範として置き、review と skill で担保する。

## Consequences / Impact

- push / PR ごとに backend（2 versions）と frontend の job が動く。実行時間は backend が約 1.2s、
  frontend が lint + test + build で数十秒程度。
- `tests/conftest.py` は全 backend テストに適用される。本番コードの挙動は変更しない。
- `frontend/package.json` に `tsx` が加わる。build 成果物には載らない dev 依存である。
- 既存 verification（`_docs/qa/Core/concurrent-evaluation-jobs/verification.md`）が
  `PARTIAL` の根拠にしていた失敗は解消済みだが、当該文書は当時の記録として書き換えない。

## Quality Implications

- CI が緑であることが、以後のリファクタにおける behavior-preservation の根拠になる。
- gate 対象コマンドと `quality_assurance.md` の baseline suite 節、`AGENTS.md` の
  コマンド一覧が乖離すると、規範が実態を指さなくなる。三者は同時に更新する。
- conftest のリセット対象を増やしすぎると、テストが自前で管理する状態を壊しうる。
  漏れの証拠があるものだけを対象にする。

## Intent-derived Invariants

- INV-001 (from DEC-005): full suite に失敗が残る状態の verification verdict を `PASS` にしない。

## Enforced in (optional)

- `.github/workflows/code-ci.yml` — DEC-001 / DEC-004
- `tests/conftest.py` — DEC-002
- `frontend/package.json` の `test` script — DEC-003
- `_docs/standards/quality_assurance.md` の baseline suite 節 — DEC-005 / INV-001

## Rollback / Follow-ups

- Rollback: `code-ci.yml` を削除すれば gate は消え、他の変更は独立して残る。
  `tests/conftest.py` の削除は順序依存を再発させるため、単独では戻さない。
- Follow-up: Node のローカル版（24）と CI / release 版（22）の差は未 gate である。
- Follow-up: `npm audit` が報告する dev 依存の既知脆弱性は本判断の対象外とした。
