---
title: "Plan: Holistic run progress"
status: active
draft_status: n/a
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/Core/holistic-run-progress/decision.md"
  - "_docs/qa/Core/holistic-run-progress/test-plan.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# Plan: Holistic run progress

## Overview

`run_holistic=true` の包括評価は、通常タスクの完了後に実行される。しかし現在の SSE
snapshot は包括評価の task state を通常 task state と同じ lane 集計へ追加するため、Run
画面で何が実行中なのかを判断できない。本変更は包括評価の状態を dedicated SSE event と
して表し、通常 lane とは別の小さな進捗表示へ反映する。

同時に、RunPage が送る `selectedTaskIds` を画面に読み込んだ `tasks` の順序から再構築し、
保存された選択状態の順序・重複・古い ID が backend の execution order へ入らないように
する。

## Scope

- backend が包括評価の開始、タスク単位の進行、完了を `holistic_progress` SSE event で送る。
- 通常 task snapshot に `task_kind` を持たせ、通常 task lane の集計対象を明示する。
- frontend の型と Run store に包括評価用 progress state を追加する。
- RunPage に通常 lane と区別した包括評価の状態表示を追加する。
- selected task ID を `selectedTasks.map((task) => task.id)` から送る。
- backend snapshot、Run store、RunPage canonicalization の回帰テストを追加する。
- 包括評価 reference と QA evidence を更新する。

## Non-Goals

- 包括評価の実行順序、judge 呼び出し、結果 JSON schema、採点方式を変えない。
- 包括評価 task を通常の task selection UI へ公開しない。
- 予測所要時間、進捗率の再設計、SSE transport の再接続を導入しない。

## Requirements

- `run_holistic` が有効で実行される時だけ dedicated event を送る。
- dedicated event は `started`、`running`、`completed` を識別し、完了数・総数・active task・
  message を含む。
- 通常 task lane の完了・実行中・待機中件数は包括評価を含めない。
- Run UI は include された task と包括評価の状態を別々の表示で読める。
- request payload の task IDs は読み込まれた `tasks` の順に一意な ID だけを含む。

## Tasks

1. task state に kind を付与し、通常 task snapshot を kind で絞る。
2. 包括評価の lifecycle で `holistic_progress` event を queue へ追加する。
3. frontend types / store / SSE parser に dedicated state を接続する。
4. RunPage の progress board に dedicated status card を置き、送信 IDs を canonicalize する。
5. unit / node test、frontend lint/build、backend test、docs validator を実行する。

## QA Plan

- Risk: Medium。実行状態の表示と request order が対象で、評価 engine の実行意味論は対象外。
- `AC-001` は backend snapshot と event builder の unit test、`AC-002` は Run store test と
  diff review、`AC-003` は RunPage helper の node test で確認する。
- `DEC-001` と `DEC-002` は verification で理由と change freedom に対して review する。

## Deployment / Rollout

- API consumer は bundled frontend のみであり、SSE に additive event を足すため段階 rollout は
  不要である。旧 frontend は未知 event を無視して通常 run を継続できる。
- rollback は dedicated event / UI state を戻すだけでよく、保存済み results や run request の
  永続データ migration はない。
