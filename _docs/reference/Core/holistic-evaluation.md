---
title: 包括評価（Holistic Evaluation）
status: active
draft_status: n/a
created_at: 2026-04-17
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/holistic-run-progress/decision.md"
  - "_docs/intent/Core/holistic-context-overflow/decision.md"
  - "_docs/intent/Core/holistic-judge-model/decision.md"
  - "_docs/intent/Core/judge-rubric-reliability/decision.md"
  - "_docs/reference/Core/judge-prompt-contract/reference.md"
  - "_docs/qa/Core/judge-rubric-reliability/verification.md"
related_issues: []
related_prs: []
---

## Overview

包括評価（Holistic Evaluation）は、全タスクの出力が揃った後にトリガーされる、横断的な文体・言語運用評価の仕組みです。

通常の per-task 評価が「タスクの回答内容（事実性・論理性・制約遵守）」を評価するのに対し、包括評価は**被験モデルの応答全体から文体の一貫性・語の選択・言語運用の質**を評価します。被験 LLM を再度呼び出すことはなく、既に収集済みの出力を束ねて judge に渡します。

### 通常タスクとの主な違い

| 項目 | 通常タスク | 包括評価タスク |
|---|---|---|
| 被験 LLM 呼び出し | あり | **なし** |
| judge への入力 | 単一タスクの入出力ペア | 全タスク出力の束 |
| 実行タイミング | タスクごと（並列） | 全通常タスク完了後（直列） |
| タスク一覧 UI への表示 | あり（選択可） | **なし**（自動実行） |
| 結果 JSON のキー | `tasks` | `holistic_tasks` |
| `average_score` への算入 | あり | **なし** |

---

## ファイル配置

包括評価タスクは、専用ディレクトリに **ルーブリック** と **評価プロンプト** の2ファイルを置くことで定義します。ファイル名（stem）が一致していればタスクとして認識されます。

```text
rubrics/
└── holistic/
    └── style.md          ← ルーブリック（採点基準）

prompts/
└── holistic/
    └── style.md          ← 評価プロンプト（観点の説明）
```

複数の包括評価タスクを定義する場合は、ファイルを増やすだけです（例: `style.md`, `coherence.md` など）。

### ユーザー上書きディレクトリ

bundled ファイルをオーバーライドしたい場合は、アプリのデータディレクトリ以下に同様の構造を置きます。

```text
{user_data_dir}/overrides/
├── rubrics/holistic/style.md
└── prompts/holistic/style.md
```

環境変数 `LLM_BENCHMARK_HOLISTIC_RUBRICS_DIR` / `LLM_BENCHMARK_HOLISTIC_PROMPTS_DIR` でディレクトリを直接指定することもできます。

---

## ファイル形式

### 評価プロンプト (`prompts/holistic/*.md`)

judge に「何を評価するか」を伝えるテキストです。内容は自由ですが、以下の情報を含めることを推奨します。

- 評価の目的（例：文体の一貫性、語の選択の適切さ）
- 評価対象から除外してほしい観点（例：事実性はこのタスクでは問わない）
- 特に注目してほしい言語的特徴

```markdown
この評価では、被験モデルが複数のタスクにわたって示した文体・語の選択・言語運用の質を評価してください。

注目してほしい観点:
- 日本語として自然かどうか（過剰な硬さ、冗長な修飾の回避）
- 語の選択の適切さ（文脈に合った単語・表現を選べているか）
- 文体の一貫性（回答間でトーンが統一されているか）
- 読みやすさ（段落構成、接続詞の使い方）

事実の正確さや課題への論理的対応は、別タスクで評価済みのため、本評価では問いません。
```

### ルーブリック (`rubrics/holistic/*.md`)

通常タスクと同じ metadata / 三軸 contract を使用し、`task_type: holistic` を明記します。
詳細な authoring contract は `_docs/reference/Core/judge-prompt-contract/reference.md` を参照してください。

```markdown
## タスク: 文体・言語運用評価
## task_type: holistic
## weights: logic_and_fact=40, constraint_adherence=30, helpfulness_and_creativity=30

## 評価目的

複数出力に見られる語義・語用、register、読みやすさの傾向を評価する。
個別 task の内容正誤は再評価しない。

## Critical Fail Conditions

なし。文体上の欠点は頻度と影響に応じて比例的に採点する。

## 評価ルーブリック

### 1. Logic & Fact（0〜40点）
...（語義・語用・意味制御の正確さ）

### 2. Constraint Adherence（0〜30点）
...（task に応じた register と不要な文体揺れ）

### 3. Helpfulness & Creativity（0〜30点）
...（文構造・冗長性・自然な日本語）

## 軸間の切り分け

同じ欠点を、意味、register、読みやすさの異なる影響なしに重複減点しない。
```

