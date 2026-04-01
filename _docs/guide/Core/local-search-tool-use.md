---
title: Local Search Tool-Use
status: active
draft_status: n/a
created_at: 2026-04-07
updated_at: 2026-04-07
references:
  - ../../plan/Core/local-search-tool-use-runtime.md
related_issues: []
related_prs: []
---

## Overview
- `task08` では、モデルプロバイダ固有の web 検索機能ではなく、アプリ内部の local search runtime を使って tool-use を評価する。
- runtime は外部 HTTP endpoint ではなく、評価実行中に `BenchmarkEngine` の内部で動く。

## How It Works
- task ごとの tool 利用設定は `task_configs/<task_id>.json` に置く。
- 現在は `task_configs/08.json` が `task08` に対して `web-search` と `open-document` を有効化している。
- 検索結果と本文は `task_fixtures/08.json` に保存する。
  - `query_snapshots`: 検索結果一覧
  - `documents`: URL ごとの本文抜粋
- 被験モデルが `<tool_call>...</tool_call>` を返すと、engine 内部の runtime が fixture を参照して結果を返す。

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
