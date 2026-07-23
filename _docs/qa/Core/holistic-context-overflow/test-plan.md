---
title: "QA Test Plan: Holistic bundled_responses context overflow handling"
status: active
draft_status: n/a
qa_schema: 2
qa_status: in-progress
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/plan/Core/holistic-context-overflow/plan.md"
  - "_docs/intent/Core/holistic-context-overflow/decision.md"
  - "_docs/archives/survey/Core/holistic-context-overflow/survey.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Holistic bundled_responses context overflow handling

## Source of Intent

- `_docs/intent/Core/holistic-context-overflow/decision.md`

## Decision Review Scope

- `DEC-001`: 固定 overhead を差し引いた予算見積もりと conservative fallback が実装されているか。
- `DEC-002`: v1 が単一 judge 呼び出し truncation に限定され、split aggregate が混在していないか。
- `DEC-003`: task 境界を保った末尾優先 drop / response truncate の順序がコードと一致するか。
- `DEC-004`: truncation 発生時に `bundling_metadata` が結果 JSON へ記録されるか。

## Quality Goal

包括評価の bundled judge 入力がコンテキスト上限を超えても、API context length エラーで
サイレント失敗せず、切り詰め内容が結果から追跡できる。通常規模の入力では従来どおりの
judge 入力形式を維持する。

## Acceptance Criteria

- AC-001: `_build_bundled_responses`（または後続処理）で推定トークン数または文字数に基づく
  上限チェックが行われ、超過時に明示的な処理（切り詰め）が適用される。
- AC-002: 切り詰めが発生した場合、judge 結果または run メタデータに truncation / split 相当の
  記録があり、UI またはログから検知できる。
- AC-003: 通常規模の bundled_responses（既存テスト相当）では、従来と同一の judge 入力形式が
  維持される（behavior preservation）。
- AC-004: 超過シナリオのユニットテストまたは統合テストが存在し、API エラー（context length
  exceeded）でサイレント失敗しない。

## Intent-derived Invariants

- INV-001: 非超過 bundled_responses の `_build_bundled_responses` 出力形式は変更しない。
- INV-002: overflow 処理が走った holistic task は `bundling_metadata.truncated === true` を持つ。

## Risk Assessment

- Medium: 誤った budget 見積もりは truncation 過多または API エラー残存のいずれかを招く。
- Medium: truncation メタデータ欠落はスコア解釈を誤らせる。
- Out of scope: live provider smoke、split evaluation、per-task judge overflow。

## Test Strategy

- Python unit test で budget resolver、truncation 分岐、`run_holistic_task` metadata 付与を
  mock adapter 上で確認する。
- 既存 holistic / benchmark engine fixture で非超過回帰を確認する。
- docs validator と markdownlint で reference 更新を確認する。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | 上限チェックと超過時 truncation 適用 | unit | `uv run --with pytest python -m pytest tests/test_benchmark_engine.py -k holistic` | oversized fixture で judge 呼び出し前に truncated bundled answer が生成される | verified |
| AC-002 | TODO | truncation / overflow メタデータ記録 | unit + review | `uv run --with pytest python -m pytest tests/test_benchmark_engine.py -k bundling_metadata`、`TaskResult.to_dict()` diff | `bundling_metadata.truncated`、除外 task、処理種別が JSON に含まれる | verified |
| AC-003 | TODO | 非超過時 behavior preservation | unit | `uv run --with pytest python -m pytest tests/test_benchmark_engine.py -k build_bundled` | 通常サイズ fixture で `_build_bundled_responses` 出力が従来形式と一致 | verified |
| AC-004 | TODO | context length exceeded によるサイレント失敗防止 | unit | `uv run --with pytest python -m pytest tests/test_benchmark_engine.py -k overflow` | mock が oversized raw prompt を受け取らず、error フィールドだけで終わらない | verified |
| INV-001 | Intent | 非超過出力形式不変 | unit | 同上 AC-003 | `### タスク:` / `---` 構造維持 | verified |
| INV-002 | Intent | truncated 時 metadata 必須 | unit | 同上 AC-002 | truncation 分岐で `truncated: true` 必須 | verified |
| DEC-001 | Intent | overhead 差引 budget と fallback | unit + review | budget resolver test、Intent diff | 未設定 model でも conservative default が効く | verified |
| DEC-002 | Intent | v1 は single-call truncation のみ | review | engine / holistic path diff | split judge loop や aggregate 合成が無い | verified |
| DEC-003 | Intent | 末尾 task 優先 drop 順序 | unit | truncation order test | 末尾 task から `dropped_tasks` に載る | verified |
| DEC-004 | Intent | metadata 記録契約 | unit | metadata serialization test | 必須フィールドが holistic task JSON に存在 | verified |

## Manual QA Checklist

- [ ] 多数タスク・長文 response の run で holistic が完走し、結果 JSON に truncation 記録がある。
- [ ] truncation あり run の Result 画面またはログで overflow 処理が読める。
- [ ] 通常規模 run では truncation メタデータが付かない（または `truncated: false`）。

## Regression Checklist

- [ ] 非超過 holistic run の judge 入力形式とスコア保存形式が従来どおりである。
- [ ] `run_holistic=false` では overflow 処理経路が呼ばれない。
- [ ] 通常 per-task judge 入力サイズは変更されない。

## Out of Scope

- 分割評価と chunk スコア集約。
- OpenRouter 等 live API による context window 取得 smoke。
- frontend 専用 truncation 警告 UI（metadata 表示以外）。

## Open Questions

None。
