---
title: "QA Verification: Judge system prompt and rubric reliability"
status: active
draft_status: n/a
qa_schema: 2
qa_status: verified
risk: Medium
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/Core/judge-rubric-reliability/decision.md"
  - "_docs/plan/Core/judge-rubric-reliability/plan.md"
  - "_docs/qa/Core/judge-rubric-reliability/test-plan.md"
  - "_docs/reference/Core/judge-prompt-contract/reference.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# QA Verification: Judge system prompt and rubric reliability

## Summary

bundled judge system prompt、11 個の per-task rubric、holistic style rubric、judge user prompt の
trust boundary を更新した。提供された recent raw evaluation session も確認し、rubric にない CF ID の
生成、任意例 omission の減点、tool trace による空回答の補完、完遂性欠陥の holistic 再計上を
明示的に禁止した。task 08 では no-change oracle と慎重な non-claim を近接する高得点域へ置く
非対称評価を追加した。backend regression と prompt contract tests は成功した。

取り込み先の標準環境で backend 全体、公式 documentation validator、Markdown lint を再実行し、
すべて成功した。task 07、08、10 の主要な採点者向け事実情報は CDC / ATSDR、OpenAI、NATO の
一次資料とも照合した。

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
uv run --with pytest pytest -q
uv run --with pytest pytest -q tests/test_prompt_contracts.py
DD_SCOPE_PATHS='<changed docs>' deno run ... <docs validators>
deno run --allow-read scripts/validate-todo.mjs
npx --yes markdownlint-cli2 <changed markdown paths>
git diff --check
```

Result:

```text
prompt contract suite: 8 passed, 23 subtests passed
backend full suite: 90 passed, 23 subtests passed
official documentation validators: PASS
markdownlint-cli2: PASS (20 files, 0 issues)
git diff --check: PASS
```

外部 judge / subject API は呼び出していない。テストは取り込み先の uv 環境で一時 shim なしに実行した。

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `tests/test_prompt_contracts.py` | PASS | metadata、weights、CF exact-ID、empty final answer、optional-example neutrality、holistic exclusion を検証 |
| `tests/test_benchmark_engine.py` | PASS | trusted rubric の先行配置、untrusted block、tool trace envelope を検証 |
| backend full pytest | PASS | 90 tests、23 subtests |
| official docs validators | PASS | frontmatter、references、Intent、QA、TODO contract |
| official Markdown lint | PASS | 変更対象20ファイル、0 issues |
| `git diff --check` | PASS | whitespace error なし |

## Empirical Session Review

| Observed behavior | Prompt / rubric response |
| --- | --- |
| rubric に存在しない `CF-3` が一 run だけ生成された | system で新規 CF ID の作成を禁止し、task 07 で timing / fictional staging だけでは CF にならないと明記 |
| task 01 の限定的 MOC / link 利用まで旧 CF が失格扱いした | CF を「全既存ノートの継続的再整理を中心策にし、負担削減がない場合」へ限定 |
| task 08 は検索 trace がある一方、final answer が空だった | trace は final answer を補完せず、空回答は 0 点・CF false と deterministic に定義 |
| task 10 で Ismay quote の omission が減点された | quote を使わないことは中立と rubric に明記 |
| holistic が空回答・途中切れを読みやすさで再度減点した | availability / completion defect の欠落自体を holistic から除外 |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | operational system prompt と static contract test |
| AC-002 | PASS | 12 rubrics の metadata / weights / sections test |
| AC-003 | PASS | answer-key-specific requirement scan と全 rubric manual review |
| AC-004 | PASS | task 02、07、08、09、10 の calibrated factual notes と static assertions |
| AC-005 | PASS | envelope order / escaping integration tests |
| AC-006 | PASS | holistic rubric / prompt に completion defect exclusion と proportional scoring を明記 |
| AC-007 | PASS | backend、Deno validators、markdownlint、diff check がすべて成功 |
| AC-008 | PASS | empirical failure-mode assertions in `tests/test_prompt_contracts.py` |
| AC-009 | PASS | task 08 の no-change oracle、near-full non-claim、false-positive penalty を contract test で確認 |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | common procedure は system、task-specific facts / anchors は rubric に分離 |
| DEC-002 | PASS | CF は exact ID、central evidence、task-destroying failure に限定 |
| DEC-003 | PASS | exact phrase / product / scholar requirements を除き、equivalent alternatives を許容 |
| DEC-004 | PASS | rubric first、all subject-originated data untrusted、tag marker escaping |
| DEC-005 | PASS | three-axis weights と JSON key contract を維持し、duplicate penalty を禁止 |
| DEC-006 | PASS | visible final answer only、empty answer deterministic rule、trace non-substitution |
| DEC-007 | PASS | holistic excludes completion / availability defects and lowers confidence for small samples |
| DEC-008 | PASS | task 08 は慎重な確認不能を高得点に保ち、oracle 一致との差より false positive との差を大きくした |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | prompt builder order and marker escaping tests |
| INV-002 | PASS | 12 rubric weight sums and output-key assertions |
| INV-003 | PASS | system prompt requires all-zero score when CF true |
| INV-004 | PASS | empty final answer and trace non-substitution assertions |
| INV-005 | PASS | holistic completion-defect exclusion assertions |
| INV-006 | PASS | task 08 asymmetric scoring order assertions |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| original task intent alignment | PASS | all 11 prompts and rubrics reviewed pairwise |
| no answer-key overfitting | PASS | task 04 / 05 / 10 additional alternative routes made explicit |
| factual calibration | PASS | direct evidence limits and public-evidence limits separated from proof of absence |
| CF proportionality | PASS | task 01 / 07 narrowed; no undefined CF IDs in bundled rubrics |
| holistic no-double-count | PASS | empty / truncated completion defect explicitly excluded |
| parser / aggregator compatibility | PASS | JSON schema, keys, weights unchanged |
| task 08 epistemic calibration | PASS | 「変更なし」満点域、「確認できない」近接高得点、誤更新断定は低得点 / CF |

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| LIVE-JUDGE-001 | repeat evaluation would require external judge / subject calls | compare old/new judge dispersion on a fixed answer corpus in a separate experiment |
| AGG-CF-001 | aggregate CF quorum / majority logic is outside prompt / rubric scope | consider a separate aggregation decision if a single CF outlier must not invalidate a model-task result |

## Residual Risks

None

## Follow-up TODOs

- Required follow-up はない。固定回答 corpus による judge 分散比較は、外部モデル呼び出しを伴う別実験として扱う。
