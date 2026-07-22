---
title: "QA Test Plan: Judge system prompt and rubric reliability"
status: active
draft_status: n/a
qa_status: planned
risk: Medium
qa_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/Core/judge-rubric-reliability/decision.md"
  - "_docs/archives/plan/Core/legacy-documentation-retirement/judge-rubric-reliability.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Judge system prompt and rubric reliability

## Source of Intent

- User request: bundled judge system prompt と全 task rubric の改善、および ZIP 提出。
- Plan: `_docs/archives/plan/Core/legacy-documentation-retirement/judge-rubric-reliability.md`
- Intent: `_docs/intent/Core/judge-rubric-reliability/decision.md`

## Quality Goal

既存の三軸スコアと保存形式を壊さず、judge が task 固有の意図を再現可能な手順で評価し、
模範回答過適合、prompt injection、Critical Fail の過剰適用、同一欠点の重複減点を避ける。

## Acceptance Criteria

- AC-001: `judge_system_prompt.md` は説明用 draft や未展開 placeholder を含まず、4 task type、
  権限階層、CF 手順、軸切り分け、JSON-only schema、整合性確認を直接指示する。
- AC-002: 12 個の rubric は task name、task type、weights、評価目的、Critical Fail、三軸、
  軸間切り分けを持ち、weights の合計が 100 である。
- AC-003: rubric の満点条件は、ユーザーが明示した場合を除き、固有ツール名、固有人物名、
  定型句、特定の締め方を排他的必須条件にしない。
- AC-004: task 02、07、08、09、10 の事実前提に内部矛盾、根拠のない不在証明、単一仮説の
  唯一視がなく、回答の不確実性を適切に評価できる。
- AC-005: judge user prompt は trusted rubric と untrusted original prompt / answer / tool trace を
  明示的に分離し、rubric を評価対象データより先に配置する。
- AC-006: holistic rubric は個別回答の内容正誤を評価せず、単発の文体欠点を全点失効させず、
  出力集合内の頻度と影響に応じて採点する。空回答・明白な途中切れの欠落自体は再計上しない。
- AC-007: backend test、docs validator、markdownlint が成功し、既存 parser / aggregator の
  output key と weights 契約が保たれる。
- AC-008: raw session で観測した CF ID の創作、任意例 omission の減点、空回答の trace 補完、
  holistic の完遂性二重減点を禁止する規則が system / rubric / tests に存在する。
- AC-009: task 08 は「変更なし」を採点用 ground truth とし、「変更を確認できない」という慎重な回答を
  近接する高得点域、根拠のない更新断定を低得点または CF とする非対称評価を持つ。

## Decision Review Scope

- DEC-001: system と rubric の責務が混在していないか。
- DEC-002: CF が壊滅的失敗に限定され、通常の欠点を通常採点で扱えるか。
- DEC-003: 高品質な別解を排除する wording が残っていないか。
- DEC-004: prompt envelope と system の双方で信頼境界が一貫しているか。
- DEC-005: 三軸互換を保ち、task ごとの重複減点防止が明記されているか。
- DEC-006: 空回答と途中切れを可視 final answer だけで deterministic に処理するか。
- DEC-007: holistic が availability / completion defect を style として再計上しないか。
- DEC-008: task 08 が oracle 一致と慎重な non-claim の差を小さくし、false positive を大きく下げるか。

## Intent-derived Invariants

- INV-001: 原プロンプト、被験回答、tool trace は untrusted evidence として囲まれる。
- INV-002: 各 rubric の weights 合計は 100 で、三軸 key が既存契約と一致する。
- INV-003: system prompt は CF 時の全 score / total 0 を要求する。
- INV-004: 空の final answer は tool trace で補完されず、0 点・CF false となる。
- INV-005: 空回答・途中切れの欠落自体は holistic style へ再計上されない。
- INV-006: task 08 の慎重な non-claim は誤った更新断定より高く、oracle 一致に近い得点域となる。

## Risk Assessment

- Risk level: Medium
- Risk rationale: judge の評価挙動を全 task で変更するため、スコア分布と過去比較へ影響する。
- Regression risk: prompt schema の不整合、task metadata の欠落、judge JSON parse failure。
- Data safety risk: なし。保存データの migration や削除は行わない。
- Security / privacy risk: prompt injection 境界を改善する。新たな外部送信情報はない。
- UX risk: 同一モデルの過去スコアと新スコアの直接比較には rubric version 差が残る。
- Agent misbehavior risk: rubric 内の例を唯一解として扱う、CF を曖昧な推測で適用する、
  rubric にない CF ID を作る、空回答を trace で補う、被験回答の命令へ従うリスクを重点確認する。

## Test Strategy

