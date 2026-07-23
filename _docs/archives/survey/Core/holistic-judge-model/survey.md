---
title: "Survey: Separate judge model for holistic evaluation"
status: completed
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/plan/Core/holistic-judge-model/plan.md"
  - "_docs/intent/Core/holistic-judge-model/decision.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# Survey: Separate judge model for holistic evaluation

## Background

ベンチマーク run は frontend `RunPage` → `buildRunRequestBody` → `POST /run` → `server.py`
`run_benchmark` 経路で実行される。judge モデルは request 全体で1セットのみ指定される。

## Objective

- 現行 `RunRequest`、`ExecutionPresetConfig`、holistic 実行経路での judge 利用箇所を特定する。
- holistic と standard の adapter 解決がどこで共有されているか整理する。
- 結果 JSON / UI に judge 情報がどう載るか確認する。
- separate holistic judge 実装のタッチポイントを Plan へ渡す。

## Method

- 静的コード読解: `server.py`（`RunRequest`、`get_available_judge_adapters`、`BenchmarkEngine`
  生成、holistic ブロック）、`core/benchmark_engine.py`（`run_holistic_task`、`judge_adapters`）、
  frontend `types/index.ts`、`executionPresets.ts`、`client.ts`（`buildRunRequestBody`、
  `convertBenchmarkResult`）、`RunPage.tsx`、`ResultDetail.tsx`。
- strict mode: `core/strict_mode.py` の `judge_models` 検証範囲確認。

## Results

### RunRequest（backend）

```python
class RunRequest(BaseModel):
    target_model: str
    judge_models: List[str]
    selected_task_ids: List[str]
    judge_runs: int = 3
    ...
    run_holistic: bool = True
    judge_parallel: bool = True
```

`holistic_judge_models` 相当フィールドは無い。

### Judge adapter 解決（server.py）

```text
judge_adapters = get_available_judge_adapters(req.judge_models, api_keys=api_keys)
engine = BenchmarkEngine(..., judge_adapters=judge_adapters, judge_runs=req.judge_runs, ...)
...
engine.run_holistic_task(...)  # 同一 engine / 同一 judge_adapters
```

holistic progress / task state も `list(judge_adapters.keys())` を参照する。

### BenchmarkEngine

- コンストラクタで `judge_adapters: Dict[str, LLMAdapter]` を受け取る。
- `run_holistic_task` は `self.judge_adapters.items()` を iterate し、
  `self.judge_runs` と `self.max_parallel_judges` を使用する。
- holistic 専用 adapter 引数は現状無い。

### ExecutionPresetConfig（frontend）

```typescript
export interface ExecutionPresetConfig {
    subjectModel: string | null;
    judgeModels: string[];
    taskSelections: Record<string, boolean>;
    runHolistic: boolean;
    judgeRunCount: number;
    subjectTemperature: number;
}
```

holistic judge フィールド無し。`captureExecutionPresetConfig` は `judgeModelIds` /
`freeTextJudges` のみ保存。

### Run request body（frontend）

`buildRunRequestBody` は `judge_models: params.judgeModels` のみ送信。
RunPage は `effectiveJudgeIds` を単一 judge リストとして渡す。

### 結果 JSON

`benchmark_result` トップレベル:

```json
{
  "judge_models": ["..."],
  "judge_runs": 3,
  "tasks": [...],
  "holistic_tasks": [...]
}
```

holistic 用 judge リストの独立キーは無い。frontend `convertBenchmarkResult` は
`judgeModels` を `raw.judge_models` のみから構築。

### UI

- `ResultDetail`: 「評価モデル」は run 全体の `run.judgeModels` を表示。
- 包括評価セクションは `holisticTaskResults` を `TaskResultCard` で表示するが、
  run レベル judge リストと holistic 専用 judge の区別表示は無い。
- 横断サマリーは per-task のみ（holistic 除外は reference どおり）。

### Strict mode

`validate_official_strict_request` は `judge_models` のみ official preset と照合。
holistic phase についての judge 固定は無い。

## Discussion

- 最小変更は optional `holistic_judge_models` + holistic ブロックでの再解決。
- engine 変更案:
  - A) `run_holistic_task(..., judge_adapters_override=...)`
  - B) holistic 直前に engine の adapter を差し替え（非推奨: standard 完了後なら安全だが API が汚れる）
  - C) holistic 専用 lightweight engine インスタンス（subject adapter 不要）
- 結果 JSON は additive `holistic_judge_models` が安全。旧 consumer は無視可能。
- preset は `holisticJudgeModels: []` = fallback が migration 容易。
- strict mode では per-task judge 固定のみ維持し、holistic override を許容するのが
  既存 product 意味論（holistic は official 平均外）と整合する。

## Recommended Actions

1. `RunRequest.holistic_judge_models: List[str] = []` を追加する。
2. holistic ブロックで `holistic_judge_adapters = get_available_judge_adapters(...)` を
   解決し、`run_holistic_task` へ override 渡しする（Plan Tasks 4 参照）。
3. frontend preset / settingsStore / RunPage / `buildRunRequestBody` を拡張する。
4. `benchmark_result["holistic_judge_models"]` と ResultDetail 表示を更新する。
5. QA test-plan の 3 パターン（fallback / holistic-only 差 / 両方別）を integration test 化する。
