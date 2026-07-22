---
title: 包括評価（Holistic Evaluation）
status: active
draft_status: n/a
created_at: 2026-04-17
updated_at: 2026-04-17
references: []
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

通常タスクのルーブリックと**同一フォーマット**を使用します。`task_type` 行は省略可能です（`holistic` として扱われます）。

```markdown
## タスク: 文体・言語運用評価
## task_type: holistic
## weights: logic_and_fact=40, constraint_adherence=30, helpfulness_and_creativity=30

## Critical Fail Conditions（禁忌回答）

| ID | 条件 |
|----|------|
| CF-1 | 日本語として明らかに不自然な文が複数回含まれている |

---

## 評価ルーブリック

### 1. Logic & Fact（0〜40点）
...（語の選択の適切さ、表現の正確さを評価）

### 2. Constraint Adherence（0〜30点）
...（文体一貫性の維持を評価）

### 3. Helpfulness & Creativity（0〜30点）
...（読みやすさ・簡潔さ・自然な日本語表現を評価）
```

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

judge に渡される user_prompt は以下の構造になります。

```markdown
## 入力プロンプト（被験LLMに渡したもの）
{prompts/holistic/style.md の内容}

## 被験LLMの回答
### タスク: 01（fact）

#### 入力プロンプト
{タスク01の入力}

#### 被験LLMの回答
{タスク01の出力}

---

### タスク: 02（speculative）
...

## タスク固有ルーブリック
{rubrics/holistic/style.md の内容}
```

---

## 結果 JSON 構造

`benchmark_result` の最上位に `holistic_tasks` キーが追加されます。各要素の構造は通常タスクと同じです。

```json
{
  "run_id": "...",
  "tasks": [...],
  "holistic_tasks": [
    {
      "task_name": "style",
      "task_type": "holistic",
      "input_prompt": "この評価では...",
      "response": "",
      "judge_results": {
        "claude-sonnet-4-6": {
          "runs": [...],
          "aggregated": { "total_score_mean": 78.3, ... }
        }
      }
    }
  ]
}
```

- `response` は常に空文字（被験 LLM を呼び出さないため）
- `subject_usage` は `null`
- `average_score` / `best_score` の算出には**含まれません**

---

## UI 表示

結果詳細画面に「包括評価」セクションが通常タスクセクションの直後に表示されます。タスクバッジは `包括` ラベルで区別されます。通常タスクの横断サマリー（judge 別平均スコア）には包括評価タスクは含まれません。

---

## Notes

- 包括評価タスクはタスク選択 UI に表示されません。ファイルが存在する場合は常に自動実行されます。
- holistic ルーブリックの軸最大値は bundled `rubrics/holistic/style.md` の配点に合わせ、UI 上は Logic & Fact 40 点、Constraint Adherence 30 点、Helpfulness & Creativity 30 点としてレンダリングされます。
- 包括評価タスクがキャンセルされた場合、それまでに完了した通常タスクの結果は保存されます。
