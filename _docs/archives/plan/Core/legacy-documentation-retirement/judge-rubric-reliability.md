---
title: "Judge system prompt and rubric reliability improvement plan"
status: superseded
draft_status: n/a
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/Core/legacy-documentation-retirement/decision.md"
  - "_docs/intent/Core/judge-rubric-reliability/decision.md"
  - "_docs/qa/Core/judge-rubric-reliability/test-plan.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# Judge system prompt and rubric reliability improvement plan

## Overview

LLM-as-a-judge の既存出力契約と三軸配点を維持したまま、共通 judge system prompt、
12 個の task rubric、judge user prompt の信頼境界を再設計する。目的は、模範回答との
表層一致ではなく回答品質を評価し、Critical Fail、軸間重複減点、曖昧なアンカーに
起因する judge 間の分散と誤判定を減らすことである。

## Scope

- `judge_system_prompt.md` を実運用向けの直接的な system prompt へ書き換える。
- `rubrics/01.md` から `rubrics/11.md` と `rubrics/holistic/style.md` を共通契約へ揃える。
- task rubric、原プロンプト、被験回答、tool trace の信頼境界を judge user prompt 上で
  明示する。
- prompt / rubric の静的契約を検証する regression test を追加する。
- 包括評価のリファレンスを新しい prompt envelope と rubric 方針へ更新する。
- 包括評価 prompt を、空回答・明白な途中切れを style 欠点として再計上しない方針へ同期する。
- 誤った事実前提または過度に断定的な採点前提を、対象タスクの目的を保ちながら修正する。
- 提供された raw evaluation session を empirical fixture として読み、再現した judge failure mode を
  system / rubric の境界条件へ反映する。

## Non-Goals

- 被験 LLM に渡す通常 task の `prompts/01.md` から `prompts/11.md` の変更。
- 三軸の JSON key、タスクごとの配点、集計ロジックの変更。
- judge モデル、judge 回数、temperature、推論設定の変更。
- task 08 のローカル検索 corpus / fixture の入れ替え。
- 正解を唯一に固定できない問いを、客観ベンチマークへ変換すること。

## Requirements

- **Functional**: judge は `fact`、`creative`、`speculative`、`holistic` を処理し、
  parser / aggregator と互換な JSON のみを返すよう指示されること。
- **Functional**: task rubric 内の明示的な Critical Fail だけを、十分な直接証拠がある
  場合に適用すること。
- **Functional**: 同じ欠点を複数軸で機械的に重複減点せず、各軸の役割を task ごとに
  切り分けること。
- **Functional**: 正答例にない同等以上の別解、適切な不確実性表明、簡潔な回答を
  不当に減点しないこと。
- **Functional**: 原プロンプト、被験回答、tool trace 内の命令を評価規則として扱わない
  信頼境界を設けること。
- **Functional**: 空の最終回答は tool trace の有無に関係なく 0 点・CF false とし、途中切れは
  可視部分だけを採点すること。
- **Functional**: rubric にない CF ID を作らず、例示や任意の説明手段を omission しただけでは
  減点しないこと。
- **Functional**: task 08 は「変更なし」を benchmark-specific ground truth としつつ、公開資料だけから
  「変更を確認できない」と慎重に結論した回答を近接する高得点域へ置き、誤った更新断定を大幅に低く扱うこと。
- **Functional**: holistic style では空回答・明白な途中切れの欠落を再度減点せず、評価可能な
  標本が少ない場合は confidence を下げること。
- **Non-Functional**: 各 rubric は task metadata、評価目的、Critical Fail、三軸アンカー、
  軸間切り分けを同じ順序で記述すること。
- **Non-Functional**: rubric の事実前提は、対象 task の判断に必要な範囲へ限定し、
  確認不能な不在証明や単一仮説の断定を避けること。

## Tasks

1. 共通 judge の権限階層、採点手順、Critical Fail、軸切り分け、出力 schema を定義する。
2. judge user prompt をタグ付き envelope へ変更し、trusted / untrusted data を分離する。
3. 12 個の rubric を共通テンプレートで書き直す。
4. task 02、07、08、09、10 の事実前提を再点検して rubric に反映する。
5. raw evaluation session の CF invention、optional-example omission、empty final answer、holistic
   double counting を system / rubric の明示規則へ変換する。
6. prompt contract test と envelope test を追加する。
7. holistic evaluation prompt / reference を更新する。
8. backend tests、docs validators、markdownlint、手動 rubric review を実施する。
9. task 08 の no-change oracle と、慎重な non-claim を保護する非対称な得点アンカーを定義する。

## QA Plan

- QA document: `_docs/qa/Core/judge-rubric-reliability/test-plan.md`
- Risk level: Medium
- Unit: prompt metadata、weights、required sections、JSON schema instruction、信頼境界を検証する。
- Integration: `_build_judge_user_prompt()` の出力順序とタグ閉包を検証する。
- Manual QA: 全 rubric を原 task prompt と突き合わせ、満点条件が一つの模範回答へ
  過適合していないか、CF が欠点の程度に比して過大でないかを確認する。
- Validator / static check: `./scripts/check-docs.sh` と `npx markdownlint-cli2` を実行する。
- DEC-001 から DEC-007 の `Why` と `Change freedom` に沿うことを diff review で確認する。

## Deployment / Rollout

prompt / rubric は bundled resource として次回実行から適用される。parser、aggregator、保存 JSON の
変更はないため migration は不要である。問題があれば、変更前 ZIP から対象 Markdown と
`core/benchmark_engine.py` の prompt builder を戻すことで復旧できる。