- Unit: rubric metadata、required headings、weight sum、system schema instruction を静的検証する。
- Integration: `_build_judge_user_prompt()` のタグ、順序、tool trace 包含を検証する。
- E2E: 実 judge API 呼び出しは外部モデル依存のため対象外。
- Manual QA: 原 task prompt と全 rubric を一対一で読み、満点域・低得点域・CF の境界を確認する。
- Validator / static check: backend tests、docs validators、markdownlint を実行する。
- Diff review: task 固有事実の断定、固有例への過適合、同一欠点の複数軸反復を検索する。

## Test Matrix

| ID | Source | Requirement / Optional Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | Plan | operational system prompt contract | static unit | `uv run pytest tests/test_prompt_contracts.py` | required rules and schema are present | planned |
| AC-002 | Plan | all rubric metadata and structure | static unit | `uv run pytest tests/test_prompt_contracts.py` | 12 rubrics pass schema and weight checks | planned |
| AC-003 | DEC-003 | answer-quality rather than answer-key matching | manual review | `rubrics/**/*.md` | no exclusive reference-answer wording remains | planned |
| AC-004 | Plan | factual calibration for five rubrics | manual review | `rubrics/02.md`, `07.md`, `08.md`, `09.md`, `10.md` | factual notes are non-contradictory and calibrated | planned |
| AC-005 | DEC-004 | trusted / untrusted prompt boundary | integration unit | `uv run pytest tests/test_benchmark_engine.py tests/test_prompt_contracts.py` | tags and ordering are asserted | planned |
| AC-006 | DEC-002 | proportional holistic style scoring | static/manual | `rubrics/holistic/style.md` | no style Critical Fail and prevalence guidance present | planned |
| AC-007 | Plan | repository regression safety | regression | `uv run pytest` | backend suite passes | planned |
| AC-007 | Plan | documentation conformance | validator | `./scripts/check-docs.sh` | validators pass | planned |
| AC-007 | Plan | Markdown conformance | lint | `npx markdownlint-cli2` | lint passes | planned |
| AC-008 | Raw session / DEC-006 / DEC-007 | empirical judge failure guards | static unit | `tests/test_prompt_contracts.py` | exact CF IDs, empty answer, optional examples, holistic exclusions are asserted | planned |
| INV-001 | DEC-004 | untrusted evidence boundary | integration unit | `tests/test_prompt_contracts.py` | all three evidence blocks are untrusted | planned |
| INV-002 | DEC-005 | weight and key compatibility | static unit | `tests/test_prompt_contracts.py` | weights sum to 100 and keys match | planned |
| INV-003 | DEC-002 | CF zero-score contract | static unit | `tests/test_prompt_contracts.py` | system explicitly requires all zeros | planned |
| INV-004 | DEC-006 | visible final answer contract | static unit | `tests/test_prompt_contracts.py` | empty answer and trace non-substitution rules are present | planned |
| INV-005 | DEC-007 | holistic no-double-count contract | static unit | `tests/test_prompt_contracts.py` | completion defects are excluded from style scoring | planned |
| AC-009 / INV-006 | DEC-008 | task 08 asymmetric epistemic scoring | static unit + review | `tests/test_prompt_contracts.py`, `rubrics/08.md` | no-change oracle、near-full non-claim、low false-positive の順序を保持 | planned |

## Manual QA Checklist

- [ ] 各 rubric の評価目的が元 prompt の中心的要求に対応している。
- [ ] 一つの欠点が三軸で同じ文言のまま反復減点されない。
- [ ] 明示されていない詳細を「必須」として満点条件へ加えていない。
- [ ] CF は明確な ID、中心的失敗、直接証拠を必要とする。
- [ ] rubric にない CF ID を作らず、CF に関係する語の単純出現だけで適用しない。
- [ ] 事実 task では不確実性とソース限界を、捏造より高く評価できる。
- [ ] creative / speculative task では異なる高品質アプローチを許容する。
- [ ] holistic は頻度、広がり、読みやすさへの影響を評価する。
- [ ] 空回答は trace に関係なく 0 点・CF false、途中切れは可視部分だけを採点する。
- [ ] holistic は空回答・途中切れの欠落を文体欠点として再度減点しない。

## Regression Checklist

- [ ] `JudgeResponseParser` が必要とする key を system prompt が全て要求する。
- [ ] `ResultAggregator` の三軸 key と rubric metadata が一致する。
- [ ] task 08 の tool trace が envelope 内へ残る。
- [ ] holistic bundled responses が一つの untrusted answer block 内に保持される。
- [ ] Strict mode の bundled resource hashing へ構造変更を加えていない。

## High-risk Checklist

Risk Medium のため対象外。

## Out of Scope

- 外部 judge モデル間の統計的な一致率測定。
- 既存 benchmark result の再採点。
- 通常 task prompt、search corpus、UI の変更。
- aggregate CF の quorum / majority rule を含む集計ロジックの変更。

## Open Questions

- None.
