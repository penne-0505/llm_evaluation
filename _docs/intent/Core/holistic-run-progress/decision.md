---
title: "Intent: Holistic run progress"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-24
references:
  - "_docs/archives/plan/Core/holistic-run-progress/plan.md"
  - "_docs/qa/Core/holistic-run-progress/test-plan.md"
related_issues: []
related_prs: []
---

# Intent: Holistic run progress

## Context

包括評価は通常 task の後に実行する別段階だが、既存の Run progress snapshot は同じ task
collection から lane を構築していた。そのため、通常 task が全件完了した後に表示される
「実行中」や「完了」の対象を、利用者が識別できない。

また、設定 store の `selectedTaskIds` はユーザー状態であり、execution order の正典ではない。
RunPage が読み込んだ `tasks` が画面と backend の両方で共有する canonical order である。

## Decisions

### DEC-001: 包括評価は通常 task snapshot ではなく dedicated lifecycle として送る

- **What**: backend は包括評価の開始・実行中・完了を `holistic_progress` SSE event として
  送り、通常 lane 用 snapshot は standard task だけで構築する。
- **Why**: 実行段階の区別を UI が推測するメッセージ文字列や index に委ねると、通常 task の
  完了数と包括評価の状態が混ざり、利用者が待機対象を判断できない。
- **Change freedom**: dedicated state の名称、event payload の内部表現、UI component の構造は、
  通常 task と包括評価を明示的に区別し、開始・進行・完了を観測できる限り変更できる。
- **Why not**: task ID の prefix や message の文言だけで包括評価を判定しない。それらは resource
  author が変更でき、SSE consumer が意味論を復元する契約として弱い。
- **Revisit when**: 将来 task graph を導入して任意の post-processing phase を共通モデルで表せる
  ようになった時。

### DEC-002: execution task IDs は RunPage の canonical task list から再構築する

- **What**: backend へ送る `selectedTaskIds` は、選択済み `tasks` を画面の順序で filter してから
  map する。
- **Why**: stale な保存状態、重複、選択順の差が execution order に入ると、画面で確認した task
  並びと backend の task index がずれ、進捗表示と結果比較の再現性を損なう。
- **Change freedom**: canonical order の提供者は `tasks` API 以外へ変更できるが、画面で表示する
  task list と request が同じ一意順序を使う必要がある。
- **Why not**: settings store の配列を並べ替えずそのまま送らない。store は selection state の保持先で
  あって execution order の source of truth ではない。

## Consequences / Impact

- SSE event を扱う frontend は additive な `holistic_progress` case を持つ。
- 通常 lane の counters は既存 task object を再利用するが、包括評価の状態は含めない。
- request canonicalization により backend での task order が UI loading order と一致する。

## Quality Implications

- backend event payload と UI store の境界をそれぞれ unit test し、RunPage では order を回帰テスト
  する。

## Intent-derived Invariants

None

## Rollback / Follow-ups

- rollback は dedicated SSE event、store state、RunPage card を同時に戻し、通常 task snapshot の
  `task_kind` filtering を維持する。これにより、UI を戻しても包括評価が通常 lane に混在しない。
- SSE consumer が複数になる場合は、`holistic_progress` payload を shared schema として切り出す
  ことを検討する。
