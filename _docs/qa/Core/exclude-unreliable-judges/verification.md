---
title: "QA Verification: Exclude unreliable judges from aggregate score"
status: active
draft_status: n/a
qa_schema: 2
qa_status: verified
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/exclude-unreliable-judges/decision.md"
  - "_docs/qa/Core/exclude-unreliable-judges/test-plan.md"
  - "_docs/archives/plan/Core/exclude-unreliable-judges/plan.md"
  - "_docs/archives/survey/Core/exclude-unreliable-judges/survey.md"
related_issues: []
related_prs: []
---

# QA Verification: Exclude unreliable judges from aggregate score

## Summary

信頼できない judge 系統を hero スコアから除外する toggle（default OFF）を実装した。
判定・閾値は `core/judge_reliability.py` に集約し、run 保存 JSON に
`exclude_unreliable_judges` と `score_aggregation` を記録する。全除外時は
`average_score` / `best_score` を `null`（N/A）とし 0 を返さない。

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
uv run pytest tests/test_judge_reliability.py tests/test_result_storage.py tests/test_engine.py tests/test_server_frontend.py -q
uv run pytest -q
npx --prefix frontend tsx --test \
  frontend/src/lib/judgeReliability.node.test.ts \
  frontend/src/components/ResultDetail.node.test.ts \
  frontend/src/api/client.node.test.ts \
  frontend/src/lib/executionPresets.node.test.ts \
  frontend/src/lib/timeRoi.node.test.ts
npm run lint --prefix frontend
npm run build --prefix frontend
git diff --check
npx markdownlint-cli2 "_docs/qa/Core/exclude-unreliable-judges/**/*.md" \
  "_docs/archives/plan/Core/exclude-unreliable-judges/**/*.md" \
  "_docs/intent/Core/exclude-unreliable-judges/**/*.md"
```

Result:

```text
targeted backend: 56 PASS
backend full pytest: 151 PASS (+ 23 subtests)
frontend node tests: 28 PASS
frontend lint: PASS
frontend production build: PASS
git diff --check: PASS
markdownlint (Feat-43 docs): 0 issues
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `test_judge_reliability.py` toggle OFF mean | PASS | AC-001 |
| `test_judge_reliability.py` high_variance | PASS | AC-002 / DEC-002 |
| `test_judge_reliability.py` low_confidence / critical_fail | PASS | AC-002 |
| `test_judge_reliability.py` cross_judge_divergence | PASS | AC-002 |
| `test_judge_reliability.py` all excluded null | PASS | AC-004 / INV-001 |
| `test_server_frontend.py` RunRequest default + hero path | PASS | AC-002 / DEC-003 |
| `test_result_storage.py` toggle + null round-trip | PASS | AC-005 / DEC-003 |
| `judgeReliability.node.test.ts` | PASS | AC-002 / INV-002 |
| `ResultDetail.node.test.ts` reasons / N/A / summary | PASS | AC-003 / AC-004 |
| `client.node.test.ts` body + convert null | PASS | AC-001 / AC-005 |
| `executionPresets.node.test.ts` legacy default false | PASS | AC-001 |
| frontend lint / build | PASS | |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| toggle OFF で既存 run の hero が変わらない | PASS（unit） | OFF は全 judge mean、legacy 空は 0 |
| toggle ON で flags 付き系統が横断サマリーから消える | PASS（unit） | `computeJudgeSummaries` が excluded を落とす |
| 除外理由・前後スコア表示 | PASS（unit） | ResultDetail ExclusionSummaryCard + node test |
| 全除外で N/A + 警告 | PASS（unit） | null hero + `allExcluded` 警告 |
| 保存 toggle 再表示一貫 | PASS（unit） | JSON round-trip / convert |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | RunPage toggle default OFF; OFF aggregation = all-judge mean |
| AC-002 | PASS | four reason codes exclude lineages from average/best + summaries |
| AC-003 | PASS | ExclusionSummaryCard + reason label mapper |
| AC-004 | PASS | null scores + allExcluded warning; never silent 0 under ON |
| AC-005 | PASS | `exclude_unreliable_judges` + `score_aggregation` persisted and remapped |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | lineage-wide exclusion after any task×judge flag |
| DEC-002 | PASS | thresholds/codes only in `core/judge_reliability.py` |
| DEC-003 | PASS | RunRequest field default false; saved on result JSON |
| DEC-004 | PASS | all excluded → null |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | exclude-ON + empty included set → null hero（0 非返却） |
| INV-002 | PASS | frontend maps reason codes only; exclusion thresholds stay backend-owned |

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| live multi-judge run 目視 | fixtures で 4 理由コードと N/A を検証。live smoke 未実施 | 任意 |
| Dashboard の null-only モデル行 | null hero は集計から除外しつつ runCount は残す | UX 調整が必要なら別 TODO |

## Residual Risks

None

## Follow-up TODOs

None

## Completion Decision

- TODO `Core-Feat-43` は Verification PASS。エントリ削除は parent に委ねる。