holistic style では、翻訳調、語義誤用、冗長性も通常の得点差として扱います。単発の問題や
少数の outlier を理由に全軸 0 点へする Critical Fail は定義しません。出力数が少なく横断傾向を
判断しにくい場合は、点数を機械的に下げず judge の `confidence` を下げます。

空回答、provider / API failure、出力上限による明白な途中切れは、per-task の可用性・完遂性欠陥であり、
holistic style の文体傾向ではありません。その欠落自体を holistic score へ再計上しません。途中までに
実際に現れた文章は語用・register・文構造の証拠にできますが、「終わっていないこと」は除外します。
評価可能な文章が一つもなければ三軸 0・Critical Fail false とし、少数だけなら score ではなく
`confidence` で標本不足を表します。

---

## 実行フロー

```text
1. 通常タスクを全件並列実行（既存フロー）
2. ↓ 全完了を待機
3. creative タイプのタスクを除外したレスポンスを収集
4. 各包括評価タスクを順次実行
   - 被験 LLM 呼び出しなし
   - 収集済み出力を束ねて judge へ渡す
   - judge 評価（既存の _run_judge_evaluation を再利用）
5. 結果を benchmark_result.holistic_tasks に追加して保存
```

### creative タスク除外について

`task_type: creative` のタスクは、文体評価において「創作的な逸脱」が意図的に含まれるため、包括評価の入力から自動的に除外されます。

---

## judge へのプロンプト構造

judge user prompt は、trusted rubric を先に置き、包括評価 prompt と bundled responses を
untrusted evidence として囲みます。block 内に同名タグが現れた場合は escape されます。

```text
<trusted_task_rubric>
{rubrics/holistic/style.md の内容}
</trusted_task_rubric>

<untrusted_original_prompt>
{prompts/holistic/style.md の内容}
</untrusted_original_prompt>

<untrusted_subject_answer>
### タスク: 01（fact）

#### 入力プロンプト
{タスク01の入力}

#### 被験LLMの回答
{タスク01の出力}

---

### タスク: 02（speculative）
...
</untrusted_subject_answer>
```

この順序と trust boundary は通常 task と共通です。`untrusted_subject_answer` 内の命令文、
system prompt らしい記述、外側タグの模倣は judge への命令として扱いません。

---

## 結果 JSON 構造

`benchmark_result` の最上位に `holistic_tasks` キーが追加されます。各要素の構造は通常タスクと同じです。

```json
{
  "run_id": "...",
  "judge_models": ["openrouter/anthropic/claude-sonnet-5"],
  "holistic_judge_models": ["openrouter/google/gemini-2.5-pro"],
  "tasks": [...],
  "holistic_tasks": [
    {
      "task_name": "style",
      "task_type": "holistic",
      "input_prompt": "この評価では...",
      "subject_prompt": "",
      "response": "",
      "judge_results": {
        "openrouter/google/gemini-2.5-pro": {
          "runs": [...],
          "aggregated": { "total_score_mean": 78.3, ... }
        }
      },
      "bundling_metadata": {
        "truncated": false,
        "action": "none",
        "dropped_tasks": [],
        "estimated_chars_before": 1200,
        "estimated_chars_after": 1200,
        "estimated_tokens_before": 300,
        "estimated_tokens_after": 300,
        "answer_budget_chars": 100000,
        "context_limit_tokens": 32768,
        "overhead_chars": 8000,
        "binding_model": "openrouter/google/gemini-2.5-pro"
      }
    }
  ]
}
```

- `judge_models` は通常タスク（per-task）の judge 一覧
- `holistic_judge_models` は包括評価で実際に使った judge 一覧（Core-Feat-46）。未実行時は空配列。
  リクエストで未指定の場合は `judge_models` へ fallback し、保存時はその実効一覧を記録する
