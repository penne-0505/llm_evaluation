---
title: "QA Verification: Exclude unreliable judges from aggregate score"
status: active
draft_status: n/a
qa_schema: 2
qa_status: partial
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
`exclude_unreliable_judges` と `score_aggregation`（`excluded_judges` /
`unreliable_candidates` 含む）を記録する。全除外時は
`average_score` / `best_score` を `null`（N/A）とし 0 を返さない。
backend / frontend の自動テストは成功。live multi-judge 目視 Manual QA は未実施。

Core-Bug-52: `computeReviewFlags` が `cross_judge_divergence` を出さず除外理由と要確認
flags がずれていた問題を修正し、DEC-001 の追跡一致を front 側でも満たす。

## Verification Verdict

Verdict: PARTIAL

## Commands Run

```bash
uv run pytest tests/test_judge_reliability.py tests/test_result_storage.py \
  tests/test_server_frontend.py -q
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
targeted backend（judge_reliability / result_storage / server_frontend）: PASS
backend full pytest: 151 PASS (+ 23 subtests)
frontend node tests: 28 PASS
frontend lint: PASS
frontend production build: PASS
git diff --check: PASS
markdownlint (Feat-43 docs): 0 issues
```

注: `tests/test_engine.py` は本機能の対象外（incomplete score 除外など別契約）。Commands から除外した。

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
| `client.node.test.ts` body + convert null | PASS | AC-001（body default）/ AC-005。RunPage 専用 node なし |
| `executionPresets.node.test.ts` legacy default false | PASS | AC-001 |
| frontend lint / build | PASS | |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| toggle OFF で既存 run の hero が変わらない | PASS（unit） | `test_toggle_off_matches_all_judge_mean`。live 再確認は DEFERRED |
| toggle ON で flags 付き系統が横断サマリーから消える | PASS（unit） | `computeJudgeSummaries` node test。live 目視は DEFERRED |
| 除外理由・前後スコア表示 | PASS（unit） | ResultDetail ExclusionSummaryCard + node test。live レイアウトは DEFERRED |
| 全除外で N/A + 警告 | PASS（unit） | null hero + `allExcluded`。live 警告色は DEFERRED |
| 保存 toggle 再表示一貫 | PASS（unit） | JSON round-trip / convert |
| live multi-judge run で Manual Checklist 一式 | DEFERRED | fixtures で代替。外部モデル依存の目視未実施 |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PARTIAL | OFF aggregation = all-judge mean（unit）。request body default は `client.node.test`。RunPage toggle UI は code review（`RunPage.node.test.ts` に exclude カバレッジなし） |
| AC-002 | PASS | four reason codes exclude lineages from average/best + summaries |
| AC-003 | PASS | ExclusionSummaryCard + reason label mapper（node） |
| AC-004 | PASS | null scores + allExcluded warning; never silent 0 under ON |
| AC-005 | PASS | `exclude_unreliable_judges` + `score_aggregation`（candidates 含む）persisted and remapped |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | lineage-wide exclusion after any task×judge flag。Core-Bug-52 で `computeReviewFlags` も `cross_judge_divergence` を同一参加者に出す |
| DEC-002 | PASS | exclusion thresholds/codes in `core/judge_reliability.py`; frontend mirrors range/SD for review flags only |
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
| live multi-judge run 目視 | fixtures で 4 理由コードと N/A を検証。live smoke 未実施 | 任意（運用時 Manual Checklist） |
| RunPage exclude toggle node test | `RunPage.node.test.ts` は task 順序のみ。toggle は body 契約で代替 | 必要なら RunPage node 追加 |
| Dashboard の null-only モデル行 | null hero は集計から除外しつつ runCount は残す | UX 調整が必要なら別 TODO |

## Residual Risks

- live Manual QA 未実施のため、実 API multi-judge での除外理由文言・N/A 警告の視覚確認が残る。
- RunPage toggle 操作そのものの自動テストが無く、UI 回帰は Settings/preset/body 契約と lint/build に依存する。
- Dashboard で null hero のみのモデル行が残る表示は、比較 UX として紛らわしい可能性がある（集計ロジック自体は Intent どおり）。

## Follow-up TODOs

- 任意: live multi-judge 1 run で Manual Checklist（toggle ON/OFF・除外理由・全除外 N/A）を目視する。
- 任意: `RunPage.node.test.ts` に exclude toggle default OFF / ON → body 反映を追加すると AC-001 UI が閉じる。
- Dashboard null-only 行の扱いが問題なら別 TODO で UX 調整する。

## Completion Decision

- TODO `Core-Feat-43` 実装核は Intent 整合。Verification は live Manual / RunPage node 欠落により PARTIAL。
  エントリ削除は parent に委ねる（Docs-57 で証跡を正直化した）。

## Core-Bug-52 follow-up (2026-07-23)

`computeReviewFlags` が `cross_judge_divergence` を出さず、除外理由と要確認 flags がずれる回帰を修正。
`taskHasCrossJudgeDivergence` と閾値定数を `judgeReliability.ts` に置き、乖離 task の参加 judge 全員へ
`formatReliabilityReason('cross_judge_divergence')` を付与する（DEC-001）。

### Bug AC Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | range > 15 で両 judge に review flag |
| AC-002 | PASS | DEC-001: flags 警告対象と除外理由コードが一致 |
| AC-003 | PASS | `judgeReliability.node.test.ts` / `ResultDetail.node.test.ts` が理由コードを固定 |

### Commands Run (Bug-52)

```bash
npx --prefix frontend tsx --test \
  frontend/src/lib/judgeReliability.node.test.ts \
  frontend/src/components/ResultDetail.node.test.ts
```

Result: 11 PASS / 0 fail

### Decision Conformance (Bug-52)

| ID | Result | Notes |
| --- | --- | --- |
| DEC-001 | PASS | 乖離 task の参加 judge 全員が review flag と除外候補の両方で追跡可能 |

Verdict (Bug-52 scope): PASS
