---
title: "QA Verification: Concurrent evaluation jobs with provider rate limits"
status: active
draft_status: n/a
qa_schema: 2
qa_status: partial
risk: High
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/plan/Core/concurrent-evaluation-jobs/plan.md"
  - "_docs/intent/Core/concurrent-evaluation-jobs/decision.md"
  - "_docs/qa/Core/concurrent-evaluation-jobs/test-plan.md"
related_issues: []
related_prs: []
---

# QA Verification: Concurrent evaluation jobs with provider rate limits

## Summary

評価ジョブの同時実行（上限 3）、プロバイダ共有レート制限（Settings 編集可・推奨デフォルト）、
Run 画面のジョブ縦積みを実装した。自動テストは PASS。実 API を使った 2〜3 本並列の
Manual QA は deferred。

## Verification Verdict

Verdict: PARTIAL

## Commands Run

```bash
uv run pytest tests/test_concurrent_jobs.py -q
uv run pytest tests/test_benchmark_engine.py -q -k 'subject or rate or concurrent or clamp'
npx --prefix frontend tsx --test frontend/src/store/runStore.node.test.ts
npx --prefix frontend tsx --test frontend/src/pages/RunPage.node.test.ts
npm run lint --prefix frontend -- --max-warnings=0
npm run build --prefix frontend
./scripts/check-docs.sh
```

Result:

```text
test_concurrent_jobs.py: 7 PASS
test_benchmark_engine.py (filtered): 24 PASS
runStore.node.test.ts: 3 PASS
RunPage.node.test.ts: 1 PASS
frontend lint / build: PASS
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `TestActiveRunRegistry` | PASS | AC-001 / INV-001 |
| `TestRateLimitStore` | PASS | AC-004 / INV-003 |
| `TestProviderRateLimiter` | PASS | AC-003 / DEC-005 cancel |
| `TestRateLimitAndActiveApis` | PASS | GET/PUT/reset + 409 |
| `runStore` MAX_CONCURRENT | PASS | AC-001 / AC-002 store |
| frontend lint / build | PASS | |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| 設定違い 2〜3 ジョブ縦積み | DEFERRED | 実 SSE / API 依存 |
| 個別キャンセルで他ジョブ継続 | DEFERRED | 実 SSE 依存 |
| 4 本目拒否（UI + API） | PARTIAL | API 409 unit PASS、UI はコードレビュー |
| Settings で窓を厳しく／緩く | DEFERRED | 体感確認未実施 |
| 1 ジョブ進行ボード回帰 | PARTIAL | JobPanel＝旧ボード相当（code review） |

## High-risk Checklist

- [x] rollback: registry / limiter / multi-job UI / Settings 永続を外すと単一ジョブ体験に戻る
- [x] recovery: 4 本目拒否やレート待ち後も、既存ジョブのキャンセル・完了・再起動ができる（unit + code）
- [x] data safety: 結果 JSON / run_id 衝突は既存と同程度。制限設定に secret を混ぜない
- [x] security: `rate_limits.json` は非 secret。API キー経路と分離

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS (auto) / PARTIAL (live) | registry + 409 |
| AC-002 | PASS (code + store) / PARTIAL (live) | JobPanel 縦積み |
| AC-003 | PASS | ProviderRateLimiter unit |
| AC-004 | PASS | store + API + Settings |
| AC-005 | PASS (review) / PARTIAL (live) | 1 ジョブ JobPanel |

## Decision Conformance

| DEC | Result | Notes |
| --- | --- | --- |
| DEC-001 | PASS | MAX_CONCURRENT=3、サーバ 409 |
| DEC-002 | PASS | ジョブ縦積み |
| DEC-003 | PASS | provider_id 共有 acquire |
| DEC-004 | PASS | Settings + 推奨デフォルト |
| DEC-005 | PASS | cancel 中断 unit |

## Invariant Coverage

| INV | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | registry ≤ 3 |
| INV-002 | PASS | subject/native/judge で acquire |
| INV-003 | PASS | unknown / builtin 既定 |

## Recommended defaults (初版実値)

| provider | max_requests | window_seconds |
| --- | --- | --- |
| openrouter | 30 | 60 |
| openai | 60 | 60 |
| anthropic | 40 | 60 |
| google-ai-studio | 30 | 60 |
| lmstudio | 120 | 60 |
| unknown | 20 | 60 |

## Deferred / Not Covered

- 実プロバイダでの 2〜3 ジョブ並列 Manual QA
- Settings 変更の体感確認
- 1 ジョブ操作感のライブ回帰

## Residual Risks

- 推奨デフォルトが契約プランとずれる場合がある（Settings で調整可能）。
- `run_id` の秒精度衝突は既存リスクのまま。

## Follow-up TODOs

- None（Manual QA は verification deferred として記録）
