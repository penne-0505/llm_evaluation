---
title: "Survey: Holistic bundled_responses context overflow"
status: archived
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/plan/Core/holistic-context-overflow/plan.md"
  - "_docs/intent/Core/holistic-context-overflow/decision.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# Survey: Holistic bundled_responses context overflow

## Background

包括評価は通常タスク完了後、`server.py` が `non_creative_responses`（creative 除外済み
completed task の dict 一覧）を `BenchmarkEngine.run_holistic_task` へ渡す。
engine 内で `_build_bundled_responses` が各 task の `task_name`、`task_type`、`input_prompt`、
`response` を固定テンプレートで連結し、`_run_judge_evaluation` の `subject_response` となる。

judge user prompt は `_build_judge_user_prompt` により、trusted rubric、holistic eval prompt、
`untrusted_subject_answer`（bundled テキスト）、envelope 説明で構成される。holistic では
tool trace は通常空である。

現行コードに入力サイズ上限チェックは存在しない。

## Objective

- bundled 入力組み立て経路と judge prompt への載せ方を特定する。
- コンテキスト超過リスク要因（タスク数、response 長、固定 overhead）を整理する。
- adapter / 設定に context window 情報があるか確認する。
- v1 overflow 処理（truncation vs split）の実装前提を Plan / Intent へ渡す。

## Method

- 静的コード読解: `core/benchmark_engine.py`（`_build_bundled_responses`、`run_holistic_task`、
  `_build_judge_user_prompt`）、`server.py`（holistic 実行ブロック、`non_creative_responses`
  構築）。
- 参照: `_docs/reference/Core/holistic-evaluation.md`（judge プロンプト構造、creative 除外）。
- adapter 層 grep: `context_window`、`max_input`、token budget 関連 API の有無。
- 既存 test grep: `holistic`、`bundled` 関連 fixture の有無。

## Results

### 入力組み立て経路

```text
server.py
  non_creative_responses = [{task_name, task_type, input_prompt, response}, ...]
  engine.run_holistic_task(..., bundled_responses=non_creative_responses)
    bundled_subject_response = _build_bundled_responses(bundled_responses)
    _run_judge_evaluation(subject_response=bundled_subject_response, input_prompt=eval_prompt, ...)
      _build_judge_user_prompt(..., subject_response, rubric_content)
```

`_build_bundled_responses` は各 item を次形式で連結する:

```text
### タスク: {id}（{type}）

#### 入力プロンプト
{input}

#### 被験LLMの回答
{response}
```

区切りは `\n\n---\n\n`。

### サイズ要因

| 成分 | 来源 | 備考 |
| --- | --- | --- |
| system prompt | bundled `judge_system_prompt.md` | holistic / standard 共通 |
| rubric | `rubrics/holistic/*.md` | trusted block |
| eval prompt | `prompts/holistic/*.md` | untrusted original prompt |
| bundled answers | 全 non-creative task | 最大可変部 |
| envelope | 固定説明文 + タグ | 数十〜数百 chars |

タスク数 N、平均 response 長 L により bundled 部分はおおよそ O(N × L) で増える。

### Context window 情報

- `adapters/base.py` および各 adapter に input context 上限を返す共通メソッドは無い。
- `max_tokens` は completion 出力上限であり、入力 window ではない。
- OpenRouter adapter は `supported_parameters` 等を扱うが、run 時の window 解決は未実装。

### テスト現状

- `tests/test_server_frontend.py` に holistic progress / snapshot 分離テストあり。
- `_build_bundled_responses` の overflow 専用 unit test は未確認。
- `tests/test_benchmark_engine.py` に engine stub adapter あり（holistic overflow 拡張の土台）。

### 失敗モード

- 超過時は provider が context length exceeded を返し、`_evaluate_judge` が
  `{"runs": [], "aggregated": None, "error": str(e)}` を記録する。
- run 自体は継続するが、holistic スコアが欠落し、truncation したかどうかは結果から読めない。

## Discussion

- split 評価は chunk ごとに judge を呼び、aggregated score を合成する必要があり、
  `ResultAggregator` 契約への影響が大きい。TODO も score 集約を follow-up Intent に委ねている。
- v1 truncation は engine 内で完結し、API schema 変更が最小。
- budget 見積もりは tokenizer 未導入のため文字数 heuristic が現実的。保守的 default
  （例: 128k token 相当を chars/4 で近似）と per-model override map の併用が妥当。
- DEC-007（holistic は完遂性欠陥を再採点しない）と整合するため、truncation で落とすのは
  「証拠量調整」であり、per-task availability スコアの二重計上ではない。

## Recommended Actions

1. Plan / Intent どおり、固定 overhead 差引 + 末尾 task 優先 truncation を v1 として実装する。
2. `bundling_metadata` を holistic `TaskResult` に additive 追加する。
3. `tests/test_benchmark_engine.py` に oversized / normal fixture を追加する。
4. `_docs/reference/Core/holistic-evaluation.md` に overflow メタデータ節を追記する。
5. adapter context window API は Non-Goal とし、必要になった時点で別 survey を行う。
