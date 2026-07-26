---
title: "QA Verification: Concurrent evaluation jobs with provider rate limits"
status: active
draft_status: n/a
qa_schema: 2
qa_status: partial
risk: High
created_at: 2026-07-24
updated_at: 2026-07-26
references:
  - "_docs/plan/Core/concurrent-evaluation-jobs/plan.md"
  - "_docs/intent/Core/concurrent-evaluation-jobs/decision.md"
  - "_docs/qa/Core/concurrent-evaluation-jobs/test-plan.md"
related_issues: []
related_prs: []
---

# QA Verification: Concurrent evaluation jobs with provider rate limits

## Summary

評価ジョブの同時実行（上限 3）、プロバイダ共有レート制限、Settings 編集、Run 画面の
ジョブ縦積みに加え、2026-07-26 に active SSE の所有を `RunPage` から app shell の
`Layout` coordinator へ移した。内部 route の child component が unmount されても接続 registry
は保持され、terminal event または app shell teardown でのみ解放される。

自動回帰は PASS。fake SSE では実行中表示まで確認したが、Browser セッションが route 操作時に
失われたため Run → Settings → Run の画面往復確認は未完了であり、総合判定は PARTIAL とする。

## Verification Verdict

Verdict: PARTIAL

## Commands Run

```bash
uv run pytest
uv run pytest tests/test_benchmark_engine.py::TestBenchmarkEngine::test_no_fixed_sleep_between_successful_runs -q
uv run pytest tests/test_concurrent_jobs.py tests/test_server_frontend.py -q
npx --yes tsx@4.20.6 --test $(find src -name '*.node.test.ts' -print | sort)
npm run lint --prefix frontend -- --max-warnings=0
npm run build --prefix frontend
./scripts/check-docs.sh
git diff --check
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| full backend `uv run pytest` | PARTIAL | 212 PASS / 1 FAIL。`ProviderRateLimiter` の共有状態に依存する既存の順序依存 test |
| failing backend test isolated | PASS | `test_no_fixed_sleep_between_successful_runs`: 1 PASS |
| concurrent/server frontend tests | PASS | 52 PASS |
| frontend node tests | PASS | 66 PASS。INV-004 lifecycle 2件、cancel retry回帰1件を含む |
| frontend lint | PASS | warning 0 |
| frontend build | PASS | TypeScript + Vite production build |
| docs validator | PASS | 既存の Core-Bug-48 warning 1件のみ |
| `git diff --check` | PASS | whitespace errorなし |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| fake SSE で active progress を表示 | PASS | fake progress が更新される実行中画面を確認 |
| Run → Settings → Run の進捗継続 | BLOCKED | route 操作時に in-app Browser の tab が消失し、再試行では kernel timeout |
| 設定違い 2〜3 ジョブ縦積み | DEFERRED | 実 provider の費用を伴うため未実行 |
| 個別キャンセルで他ジョブ継続 | DEFERRED | 実 SSE Manual QA 未実行 |
| 4 本目拒否（UI + API） | PARTIAL | API / registry auto PASS、UI Manual QA未実行 |
| 1 ジョブ進行ボード回帰 | PARTIAL | node / build PASS、live操作未実行 |

## Review Results

`cheap-second-opinion` で route lifecycle、cancel、stale job、connection cleanup を独立レビューした。

- 有効: cancel API 失敗時に `cancelRequested` が残り、再試行不能になる指摘。失敗時にrunning状態を
  保ったまま要求フラグを戻し、エラー表示と再試行を可能にした。回帰test PASS。
- 不成立: `jobs` 内部更新でeffectが再実行されない指摘。`patchJob` は新しい配列を返す。
- 不成立: child route 遷移で `Layout` cleanupが走る指摘。`Layout` は親route elementであり、
  `/run` と `/settings` の切替では保持される。

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS (auto) / PARTIAL (live) | registry上限 + API 409 |
| AC-002 | PASS (code + store) / PARTIAL (live) | JobPanel縦積み、job-scoped cancel |
| AC-003 | PASS | ProviderRateLimiter unit |
| AC-004 | PASS | store + API + Settings |
| AC-005 | PASS (auto) / PARTIAL (live) | frontend node / build |
| AC-006 | PASS (code + node) / PARTIAL (Browser) | app-shell registry regression PASS、route往復はBrowser障害で未完了 |

## Decision Conformance

| DEC | Result | Notes |
| --- | --- | --- |
| DEC-001 | PASS | MAX_CONCURRENT=3、server 409 |
| DEC-002 | PASS | ジョブ縦積みとjob-scoped操作 |
| DEC-003 | PASS | provider_id共有 acquire |
| DEC-004 | PASS | Settings + 推奨default |
| DEC-005 | PASS | limiter待ちcancel unit。cancel API failureも再試行可能 |
| DEC-006 | PASS (implementation) / PARTIAL (Browser) | LayoutがSSE lifecycleを所有。画面往復のlive evidence未完了 |

## Invariant Coverage

| INV | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | registry ≤ 3 |
| INV-002 | PASS | subject/native/judgeで acquire |
| INV-003 | PASS | unknown / builtin default |
| INV-004 | PASS (node) / PARTIAL (Browser) | active connection保持・terminal cleanup・shell teardown abortを回帰testで確認 |

## Deferred / Not Covered

- Browser上の Run → Settings → Run 往復と復帰後のprogress表示。
- 実providerを使う設定違い2〜3ジョブ並列、個別cancel、1ジョブ操作感。

## Residual Risks

- Browser上での Run → Settings → Run 往復と復帰後の更新値表示を確認できていない。
- 実providerによる設定違い2〜3ジョブ並列、個別cancel、1ジョブ操作感は未確認。
- full backend suiteは順序依存1件でnon-green。ただし単独実行と今回の関連backend 52件はPASS。

## Follow-up TODOs

- `Core-Feat-66` Step 7: Browserが利用可能な状態でroute往復と実API複数job Manual QAを実行する。
