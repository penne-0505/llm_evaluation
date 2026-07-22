---
title: "Judge prompt and rubric contract"
status: active
draft_status: n/a
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/Core/judge-rubric-reliability/decision.md"
  - "_docs/qa/Core/judge-rubric-reliability/test-plan.md"
  - "_docs/qa/Core/judge-rubric-reliability/verification.md"
  - "../../../../judge_system_prompt.md"
related_issues: []
related_prs: []
---

# Judge prompt and rubric contract

## Overview

judge prompt は、全 task 共通の採点手順を持つ `judge_system_prompt.md` と、task 固有の判断基準を持つ
`rubrics/**/*.md` の二層で構成する。被験回答との表層一致ではなく、原プロンプトの目的を満たす
回答品質を採点し、既存の三軸 JSON contract と互換な結果を返す。

## Responsibility boundary

### System prompt

`judge_system_prompt.md` は次を定義する。

- system、trusted rubric、untrusted evidence の権限順序。
- task metadata と fallback weights。
- Critical Fail の適用条件。
- 空回答、途中切れ、tool trace の扱い。
- 三軸の一般的な意味と重複減点防止。
- fact / code、creative / speculative、holistic の追加規則。
- JSON-only output schema と整合性確認。

### Task rubric

各 rubric は次を定義する。

- task name、`task_type`、三軸 weights。
- 評価目的と、必要な場合の採点者向け事実情報。
- task 成立を失わせる明示的な Critical Fail。
- 三軸ごとの評価観点と得点帯アンカー。
- 同じ欠点を複数軸で重複評価しないための切り分け。

一般手順を rubric ごとに複製せず、task 固有でない規則は system prompt へ置く。

## Judge user prompt envelope

`BenchmarkEngine._build_judge_user_prompt()` は次の順序で judge user prompt を組み立てる。

```text
<trusted_task_rubric>
...
</trusted_task_rubric>

<untrusted_original_prompt>
...
</untrusted_original_prompt>

<untrusted_subject_answer>
...
</untrusted_subject_answer>

<untrusted_tool_trace>
...
</untrusted_tool_trace>
```

`untrusted_tool_trace` は tool 利用がある場合だけ付く。untrusted block 内に外側タグと同じ文字列が
現れた場合は HTML entity へ escape し、評価対象の文字列で外側境界を閉じられないようにする。

原プロンプト、被験回答、tool trace はすべて evidence であり、judge への命令ではない。
tool trace は根拠確認の補助に使うが、呼び出し回数を直接点数化せず、最終回答にない source 表示を
trace だけから補完しない。

## Visible final answer contract

- `<untrusted_subject_answer>` が空文字または空白だけなら、三軸と `total_score` は 0、
  `critical_fail` は false とする。回答不在を ID 付き CF とする rubric だけが例外である。
- tool trace に検索結果や根拠があっても、空の final answer を補完しない。
- 明白な途中切れは可視部分だけを採点し、未出力の続きは推測しない。途中切れ自体は rubric に
  明記されない限り CF ではない。
- holistic style では、空回答、API failure、明白な途中切れの欠落自体を再度減点しない。可視部分に
  実際に現れた語用・register・文構造だけを証拠にする。

## Rubric metadata

各 bundled rubric は先頭に次の三行を持つ。

```markdown
## タスク: <表示名>
## task_type: fact | creative | speculative | holistic
## weights: logic_and_fact=<int>, constraint_adherence=<int>, helpfulness_and_creativity=<int>
```

weights は 0 以上の整数で合計 100 とする。bundled rubric の既定配点は次の通り。

| task_type | logic_and_fact | constraint_adherence | helpfulness_and_creativity |
| --- | ---: | ---: | ---: |
| `fact` | 60 | 30 | 10 |
| `creative` | 30 | 30 | 40 |
| `speculative` | 40 | 20 | 40 |
| `holistic` | 40 | 30 | 30 |

## Rubric structure

bundled rubric は次の見出しを使用する。

```markdown
## 評価目的
## 採点者向け事実情報      # 必要な task のみ
## Critical Fail Conditions
## 評価ルーブリック
### 1. Logic & Fact（0〜N点）
### 2. Constraint Adherence（0〜N点）
### 3. Helpfulness & Creativity（0〜N点）
## 軸間の切り分け
```

各軸は `評価観点` と `得点アンカー` を持つ。アンカーは排他的な模範回答ではなく、点数帯を判断する
参照点として書く。固有ツール、固有人物、定型句、結論の言い回しを必須にするのは、それ自体が
原プロンプトの明示要件である場合に限る。

## Critical Fail

Critical Fail は全 score を 0 にするため、次の性質を持つ task-specific failure だけを ID 付きで定義する。

- 回答の中心を壊し、通常の部分点では task 性能を表せない。
- 最終回答から直接確認できる。
- 単なる不足、浅さ、文体、境界事例ではない。
- rubric に存在する ID と条件へ厳密に対応し、新しい CF ID を judge が作らない。

該当条件がない rubric は `なし。` と明記する。holistic style rubric では、文体欠点を頻度と影響に応じて
比例採点し、Critical Fail を使わない。

CF に関係する語や手法が現れるだけでは適用しない。引用、否定、棄却、補助案、適用範囲を狭めた
利用、負担や危険を実質的に除いた変更案は、rubric が明示しない限り中心的な CF 該当策ではない。

## Axis separation

- `logic_and_fact`: 事実、コード、因果、概念、内部整合性。creative では genre / metaphor の整合性、
  holistic では語義・語用の正確さを扱う。
- `constraint_adherence`: 原プロンプトと rubric の明示要件、範囲、形式、安全境界。
- `helpfulness_and_creativity`: 明瞭さ、具体性、実用性、読者適合、創造的価値。

同じ欠点は最も直接対応する一軸で主に減点する。複数軸へ反映する場合は、事実誤り、要件未達、
実行不能など、異なる帰結を reasoning に示す。

rubric の例示、固有名、任意の説明手段は、原プロンプトまたは rubric が必須と明記しない限り
omission を減点しない。judge は語句一致ではなく、回答が果たした機能と可視の欠点で得点帯を選ぶ。

## Output compatibility

judge は次の key を持つ JSON object 一つだけを返す。

- `task_name`
- `task_type`
- `inferred_task_type`
- `weights`
- `score`
- `total_score`
- `reasoning`
- `critical_fail`
- `critical_fail_reason`
- `confidence`

`score` は `logic_and_fact`、`constraint_adherence`、`helpfulness_and_creativity` を持つ。
`total_score` は三軸の厳密な合計である。この key contract は `JudgeResponseParser` と
`ResultAggregator` の既存処理を維持する。

## Verification

- Contract tests: `uv run pytest tests/test_prompt_contracts.py`
- Backend regression: `uv run pytest`
- Documentation validators: `./scripts/check-docs.sh`
- Markdown lint: `npx markdownlint-cli2`
- QA evidence: `_docs/qa/Core/judge-rubric-reliability/verification.md`
