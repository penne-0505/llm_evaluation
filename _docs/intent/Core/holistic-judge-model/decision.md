---
title: "Intent: Separate judge model for holistic evaluation"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/plan/Core/holistic-judge-model/plan.md"
  - "_docs/qa/Core/holistic-judge-model/test-plan.md"
  - "_docs/archives/survey/Core/holistic-judge-model/survey.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# Intent: Separate judge model for holistic evaluation

## Context

ベンチマーク run は `RunRequest.judge_models` で judge adapter を解決し、`BenchmarkEngine`
コンストラクタへ `judge_adapters` として渡す。通常タスクも `run_holistic_task` も同じ
adapter dict を使う。frontend の `ExecutionPresetConfig` は `judgeModels` のみを保持し、
RunPage は単一 judge 選択を request body へ送る。

包括評価は長文 bundled 入力を judge に渡すため、per-task 向けに選んだ judge（例: rubric
忠実度重視）と、長文耐性・文体評価向け judge を同一に強制する必要はない。一方、
未指定時の後方互換と strict mode（official per-task judge 固定）との境界を明確にする必要がある。

## Decisions

### DEC-001: holistic judge は optional `holistic_judge_models` で指定し、未指定時は `judge_models` に fallback する

- **What**: `RunRequest` / preset / frontend state に optional な `holistic_judge_models`
  （List[str]）を追加する。空または未指定のとき holistic 実行は `judge_models` と同じ adapter
  セットを使う。
- **Why**: 既存 preset・API consumer・結果比較を壊さず、必要な run だけ分離を opt-in できる。
- **Change freedom**: フィールド名、UI での default 表示（「通常 judge と同じ」トグル）は
  fallback 意味論を変えない限り変更できる。
- **Why not**: 常に別フィールド必須にしない。移行コストと preset 互換が不必要に上がる。

### DEC-002: holistic 実行経路だけ adapter 解決を分離する

- **What**: `server.py` は standard tasks 用に `req.judge_models` から adapter を解決し、
  holistic ブロックでは `req.holistic_judge_models or req.judge_models` から別解決した
  adapter を `run_holistic_task` へ渡す。`judge_runs` と `judge_parallel` / 並列 semaphore
  設定は holistic adapter セットにも適用する。
- **Why**: 同一 run 内で per-task と holistic の judge 役割を独立させ、並列・試行回数の
  実行意味論を既存 engine 契約に揃える。
- **Change freedom**: engine への渡し方（専用 `BenchmarkEngine` インスタンス vs
  `run_holistic_task(judge_adapters=...)` 引数）は、standard path を汚さない限り変更できる。
- **Why not**: standard task 実行中だけ adapter を差し替えない。run 全体の judge 状態が
  混線し、progress / usage 集計が誤る。

### DEC-003: 結果 JSON は通常 judge と holistic judge を別キーで記録する

- **What**: `benchmark_result` トップレベルに `judge_models`（従来）に加え
  `holistic_judge_models` を保存する。holistic 未実行 run では key 省略または空配列とし、
  frontend converter が `BenchmarkResult` 型へ mapped する。
- **Why**: 結果画面・再現・cost 解釈で「どの judge がどの phase を評価したか」を後から
  区別できる。
- **Change freedom**: UI 表示ラベル、summary 集計から holistic judge を除外する既存方針は
  維持しつつ、表示位置は変更できる。
- **Why not**: `judge_models` だけを上書きしない。standard task の judge 情報が失われる。

### DEC-004: preset 保存・復元は holistic judge 設定を含む

- **What**: `ExecutionPresetConfig` に `holisticJudgeModels: string[]`（frontend 命名）を
  追加し、`captureExecutionPresetConfig` / `resolveExecutionPresetConfig` /
  `settingsStore` apply 経路で読み書きする。空配列は「fallback 使用」を意味する。
- **Why**: Run 設定の再現性が preset の主要価値であり、holistic judge だけが preset 外に
  残ると利用者が毎回手動設定する。
- **Change freedom**: UI 上で preset 編集と Run 画面の配置は変更できる。保存される semantic
  （空 = fallback）は維持する。

### DEC-005: per-task judge 継続と holistic 専用 judge 分離を許容する（同一継続も opt-in で維持）

- **What**: 設計上、通常 judge は task rubric 忠実度・三軸採点に最適化し、holistic judge は
  長文 bundled 入力と横断文体評価に適したモデルを選べる。未指定 fallback により「同一 judge
  継続」も引き続き正式な設定パスとする。strict mode enforced 時は per-task `judge_models`
  のみ official preset と照合し、`holistic_judge_models` override は strict 違反にしない
  （holistic は official 横断サマリーに含めない既存方針と整合）。
- **Why**: 役割が異なる judge を1モデルに縛ると、長文 holistic では context 不足、
  per-task では過剰コストや rubric 不一致が起きうる。strict 比較対象は per-task に限定する
  既存 product 意味論を壊さない。
- **Change freedom**: 将来 strict holistic profile を別途定義する場合は Intent 更新が必要。
  v1 では holistic judge 自由選択を許容する。
- **Why not**: strict mode で holistic judge も固定しない。official benchmark スコア比較の
  対象外 phase まで preset 固定すると設定コストだけが増える。

## Consequences / Impact

- Run UI と preset schema が1フィールド分拡張される。
- server は holistic ブロックで追加 adapter 解決を行い、API key 不足時は holistic 開始前に
  エラーまたは partial failure 方針を既存 holistic failure 処理に合わせる。
- usage / cost 集計は holistic judge 呼び出しを既存 judge usage 集計へ含めつつ、モデル名は
  `holistic_judge_models` で区別可能になる。

## Quality Implications

- backend test で standard / holistic adapter 分離を mock 確認する。
- frontend node test で preset round-trip と request body 3 パターンを確認する。
- ResultDetail で holistic judge 表示の review を行う。

## Intent-derived Invariants

- INV-001 (from DEC-001): `holistic_judge_models` 未指定または空のとき、holistic 実行は `judge_models` と同一 adapter セットを使う（後方互換）。
- INV-002 (from DEC-002): `run_holistic=false` の run では holistic adapter 解決を行わない。

## Rollback / Follow-ups

- rollback は optional field、UI state、結果 JSON key を同時に戻す。旧 results は
  `holistic_judge_models` なしとして `judge_models` 表示に fallback できる。
- holistic judge 専用 temperature / system prompt が必要になったら別 Intent で扱う。
