---
title: "QA Test Plan: OpenAI judge reasoning and thinking capture"
status: active
draft_status: n/a
qa_schema: 2
qa_status: in-progress
risk: High
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/survey/Core/openai-judge-thinking/survey.md"
  - "_docs/archives/plan/Core/openai-judge-thinking/plan.md"
  - "_docs/intent/Core/openai-judge-thinking/decision.md"
related_issues: []
related_prs: []
---

# QA Test Plan: OpenAI judge reasoning and thinking capture

## Source of Intent

- `_docs/intent/Core/openai-judge-thinking/decision.md`

## Decision Review Scope

- `DEC-001`: `api_reasoning` と judge JSON `reasoning` / `reasoningSamples` の分離。
- `DEC-002`: Chat Completions 第一選択、Responses API defer。
- `DEC-003`: `<thinking>` fallback と JSON パース前 strip。
- `DEC-004`: `CompletionResult` 共有拡張パターン。

## Quality Goal

OpenAI 系 judge 実行時、API thinking を失わず保存・表示しつつ、採点 JSON 取得と既存
`reasoningSamples`（採点根拠）表示を壊さない。thinking 欠落・非対応モデルでは graceful
degradation する。

## Acceptance Criteria

- AC-001: OpenAI / OpenRouter reasoning 対応 judge 呼び出しで adapter / engine が API thinking を
  抽出する。
- AC-002: 抽出 thinking は run JSON に永続化され（`api_reasoning`）、judge JSON `reasoning` と
  区別される。
- AC-003: `ResultDetail` で API thinking が折りたたみ表示され、`reasoningSamples` と混同しない。
- AC-004: 非対応・取得失敗時も judge スコア取得は従来どおり成功し、thinking 欠落のみ記録される。
- AC-005: Chat Completions vs Responses API vs タグ抽出の採否根拠が Intent に記録されている。

## Intent-derived Invariants

None

## Risk Assessment

- **High — 外部 API**: OpenRouter / OpenAI の reasoning フィールド形状変更で抽出が空になる。
- **High — 保存 JSON**: additive だが run サイズ増・機微テキスト混入の可能性。
- **High — 採点境界**: thinking を strip し忘れると JSON パース失敗。
- **Medium — UI**: 採点根拠と thinking のラベル混同。
- **Regression**: 非 reasoning judge（gpt-4o 等）の従来パス。

## Test Strategy

- **Unit**: OpenRouter adapter stub（`message.reasoning`、`reasoning_details`、content タグ、空）。
- **Unit**: thinking strip 後の `JudgeResponseParser` 成功。
- **Integration**: `BenchmarkEngine._run_judge_evaluation` が run dict に `api_reasoning` を付与。
- **Frontend**: `client.ts` 変換と `ResultDetail` 表示分離（node test または component test）。
- **Manual**: OpenRouter reasoning モデル 1 件で thinking 折りたたみと採点根拠の両方表示。
- **Diff review**: Intent DEC-002 / DEC-003 と実装経路の一致。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO / DEC-002 | Chat Completions から `message.reasoning` / `reasoning_details` 抽出 | unit | `uv run pytest tests/test_adapters.py`（新規ケース） | stub response → `CompletionResult.api_reasoning` 非空 | verified |
| AC-001 | TODO / DEC-003 | content `<thinking>` fallback 抽出 | unit | `tests/test_adapters.py` | 正規フィールド空・タグありで api_reasoning 設定 | verified |
| AC-002 | TODO / DEC-001 | run JSON の `api_reasoning` と judge `reasoning` 分離 | integration | `uv run pytest tests/test_benchmark_engine.py` | parsed run に両フィールド、キー衝突なし | verified |
| AC-002 | TODO / DEC-003 | strip 後 text で JSON パース成功 | integration | `tests/test_benchmark_engine.py` | thinking 混入 content でも aggregated スコア取得 | verified |
| AC-003 | TODO | frontend API thinking 折りたたみ・ラベル分離 | node unit + manual | `frontend/src/api/client.node.test.ts`、ResultDetail 手動 | `apiReasoningSamples`（名称は実装準拠）と `reasoningSamples` 独立 | covered |
| AC-004 | TODO | 非対応・欠落時 graceful degradation | unit + integration | `tests/test_adapters.py`、`tests/test_benchmark_engine.py` | thinking なしでも aggregated 成功、error なし | verified |
| AC-005 | TODO / DEC-002 | Intent 採否記録 | diff review | `_docs/intent/Core/openai-judge-thinking/decision.md` | CC 第一、Responses defer、タグ fallback が DEC に明記 | verified |
| AC-001–004 | Plan | 型・lint 回帰 | lint/build | `npm run lint --prefix frontend`、`npm run build --prefix frontend` | success | verified |
| AC-001–004 | Plan | backend 回帰 | regression | `uv run pytest` | 既存 adapter / engine テスト pass | verified |

## Manual QA Checklist

- [ ] OpenRouter reasoning 対応 judge（例: deepseek-r1 系）で API thinking 折りたたみが表示される。
- [ ] 同一 judge で「採点根拠（reasoningSamples）」と「API thinking」が別ラベルである。
- [ ] gpt-4o 等非 reasoning judge で thinking セクションが出ず、採点は従来どおり。
- [ ] thinking 欠落 run を再読み込みしても UI がエラーにならない。

## Regression Checklist

- [ ] `reasoningSamples` は judge JSON `reasoning` のみから構築される。
- [ ] `is_reasoning_opt_in` と `extra_body.reasoning` 送信条件は変更しない（除非仕様変更）。
- [ ] 保存 JSON の aggregated スコア・confidence 集計は unchanged。
- [ ] holistic judge 経路も同一 thinking マージ契約を使う（該当する場合）。

## High-risk Checklist

- [ ] Rollback or recovery path is documented（Plan Deployment / Intent Rollback）。
- [ ] Data safety has been checked（additive フィールド、旧 run 互換、run サイズ）。
- [ ] Security / privacy implications have been checked（thinking に PII が含まれうる旨を UI または docs に明示）。
- [ ] Failure mode is understood（thinking 欠落・パース失敗・API 形状変更時も採点完走）。

## Out of Scope

- Responses API Beta の live smoke（defer）。
- Anthropic / Gemini judge（Core-Feat-38）。
- 被験 subject thinking 表示。
- 保存済み run の backfill。

## Open Questions

- o-series で CC 経路が常に空の場合、product が Responses follow-up を要求するか（実装後の verification で記録）。