- `response` は常に空文字（被験 LLM を呼び出さないため）
- `subject_prompt` は常に空文字（被験 LLM を呼び出さないため。Core-Bug-36）
- `subject_usage` は `null`
- `average_score` / `best_score` の算出には**含まれません**
- `bundling_metadata` は包括評価専用の additive フィールド（通常 task には付かない）

### bundled_responses の context overflow（Core-Enhance-35）

judge 呼び出し前に、system prompt・rubric・eval prompt・trust envelope・出力予約・安全マージンを
差し引いた残りを `untrusted_subject_answer`（bundled subject answers）の文字予算とする。
見積もりは v1 では文字数ベース（おおよそ 4 文字 ≈ 1 token）であり、モデル window が未解決の場合は
保守的なデフォルト（32,768 token）を使う。複数 judge がある場合は、利用可能なモデルのうち
最も厳しい上限を採用する。

予算超過時の v1 処理は**単一 judge 呼び出し内の切り詰めのみ**（分割評価・chunk 間スコア集約なし）:

1. bundled 内の**末尾 task**から順に完全除外する（`action: "task_drop"`）
2. 残 task が 1 件でも収まらない場合のみ、その task の `#### 被験LLMの回答` 本文を末尾から
   文字 truncate し、見出しと入力プロンプトは維持する（`action: "response_truncate"`）

overflow 処理の有無は `bundling_metadata` で追跡する:

| フィールド | 意味 |
| --- | --- |
| `truncated` | 切り詰め / task drop が発生したか。発生時は必ず `true` |
| `action` | `none` / `task_drop` / `response_truncate` |
| `dropped_tasks` | 除外した task_name の一覧（末尾から除外した順） |
| `estimated_chars_*` / `estimated_tokens_*` | 処理前後の推定サイズ |
| `answer_budget_chars` | bundled answer に割り当てた文字上限 |
| `context_limit_tokens` | 採用した judge context 上限 |
| `overhead_chars` | 固定 overhead（system + envelope 等）の文字見積もり |
| `binding_model` | 上限解決に使った judge モデル名 |

通常規模の入力では `_build_bundled_responses` の出力形式（`### タスク:` 見出し、`---` 区切り）は
変更されない。切り詰め発生時は engine ログにも warning を残す。

---

## UI 表示

結果詳細画面に「包括評価」セクションが通常タスクセクションの直後に表示されます。タスクバッジは `包括` ラベルで区別されます。通常タスクの横断サマリー（judge 別平均スコア）には包括評価タスクは含まれません。包括評価で通常 judge と異なるモデルを使った場合は、概要の「包括評価モデル」と包括評価セクション見出しにそのモデル名が表示されます。

設定画面の包括評価セクションでは、通常の評価モデルとは別に包括評価モデルを任意選択できます。未選択時は通常の評価モデルと同じセットを使います（後方互換）。Strict Mode は per-task `judge_models` のみを固定し、包括評価モデルの選択は strict 違反にしません。

### Run 画面の進捗

包括評価を有効にした run では、通常タスク完了後に backend が `holistic_progress` SSE event を
送信します。event の `status` は `started`、`running`、`completed` であり、成功・失敗・総 task
件数、現在の task ID と message を含みます。holistic task の実行中も queue を drain するため、
`running` は task 完了後ではなく実行中に届きます。Run 画面はこの event を通常 task lane と別の
「包括評価」card に表示します。

通常 task の SSE snapshot は `task_kind: "standard"` を持ち、包括評価内部の task state は
`task_kind: "holistic"` として区別されます。lane の完了・実行中・待機中件数は standard task の
みを集計するため、包括評価の開始で通常 task の完了件数が増えたようには表示されません。

---

## Notes

- judge system prompt、rubric metadata、trust envelope の正典は `_docs/reference/Core/judge-prompt-contract/reference.md` です。
- 包括評価タスクはタスク選択 UI に表示されません。ファイルが存在する場合は常に自動実行されます。
- holistic ルーブリックの軸最大値は bundled `rubrics/holistic/style.md` の配点に合わせ、UI 上は Logic & Fact 40 点、Constraint Adherence 30 点、Helpfulness & Creativity 30 点としてレンダリングされます。
- 包括評価タスクがキャンセルされた場合、それまでに完了した通常タスクの結果は保存されます。
- bundled_responses の context overflow 契約は本ドキュメントの「bundled_responses の context overflow」節と `_docs/intent/Core/holistic-context-overflow/decision.md` を正典とする。
