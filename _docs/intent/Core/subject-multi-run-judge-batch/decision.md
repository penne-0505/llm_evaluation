---
title: "Intent: Subject multi-run judge batch evaluation"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/survey/Core/subject-multi-run-judge-batch/survey.md"
  - "_docs/archives/plan/Core/subject-multi-run-judge-batch/plan.md"
  - "_docs/qa/Core/subject-multi-run-judge-batch/test-plan.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# Intent: Subject multi-run judge batch evaluation

## Context

現行パイプラインは `BenchmarkEngine.run_task` が被験 LLM を 1 回呼び、得た `subject_response` を
各 judge の `_run_judge_evaluation`（`judge_runs` 回）へ渡す。被験側のサンプリングばらつきを
judge が観測できず、安定性や worst-case の評価ができない。

包括評価（holistic）のみ、複数 task 出力を `_build_bundled_responses` で 1 文字列に束ね、
judge 1 入力として評価する先例がある。同一 task 内の複数被験 run へ拡張する際、
best-of / list-eval / per-run average など評価セマンティクスの選択が主論点である。

## Decisions

### DEC-001: 評価セマンティクスは list-eval bundled を採用する

- **What**: `subject_runs = N` のとき N 回の被験出力を 1 つの `<untrusted_subject_answer>` 相当
  ブロックに run 番号付きで列挙し、judge は **集合として 1 組のスコア**（既存三軸 + total）を
  返す。judge API 呼び出し回数は `judge_runs` のみ（被験 N 回とは独立）。
- **Why**: TODO Goal「1 回の judge 評価入力としてまとめて渡す」と一致。holistic bundler との
  共通化で実装リスクを下げ、ばらつき・一貫性を judge が直接評価できる。
- **Change freedom**: 列挙フォーマット（見出し、区切り線）、run ラベル、`tool_trace` 要約形式は
  変更可能。スコア出力 schema は現行維持。
- **Why not**: **best-of** は最良 run 選択基準が judge 依存で再現性が低い。**per-run judge +
  平均** は judge コストが N 倍になり、AC-002 の独立性（被験 N × judge M の直積）と混同されやすい。

### DEC-002: `subject_runs` と `judge_runs` は独立パラメータとする

- **What**: `RunRequest.subject_runs`（default `1`、max `5`）は被験 LLM 呼び出し回数。
  `judge_runs` は bundled 回答に対する judge 試行回数。engine / server / UI / preset で
  別フィールドとして保持する。
- **Why**: 被験ばらつきの観測密度と judge 採点の安定化（複数 judge run）は別次元のノブである。
- **Change freedom**: max 上限、default 値、UI 配置は変更可能。
- **Why not**: 単一 `runs` パラメータに統合すると、既存 `judge_runs` 意味論を破壊する。

### DEC-003: 結果 schema は run 配列 + 後方互換の代表 `response` を保存する

- **What**: task 結果 JSON に以下を保存する。

  ```json
  {
    "subject_runs": [
      { "run_index": 1, "response": "...", "subject_usage": {}, "tool_trace": [], "error": null }
    ],
    "response": "<run #1 response または bundled 代表>",
    "subject_run_count": 3
  }
  ```

  旧 consumer は `response` のみ読めば従来同等。詳細 UI は `subject_runs` を表示する。
- **Why**: 後方互換と run 別 usage / エラー追跡を両立する。
- **Change freedom**: `response` の代表値ポリシー（first success / last / プレースホルダ）は
  実装詳細として変更可能。保存キー名は migration 方針に従う。
- **Revisit when**: strict mode が subject run 内容を hash 対象に含める必要が出た場合。

### DEC-004: 一部被験 run 失敗時は成功 run のみ judge へ渡し、失敗 run は列挙内に `[ERROR]` として残す

- **What**: 被験 run が LLM エラー等で失敗した場合、その run は bundled 入力に `[ERROR] ...` として
  含める。成功 run が 1 件以上あれば judge 評価は続行する。全 run 失敗時は task 失敗扱い。
- **Why**: 部分成功の情報を judge が減点根拠にできる。全 run 失敗のみ hard fail とする。
- **Change freedom**: 失敗 run を列挙から省略するモードは将来オプションにできるが初版は明示列挙。

### DEC-005: コスト・コンテキスト影響を文書化し、`subject_runs` 上限 5 で clamp する

- **What**: 被験 API コストと所要時間はおおよそ `subject_runs` に比例して増加する。
  judge 入力トークンは bundled 長に比例。`subject_runs` は API / UI 双方で 1〜5 に clamp。
- **Why**: 長回答 task × 多 run で judge コンテキスト上限に抵触するリスクを bounded にする。
  AC-005 の Intent 記録義務を満たす。
- **Change freedom**: 上限値は設定化可能。初版は 5。
- **Why not**: 上限なしは Risk High のコスト暴走と context overflow を招く。

### DEC-006: strict mode は `subject_runs` を固定しない

- **What**: 初版の strict preset 検証は既存の `judge_runs` / temperature / task 集合に限定し、
  `subject_runs` は standard / strict 双方でユーザー指定（1–5）を許可する。
- **Why**: 被験ばらつき観測は採点再現性ノブ（judge_runs）とは別次元であり、strict の
  judge 側固定契約を壊さない。
- **Change freedom**: 将来 strict で `subject_runs=1` 固定にする場合は preset と validator へ追加。
- **Revisit when**: strict leaderboard が被験サンプリング条件もハッシュ対象にする場合。

## Consequences / Impact

- `RunRequest`、preset schema version、strict mode 検証（該当時）への additive field。
- `summarize_subject_usage` が run 配列を合算する。
- judge system prompt / rubric 注記に複数試行評価の短い指示を追加。
- ResultDetail に run タブまたは折りたたみ表示。

## Quality Implications

- `subject_runs=1` で現行プロンプト・スコア分布が大きく変わらないことを回帰テストする。
- N run / エラー混在 / 上限 clamp を Test Matrix で検証する。
- bundled 長が極端な fixture で judge prompt builder が破綻しないことを unit test する。

## Intent-derived Invariants

- INV-001 (from DEC-002): `subject_runs` を N に設定しても judge 評価の outer 呼び出し回数は
  `judge_runs` × judge モデル数であり、N 倍にならない。
- INV-002 (from DEC-001): bundled 入力は単一 task の複数 run のみを含み、holistic の複数 task
  bundling とは builder 関数を共有しても混同しない（task 種別で分岐）。
- INV-003 (from DEC-003): `subject_runs=1` の保存 JSON は、新 field を除き従来 schema と
  意味的に同等である。

## Rollback / Follow-ups

- rollback は `subject_runs` フィールドと multi-run loop を除去し default 1 に戻す。
- 保存済み multi-run 結果は読取専用表示を維持（データ loss なし）。
- 将来 best-of / per-run average が必要なら、別 `subject_eval_mode` enum で拡張する。
