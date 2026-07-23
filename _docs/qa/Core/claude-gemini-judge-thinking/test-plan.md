---
title: "QA Test Plan: Claude and Gemini judge reasoning capture"
status: active
draft_status: n/a
qa_schema: 2
qa_status: in-progress
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/survey/Core/claude-gemini-judge-thinking/survey.md"
  - "_docs/archives/plan/Core/claude-gemini-judge-thinking/plan.md"
  - "_docs/intent/Core/claude-gemini-judge-thinking/decision.md"
  - "_docs/qa/Core/claude-gemini-judge-thinking/verification.md"
  - "_docs/qa/Core/openai-judge-thinking/test-plan.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Claude and Gemini judge reasoning capture

## Source of Intent

- `_docs/intent/Core/claude-gemini-judge-thinking/decision.md`

## Decision Review Scope

- `DEC-001`: OpenRouter 正規化フィールドからの Anthropic / Gemini 抽出。
- `DEC-002`: Gemini 非 thinking no-support rationale。
- `DEC-003`: `:thinking` と opt-in の同一レスポンス抽出経路。
- `DEC-004`: Core-Feat-37 との `api_reasoning` / UI 契約共有。

## Quality Goal

Claude / Gemini judge 実行時、API thinking を provider 別に正しく取得（または no-support で
空）し、judge 採点と `reasoningSamples` を壊さない。`:thinking` と opt-in の両モードを
テストで確認する。

## Acceptance Criteria

- AC-001: Anthropic Messages API 相当の thinking（OpenRouter 経由）が adapter で抽出される。
- AC-002: Gemini thinking 取得可否が調査され、可能なら実装、不可なら Intent に no-support
  rationale がある。
- AC-003: 抽出結果は judge JSON `reasoning` と区別され run JSON に保存される。
- AC-004: `:thinking` suffix と opt-in reasoning の両方で thinking 取得または graceful skip が
  テストされる。
- AC-005: thinking 取得失敗時も judge スコア集計は従来どおり完了する。

## Intent-derived Invariants

None

## Risk Assessment

- **Medium — 外部 API**: OpenRouter の Anthropic / Gemini 正規化形状変更。
- **Medium — 保存 JSON**: additive `api_reasoning`（37 と同一）。
- **Medium — `:thinking` 誤解**: opt-in False でも抽出必須（DEC-003）。
- **Regression**: 非 reasoning Claude / Gemini 通常モデルの judge パス。

## Test Strategy

- **Unit**: OpenRouter stub — Claude `reasoning` + `reasoning_details`、`:thinking` モデル ID。
- **Unit**: Gemini thinking モデル stub / 非 thinking 空レスポンス。
- **Integration**: engine run dict、`api_reasoning` と judge `reasoning` 共存。
- **Frontend**: 37 UI 契約利用時は表示分離の smoke（本タスク単独では backend テストを主とする）。
- **Diff review**: Intent DEC-002 Gemini no-support 記述とテストの一致。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO / DEC-001 | Anthropic thinking OpenRouter レスポンス抽出 | unit | `uv run pytest tests/test_adapters.py` | Claude stub → `api_reasoning` 非空 | verified |
| AC-002 | TODO / DEC-002 | Gemini thinking モデル抽出 | unit | `tests/test_adapters.py` | Gemini thinking stub → 非空 | verified |
| AC-002 | TODO / DEC-002 | Gemini 非 thinking no-support | diff review + unit | `_docs/intent/.../decision.md`、`tests/test_adapters.py` | Intent rationale + 空 api_reasoning、採点成功 | verified |
| AC-003 | TODO / DEC-004 | `api_reasoning` vs judge `reasoning` | integration | `uv run pytest tests/test_benchmark_engine.py` | 両フィールド共存 | verified |
| AC-004 | TODO / DEC-003 | `:thinking` suffix（extra_params なし） | unit | `tests/test_adapters.py` | `:thinking` ID + reasoning フィールド → 抽出 | verified |
| AC-004 | TODO / DEC-003 | opt-in + effort high | integration | `tests/test_benchmark_engine.py` | extra_params 送信 + 抽出 | verified |
| AC-005 | TODO | thinking 欠落・失敗時採点完走 | integration | `tests/test_benchmark_engine.py` | aggregated 成功 | verified |
| AC-001–005 | Plan | backend 回帰 | regression | `uv run pytest` | 既存 reasoning opt-in テスト pass | verified |
| AC-003 | TODO / DEC-004 | UI 表示分離（37 契約） | manual / node | `frontend/src/api/client.node.test.ts`、ResultDetail | API thinking と reasoningSamples 独立（live 目視は Core-Test-49） | verified |

## Manual QA Checklist

- [ ] Claude `:thinking` judge で API thinking 折りたたみが表示される（37 UI 利用時）。
- [ ] Claude opt-in judge（effort high）で thinking が表示される。
- [ ] Gemini thinking モデルで thinking 表示（対応モデル利用時）。
- [ ] Gemini 非 thinking judge で thinking セクションなし・採点成功。

## Regression Checklist

- [ ] `is_reasoning_opt_in` の `:thinking` → False 挙動は維持（effort 送信条件）。
- [ ] judge JSON `reasoning` / `reasoningSamples` は採点根拠のまま。
- [ ] OpenAI judge パス（Core-Feat-37）に Claude/Gemini 分岐が副作用を出さない。

## High-risk Checklist

Not applicable (Risk Medium).

## Out of Scope

- OpenAI Responses API（Core-Feat-37）。
- LM Studio judge。
- 被験 subject thinking。
- ネイティブ Anthropic / Google SDK。

## Open Questions

- Resolved: Core-Feat-37 UI はマージ済み。38 は UI 非変更で契約再利用。live Manual QA は
  verification PARTIAL として Core-Test-49 拡張へ defer。
