---
title: "Survey: Subject multi-run judge batch evaluation"
status: archived
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "TODO.md"
  - "_docs/reference/Core/holistic-evaluation.md"
  - "_docs/archives/plan/Core/subject-multi-run-judge-batch/plan.md"
related_issues: []
related_prs: []
---

# Survey: Subject multi-run judge batch evaluation

## Background

Core-Feat-44 は、通常タスクで被験 LLM を複数回実行し、出力を 1 回の judge 評価入力として
束ねる機能を追加する。現状の実行パイプラインは **被験 1 回 → judge `judge_runs` 回** であり、
被験側のばらつきを judge に渡す手段がない。

調査対象:

- `BenchmarkEngine.run_task` — 被験呼び出しと judge 評価の接続
- `judge_runs` — `RunRequest` / engine 初期化パラメータ
- `run_holistic_task` / `_build_bundled_responses` — 複数出力を 1 judge 入力へ束ねる既存パターン

## Objective

1. 現行 `run_task` の被験〜judge データフローを把握する。
2. 評価セマンティクス（best-of / list-eval / average）のトレードオフを整理する。
3. holistic bundled パターンを subject multi-run へ転用できるか評価する。
4. API コスト・コンテキスト長・保存 schema への影響を見積もる。

## Method

- 2026-07-23 時点の `core/benchmark_engine.py`、`server.py`（`RunRequest`）、
  `frontend/src/lib/executionPresets.ts` を静的読解。
- holistic reference doc と `_build_bundled_responses` 実装を比較。
- TODO AC-001〜005 と照合。

## Results

### 現行 `run_task` フロー

1. `_call_subject_llm` を **1 回** 呼び、`subject_response`（文字列）を得る。
2. 各 judge adapter に対し `_run_judge_evaluation(subject_response=...)` を実行。
3. `_run_judge_evaluation` 内で `judge_runs` 回の judge API 呼び出し → `ResultAggregator.aggregate`。
4. `TaskResult.to_dict()` は単一 `response`、`subject_usage`、`tool_trace` を保存。

`judge_runs` は engine コンストラクタと `RunRequest.judge_runs`（default 3）で制御。
被験側の繰り返しパラメータは存在しない。

### Holistic の bundled パターン（関連先例）

`run_holistic_task`:

- 被験 LLM は呼ばない。
- 通常 task の出力一覧 `bundled_responses` を `_build_bundled_responses` で 1 文字列化。
- その文字列を `subject_response` として `_run_judge_evaluation` に渡す。

`_build_bundled_responses` 形式:

```text
### タスク: {task_id}（{task_type}）
#### 入力プロンプト
...
#### 被験LLMの回答
...

---

（次タスク…）
```

- 複数 **異なる task** の出力を横断評価する用途。
- envelope は `_build_judge_user_prompt` の `<untrusted_subject_answer>` 1 ブロックに収まる。
- strict mode の bundled resource hashing は holistic 専用。

### 評価セマンティクス选项

| 方式 | 概要 | メリット | デメリット |
| --- | --- | --- | --- |
| **A. List-eval（bundled）** | N 被験出力を 1 プロンプトに並列列挙し、judge が集合として 1 スコアを返す | judge 呼び出し回数は現行と同じ。ばらつき・一貫性を直接評価可能。holistic と実装共通化しやすい | プロンプト長 N 倍。rubric / system prompt の「複数出力」指示が必要。コンテキスト上限リスク |
| **B. Best-of** | N 被験のうち judge が最良 1 件だけ採点（または自動 best 選択後 1 回 judge） | 短い judge 入力 | 「最良」の定義が judge 依存。残り run の情報損失。実装が 2 段階になりやすい |
| **C. Average-of-scores** | 各被験 run を個別 judge し、N×judge_runs スコアを平均 | 既存 aggregator をほぼ流用 | API コスト N 倍。judge 呼び出しが N × judge_runs に増加。task 結果 schema が「複数 judge 結果セット」へ膨張 |
| **D. Per-run scores + 集約** | 各被験 run に run 別スコアを付け、UI/backend で mean/max を表示 | 透明性が高い | C と同様にコスト増。AC-003 の「1 回の judge 評価入力」とズレる |

### スキーマ・UI 現状

- `RunRequest`: `judge_runs`, `subject_temp`, `run_holistic` 等。**`subject_runs` なし**。
- `ExecutionPresetConfig`: `judgeRunCount` のみ。被験 run 数の preset フィールドなし。
- `TaskResult` / frontend `TaskResult`: 単一 `response` フィールド。
- usage 集計: `summarize_subject_usage(completed)` は task 単位の `subject_usage` を合算。

### コスト・コンテキスト見積もり

- **List-eval (A)**: 被験 API コスト ≈ N 倍、judge API コスト ≈ 現行維持（judge_runs 依存）。
  judge 入力トークン ≈ N × 平均回答長 + ヘッダオーバーヘッド。
- **Per-run judge (C/D)**: 被験 N 倍 + judge N 倍（× judge_runs）。
- tool 利用 task では各被験 run が独立 `tool_trace` を持つ。bundled 形式では run 別 trace の
  要約または省略方針が必要。

## Discussion

### 推奨セマンティクス

**A. List-eval（bundled）** を第一候補とする。

- TODO Goal「出力を 1 回の judge 評価入力としてまとめて渡す」と字面一致。
- holistic の `_build_bundled_responses` と `_build_judge_user_prompt` を拡張すれば、
  「同一 task の run #1..#N」版を共通化できる。
- `judge_runs` との独立性: 被験 N 回 × judge 各 M 回の **直積** ではなく、
  被験 N 出力を束ねた **1 回答ブロック** に対して judge M 回 — 意図が明確。

Best-of / average は Non-Goals とし、将来 `subject_runs` 保存形式を変えずに
 judge プロンプトモードとして追加可能な余地を Intent に残す。

### 実装上の論点

1. **プロンプト契約**: system / rubric に「複数被験試行を集合として評価し、一貫性・最良/最悪の差を
   考慮する」旨を追加。`subject_runs=1` では現行文言と同等に退化。
2. **保存 schema**: `subject_runs: [{ response, subject_usage, tool_trace, run_index }, ...]` と
   後方互換の `response`（代表値または run #1）を併存。
3. **エラー混在**: 一部 run が `[ERROR]` の場合、成功 run のみ judge へ渡すか、
   失敗 run も明示して減点するか — Intent で決定。
4. **上限**: UI / API で `subject_runs` の max（例: 5）を設け、コンテキスト超過を QA で検証。

### Risk High の根拠

- 評価意味論の変更（judge が見る evidence の構造が変わる）。
- 被験 API コスト・所要時間の線形増加。
- 長回答 task × 多 run で judge コンテキスト上限に抵触しうる。

## Recommended Actions

1. Plan / Intent で **list-eval bundled** を採用し、best-of / per-run average を Non-Goals に明記。
2. `_build_bundled_subject_runs`（仮）を holistic bundler と共通化可能な形で設計。
3. `RunRequest` / preset / Run UI に `subject_runs`（default 1）を追加。
4. 結果 JSON と ResultDetail に run 別出力・合算 usage を表示。
5. QA test-plan で 1 run / N run / エラー混在 / コンテキスト上限近傍を Test Matrix に含める。
