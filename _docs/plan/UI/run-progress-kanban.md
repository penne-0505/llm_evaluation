---
title: Run Progress Kanban UI
status: active
draft_status: n/a
created_at: 2026-04-04
updated_at: 2026-04-04
references: []
related_issues: []
related_prs: []
---

## Overview
- 評価実行中の進捗表示を、単一の進捗セクションから kanban 風の 3 列レイアウトへ変更する。
- タスクの状態遷移を `Queued / Running / Completed` の列移動として可視化し、並列実行時の現在位置を把握しやすくする。

## Scope
- Run 画面の `running` 状態 UI を再設計する。
- 進捗 snapshot に completed task の一覧を追加する。
- queued / running / completed の各列で同一カード表示を利用する。
- 実行中インジケーターと経過時間表示を、Run 画面外でも状態把握できる形に整える。

## Non-Goals
- 評価エンジンの並列数やスケジューリング挙動そのものの変更。
- 実行完了後の Results / Dashboard 画面のレイアウト変更。

## Requirements
- **Functional**:
  - 実行中タスクは `Running` 列、未着手タスクは `Queued` 列、完了済みタスクは `Completed` 列に表示する。
  - 各列のカードは同系統の見た目を維持し、phase に応じてバッジとパイプライン状態だけ変化させる。
  - 上部サマリーとして completed / running / queued / elapsed は継続表示する。
  - Subject の応答完了もパイプライン上で完了色として判読できること。
  - 各 kanban 列は一定高さを維持し、タスク過多時は列内部のみスクロールすること。
  - Run 画面以外でも、進行中であることを示す簡易 progress を表示すること。
  - モバイルでは列を縦積みし、狭い画面でも内容が読めること。
- **Non-Functional**:
  - 並列実行数が 3 前後のときに、現在位置と残タスク量が一目で分かること。
  - SSE payload 追加は既存の進捗イベント構造を大きく壊さないこと。
  - 経過時間表示は SSE 更新間隔に依存せず、ユーザーからリアルタイムに見えること。

## Tasks
- `server.py` の progress snapshot に `completed_tasks` を追加する。
- フロントの `RunProgress` 型、store、SSE 正規化を更新する。
- Run 画面を 3 列の kanban ボードへ再設計する。
- Subject 完了色、固定高さ列、リアルタイム elapsed、グローバル run indicator を追加する。
- 進捗 snapshot の completed task 追加について回帰テストを加える。

## Test Plan
- 実行中の progress snapshot に completed task が含まれることを unit test で確認する。
- `npm run build` で型崩れや UI コンパイルエラーがないことを確認する。
- 実行時に queued / running / completed の 3 列へタスクが遷移することを目視確認する。

## Deployment / Rollout
- 通常のフロントエンド更新として配布する。
- 既存 SSE クライアントと同時に更新し、旧フロントキャッシュが残る環境では再読み込みを案内する。
