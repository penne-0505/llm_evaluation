---
title: "QA Test Plan: Holistic run progress"
status: active
draft_status: n/a
qa_schema: 2
qa_status: planned
risk: Medium
created_at: 2026-07-22
updated_at: 2026-07-24
references:
  - "_docs/archives/plan/Core/holistic-run-progress/plan.md"
  - "_docs/intent/Core/holistic-run-progress/decision.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Holistic run progress

## Source of Intent

- `_docs/intent/Core/holistic-run-progress/decision.md`

## Decision Review Scope

- `DEC-001`: dedicated lifecycle が通常 task lane と混在しないこと。
- `DEC-002`: request task IDs が画面 canonical order と同じこと。

## Quality Goal

包括評価の実行中に、Run 画面が通常 task の進捗を誤って増減させず、包括評価の開始・進行・
完了を明確に表示する。backend が受け取る selected task IDs は UI 上の task 順序と一致する。

## Acceptance Criteria

- AC-001: backend は包括評価の lifecycle を dedicated SSE event で送信し、通常 task snapshot の
  lane 集計から包括 task を除外する。
- AC-002: frontend は dedicated event を store に反映し、RunPage で通常 lane と別表示にする。
- AC-003: RunPage request の task IDs は selected task の canonical order・一意集合である。

## Intent-derived Invariants

None

## Risk Assessment

- Medium: SSE の payload / parser / Zustand state の不一致は、run 自体は継続しても進捗を誤表示する。
- Medium: selected task order の誤りは progress index と結果の表示順をずらす。
- Out of scope の evaluation engine や provider 呼び出しを mock し直さず、純粋な event / state / request
  boundary を直接確認する。

## Test Strategy

- Python unit test で standard/holistic mixed state の snapshot、holistic event payload、task 完了前の
  event delivery、および cancellation / exception 後に task が残らないことを確認する。
- Node test で Zustand store が lifecycle event 由来の update を保持できることを確認する。
- Node test で RunPage の selected-task helper が canonical order、重複除去、未知 ID 除外を確認する。
- frontend lint/build と docs validator で型、render、documentation contract を確認する。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | dedicated lifecycle と standard lane separation | unit | `uv run --with pytest --with fastapi python -m pytest tests/test_server_frontend.py` | holistic event が task 完了前に delivery され、snapshot は standard-only。cancel / exception 後に pending task なし | verified |
| AC-002 | TODO | SSE event を typed store state と dedicated UI へ接続 | node unit + review | `npx --prefix frontend tsx --test frontend/src/store/runStore.node.test.ts`、RunPage diff | store lifecycle state と通常 lane から独立した status card | verified |
| AC-003 | TODO | canonical task ID request ordering | node unit | `npx --prefix frontend tsx --test frontend/src/pages/RunPage.node.test.ts` | canonical list order、unknown/duplicate の除外 | verified |
| AC-001--003 | TODO | type and integration regression | lint/build | `npm run lint --prefix frontend` / `npm run build --prefix frontend` | typecheck、lint、Vite build success | verified |

## Manual QA Checklist

- [x] `run_holistic=true` で通常 task の完了後に dedicated 「包括評価」表示が開始する。
- [x] 包括 task の進行中、通常 lane の完了・実行中・待機中件数が変わらない。
- [x] 包括評価完了時に total と completed が一致し、最後のメッセージが読める。
- [x] `run_holistic=false` では dedicated card が表示されない。

## Regression Checklist

- [x] standard-only run の SSE progress と lane 表示が従来どおりである。
- [ ] cancel / error event が既存 status 遷移を維持する。
- [x] strict mode でも canonical task ID list が backend request に渡る。

## Out of Scope

- judge 呼び出しの並列性、including result score、provider API の live smoke。
- 包括評価 resource のロード失敗時における retry UI。

## Open Questions

None。
