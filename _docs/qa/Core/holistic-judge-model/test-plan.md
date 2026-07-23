---
title: "QA Test Plan: Separate judge model for holistic evaluation"
status: active
draft_status: n/a
qa_schema: 2
qa_status: in-progress
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/plan/Core/holistic-judge-model/plan.md"
  - "_docs/intent/Core/holistic-judge-model/decision.md"
  - "_docs/archives/survey/Core/holistic-judge-model/survey.md"
  - "_docs/reference/Core/holistic-evaluation.md"
  - "_docs/qa/Core/holistic-judge-model/verification.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Separate judge model for holistic evaluation

## Source of Intent

- `_docs/intent/Core/holistic-judge-model/decision.md`

## Decision Review Scope

- `DEC-001`: optional `holistic_judge_models` と `judge_models` fallback が API / preset 全体で一貫するか。
- `DEC-002`: holistic path のみ adapter 解決が分離され、standard path が unchanged か。
- `DEC-003`: 結果 JSON に `holistic_judge_models` が記録され converter が読めるか。
- `DEC-004`: preset capture / resolve が holistic judge を round-trip するか。
- `DEC-005`: 同一 judge 継続 vs 別 judge 分離の設計理由が Intent に残り、strict mode 境界が意図どおりか。

## Quality Goal

通常タスク judge と独立に holistic 専用 judge を指定・実行・保存・表示でき、未指定時は従来
どおり `judge_models` が holistic にも使われる。preset 復元と strict mode 境界が破綻しない。

## Acceptance Criteria

- AC-001: Run 設定（`RunRequest` / `ExecutionPresetConfig` / Run UI）で holistic judge モデルを
  通常 judge とは別に指定できる。未指定時は `judge_models` を holistic にも使用する。
- AC-002: `server.py` の holistic 実行経路が holistic 用 adapter セットを使用し、通常タスク
  judge とは独立に並列・試行回数設定が効く。
- AC-003: 保存結果 JSON に holistic judge モデル情報が記録され、結果画面で通常 judge と区別
  して表示できる。
- AC-004: preset 保存・復元が holistic judge 設定を含む。
- AC-005: Intent に同一 judge 継続 vs 別 judge 分離の設計理由が DEC として残り、通常のみ /
  holistic のみ / 両方別指定のケースが検証される。

## Intent-derived Invariants

- INV-001: `holistic_judge_models` 未指定または空 → holistic は `judge_models` と同一 adapter。
- INV-002: `run_holistic=false` → holistic adapter 解決なし。

## Risk Assessment

- Medium: adapter 解決の取り違えは standard / holistic 両方のスコア信頼性を損なう。
- Medium: preset 欠落は利用者設定の再現性を失う。
- Low: strict mode との誤整合（holistic override を strict 違反とみなす）を避ける。
- Out of scope: live provider smoke、holistic overflow（Core-Enhance-35）。

## Test Strategy

- Python unit / integration test で `RunRequest` 受理、holistic adapter 分離、saved JSON key を
  mock engine 上で確認する。
- Node test で preset capture/resolve、request body 3 パターンを確認する。
- frontend lint/build と ResultDetail review で表示分離を確認する。
- Intent DEC-005 を verification で rationale と strict 境界を review する。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | RunRequest / preset / UI で holistic judge 指定 | schema + node + review | `uv run --with pytest python -m pytest tests/test_server_frontend.py -k holistic_judge`、`npx --prefix frontend tsx --test frontend/src/lib/executionPresets.node.test.ts` | optional field 受理、preset に `holisticJudgeModels`、RunPage UI に選択 | verified |
| AC-002 | TODO | holistic path が別 adapter セット使用 | unit / integration | `uv run --with pytest python -m pytest tests/test_server_frontend.py -k holistic_judge_adapters` | mock で standard vs holistic adapter ID が分離、`judge_runs` 適用 | verified |
| AC-003 | TODO | 結果 JSON と UI 表示 | unit + review | `frontend/src/api/client.node.test.ts`、ResultDetail diff | `holistic_judge_models` 保存、包括評価セクションで holistic judge 表示 | verified |
| AC-004 | TODO | preset round-trip | node unit | `npx --prefix frontend tsx --test frontend/src/lib/executionPresets.node.test.ts`、`frontend/src/store/settingsStore.node.test.ts` | capture → resolve で holistic judge 復元 | verified |
| AC-005 | TODO | DEC 記録と 3 パターン検証 | integration + review | holistic judge 3-pattern test、Intent diff | 通常のみ / holistic のみ / 両方別指定で期待 adapter が使われる | verified |
| INV-001 | Intent | 未指定時 fallback | unit | fallback test | 空 `holistic_judge_models` で `judge_models` adapter が holistic に使われる | verified |
| INV-002 | Intent | run_holistic=false で解決スキップ | unit | server path test | holistic adapter 解決関数が呼ばれない | verified |
| DEC-001 | Intent | optional field + fallback 一貫 | review + unit | API schema test | backend / frontend 両方で semantic 一致 | verified |
| DEC-002 | Intent | holistic-only adapter 分離 | unit | engine / server mock test | standard task が holistic adapter を使わない | verified |
| DEC-003 | Intent | 別 JSON key 記録 | unit | result JSON fixture | `judge_models` 上書きなし | verified |
| DEC-004 | Intent | preset に含める | node unit | executionPresets test | 空配列 = fallback の round-trip | verified |
| DEC-005 | Intent | 設計理由と strict 境界 | review | strict mode test + Intent | holistic override が strict enforced を阻害しない | verified |

## Manual QA Checklist

- [ ] Run 画面で holistic judge を通常 judge と別指定して run し、holistic 結果に期待モデル名が出る。
- [ ] holistic judge 未指定 run が従来と同じ judge で holistic 完走する。
- [ ] preset 保存 → 再読み込み → Run で holistic judge 設定が復元される。
- [ ] strict mode ON で per-task judge は preset 固定、holistic judge override は run 可能（または UI 方針どおり）。

## Regression Checklist

- [ ] standard-only run（`run_holistic=false`）の judge 解決・結果 JSON が従来どおり。
- [ ] 旧 preset（holistic field なし）読み込みで fallback が効く。
- [ ] 横断サマリー（per-task average）に holistic task が含まれない既存方針を維持。

## Out of Scope

- holistic judge 専用 temperature / system prompt。
- strict official holistic judge preset。
- Core-Enhance-35 overflow 処理。

## Open Questions

None。
