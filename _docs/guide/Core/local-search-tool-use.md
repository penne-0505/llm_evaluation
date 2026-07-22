---
title: Local Search Tool-Use
status: active
draft_status: n/a
created_at: 2026-04-07
updated_at: 2026-06-03
references:
  - "_docs/intent/Core/legacy-documentation-retirement/decision.md"
  - "_docs/archives/plan/Core/legacy-documentation-retirement/local-search-tool-use-runtime.md"
related_issues: []
related_prs: []
---

## Overview
- `task08` では、モデルプロバイダ固有の web 検索機能ではなく、アプリ内部の local search runtime を使って tool-use を評価する。
- runtime は外部 HTTP endpoint ではなく、評価実行中に `BenchmarkEngine` の内部で動く。

## How It Works
- task ごとの tool 利用設定は `task_configs/<task_id>.json` に置く。
- 現在は `task_configs/08.json` が `task08` に対して `web_search` と `fetch_webpage` を有効化している。
- 検索結果と本文は `task_fixtures/08.json` に保存する。
  - `query_snapshots`: 検索結果一覧
  - `documents`: URL ごとの本文抜粋
- 被験モデルが `<tool_call>...</tool_call>` を返すと、engine 内部の runtime が fixture を参照して結果を返す。
- 被験モデルが `max_steps` 到達後も tool call を続けた場合、runtime は追加 tool を実行せず、収集済みの `tool_trace` を根拠に tool なしの最終回答を 1 回だけ生成させる。
- judge prompt には `tool_trace` の compact summary が含まれる。summary には `tool_call_count`、`tool_step_count`、成功/失敗数、各 call の tool 名・引数・結果概要を含め、judge が根拠利用や過剰/不足な探索を評価できるようにする。

## Scope
- runtime 自体は task 非依存の共通実装。
- どの task で有効にするかは `task_configs/<task_id>.json` で切り替える。
- 現時点で local search runtime を使うのは `task08` のみ。

## Files
- `task_configs/08.json`: `task08` の tool 利用設定
- `task_fixtures/08.json`: `task08` の検索結果と本文コーパス
- `core/tool_runtime.py`: local search runtime 本体
- `core/benchmark_engine.py`: subject 側 tool loop の実行

## Notes
- `task08` が外部検索 API を直接呼ぶことはない。
- FastAPI に検索用 endpoint を追加しているわけでもない。
- 新しい task で使う場合は、対応する `task_configs/<task_id>.json` と `task_fixtures/<task_id>.json` を追加する。
