---
title: "QA Verification: Holistic run progress"
status: active
draft_status: n/a
qa_schema: 2
qa_status: verified
risk: Medium
created_at: 2026-07-22
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/holistic-run-progress/decision.md"
  - "_docs/qa/Core/holistic-run-progress/test-plan.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# QA Verification: Holistic run progress

## Summary

backend の dedicated `holistic_progress` event と standard-only lane snapshot、frontend の typed
store / RunPage card、request task ID canonicalization を実装した。さらに、holistic task を別 task として
実行しながら progress queue を drain するよう修正した。これにより `running` event は task 完了を待たずに
SSE へ yield され、cancel 時は task を cancel・await する。自動テスト、lint、production build、scoped
docs validation は成功した。加えて、OpenRouter (`google/gemma-3-4b-it`) を被験・judge に使い、
ローカル backend (`127.0.0.1:8765`) 上で `run_holistic=true/false` の live Run UI smoke を実施し、
専用 card の lifecycle と通常 lane 非混在を確認した。

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
uv run --with pytest --with 'fastapi>=0.115.0' python -m pytest tests/test_server_frontend.py
uv run --with pytest pytest -q
npx --prefix frontend tsx --test frontend/src/store/runStore.node.test.ts frontend/src/pages/RunPage.node.test.ts
node --test frontend/src/api/client.node.test.ts frontend/src/store/runStore.node.test.ts frontend/src/lib/executionPresets.node.test.ts frontend/src/store/settingsStore.node.test.ts frontend/src/pages/RunPage.node.test.ts
npm run lint --prefix frontend
npm run build --prefix frontend
DD_SCOPE_PATHS='<changed docs>' deno run ... <docs validators>
git diff --check
```

Result:

```text
backend pytest: 23 PASS
backend full pytest: 82 PASS
frontend node tests: 10 PASS
frontend lint: PASS
frontend production build: PASS
scoped docs validation: PASS
git diff --check: PASS
live Run UI smoke (OpenRouter google/gemma-3-4b-it, task 02): PASS
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `tests/test_server_frontend.py` | PASS | payload / standard-only snapshot に加え、完了前 delivery と cancel / exception cleanup を含む23件 |
| backend full suite | PASS | 82件 |
| `runStore.node.test.ts` | PASS | standard progress と holistic progress の state 分離 |
| `RunPage.node.test.ts` | PASS | canonical order、unknown ID 除外、重複除外 |
| frontend related node suite | PASS | preset order を含む10件 |
| frontend lint / build | PASS | TypeScript、ESLint、Vite production bundle |
| scoped docs validators | PASS | Plan / Intent / QA / reference / TODO contract |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| Run 画面通常状態の interactive smoke | PASS | ローカルアプリを実ブラウザで開き、Run 画面の描画と新規 console error がないことを確認した。 |
| live holistic run (`run_holistic=true`) | PASS | OpenRouter `google/gemma-3-4b-it`（被験・judge 同一）、task `02`、judge runs=1。通常 task 完了後に dedicated 「包括評価」card が表示され、`包括評価 1/1: 実行中` / `0 / 1 タスク処理済み` / `#1 style` を確認。この間の通常 lane は完了1・実行中0・待機中0のまま（`1 / 1+ タスク完了`）。run は評価完了まで到達。 |
| live non-holistic run (`run_holistic=false`) | PASS | 同モデル・同タスク。進行表示は `N / 1 タスク完了`（`+` なし）。実行中から完了まで dedicated card（`section` 内の「包括評価」）は一度も表示されなかった。 |
| UI code review | PASS | dedicated card は `holisticProgress` のみを読み、standard lane の counters を再利用しない。 |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | backend unit test が event の task 完了前 delivery、standard-only snapshot、cancel / exception cleanup を確認。 |
| AC-002 | PASS | typed store test、lint/build、RunPage diff、および live Run UI smoke で専用 card の開始・進行と通常 lane 非混在を確認。 |
| AC-003 | PASS | RunPage node test が canonical order と stale / duplicate ID 除外を確認。 |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | lifecycle event と `task_kind` filtering により、メッセージ文字列からの推測なしで包括評価を通常 lane と分離する。live smoke でも通常 lane 件数が包括評価開始で増えないことを確認。 |
| DEC-002 | PASS | RunPage は loaded `tasks` を filter した `selectedTasks.map(...)` のみを request へ渡す。 |

## Invariant Coverage

None

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| — | — | — |

## Residual Risks

None

## Follow-up TODOs

None
