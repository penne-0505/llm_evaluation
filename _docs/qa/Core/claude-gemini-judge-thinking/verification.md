---
title: "QA Verification: Claude and Gemini judge reasoning capture"
status: active
draft_status: n/a
qa_schema: 2
qa_status: partial
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/claude-gemini-judge-thinking/decision.md"
  - "_docs/archives/plan/Core/claude-gemini-judge-thinking/plan.md"
  - "_docs/qa/Core/claude-gemini-judge-thinking/test-plan.md"
  - "_docs/qa/Core/openai-judge-thinking/verification.md"
related_issues: []
related_prs: []
---

# QA Verification: Claude and Gemini judge reasoning capture

## Summary

Claude / Gemini judge は Core-Feat-37 と同一の
`extract_api_reasoning_from_message`（OpenRouter 正規化 `message.reasoning` /
`reasoning_details`）で `api_reasoning` を取得する。Anthropic 向けに
`reasoning_details` の `thinking` キーを正規化キーへ追加した以外、provider 専用パーサは
置かない。`:thinking`（effort 未送信）と opt-in（effort high）の両方、および Gemini
thinking / 非 thinking（空 `api_reasoning` + 採点完走）を stub で確認した。
engine / frontend は 37 経路を再利用し、本タスクでは ResultDetail / Dashboard を変更していない。
live OpenRouter Manual QA は未実施のため PARTIAL。

## Verification Verdict

Verdict: PARTIAL

## Commands Run

```bash
uv run pytest tests/test_adapters.py tests/test_benchmark_engine.py -q
uv run pytest -q
node --test frontend/src/api/client.node.test.ts
git diff --check
```

Result:

```text
adapter + engine targeted: 46 PASS
backend full pytest: 117 PASS (+ 23 subtests)
frontend client.node.test.ts: 3 PASS
git diff --check: PASS
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| Claude `:thinking` / opt-in stub（`test_adapters.py`） | PASS | AC-001, AC-004, DEC-003 |
| Gemini thinking / 非 thinking stub | PASS | AC-002, DEC-002 |
| engine Claude/Gemini `api_reasoning` 永続化・欠落完走 | PASS | AC-003, AC-005 |
| backend full suite | PASS | 117件 |
| `client.node.test.ts` api_reasoning 分離 | PASS | 37 UI 契約再利用 |
| Intent DEC-002 Gemini no-support diff review | PASS | Intent rationale 既存 |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| Claude `:thinking` judge で API thinking 折りたたみ | DEFERRED | live API 未実施 |
| Claude opt-in judge で thinking 表示 | DEFERRED | live API 未実施 |
| Gemini thinking モデルで thinking 表示 | DEFERRED | live API 未実施 |
| Gemini 非 thinking でセクションなし・採点成功 | PASS（stub） | engine / adapter 空 `api_reasoning` |

## High-risk Checklist

Not applicable (Risk Medium).

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | Claude stub: `message.reasoning` / `anthropic-claude-v1` details / `thinking` key |
| AC-002 | PASS | Gemini thinking stub 非空 + 非 thinking 空 + Intent DEC-002 rationale |
| AC-003 | PASS | engine が `api_reasoning` と採点 `reasoning` を共存保存（37 マージ再利用） |
| AC-004 | PASS | `:thinking`（extra_params なし）と opt-in（effort high）の両方 |
| AC-005 | PASS | Gemini 非 thinking / 欠落 stub でも aggregated 成功 |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | OpenRouter CC 共通ヘルパのみ。ネイティブ SDK なし |
| DEC-002 | PASS | 非 thinking Gemini は空 `api_reasoning`、採点は継続 |
| DEC-003 | PASS | 抽出はレスポンスフィールド有無。opt-in はリクエスト制御のみ |
| DEC-004 | PASS | `api_reasoning` / ResultDetail ラベルは 37 契約をそのまま利用 |

## Invariant Coverage

None

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| Manual live Claude/Gemini UI | OpenRouter live thinking judge 未実施 | Core-Test-49 を Claude / Gemini にも拡張 |

## Residual Risks

- OpenRouter が Anthropic / Gemini の `reasoning_details` 形状を変えた場合、stub 代表形以外で
  抽出テキストが粗くなる可能性。
- OpenRouter ドキュメント上 Anthropic `:thinking` suffix は廃止方向。本アプリは既存
  `is_reasoning_opt_in` 契約と DEC-003 のため suffix 抽出パスを維持しているが、実モデル ID
  は opt-in + effort 側が主経路になる可能性がある。

## Follow-up TODOs

- Core-Test-49: Manual QA 対象に Claude `:thinking` / opt-in と Gemini thinking 各 1 件を追加し、
  ResultDetail の API thinking 折りたたみを live 確認する。

## Reuse from Core-Feat-37

- `CompletionResult.api_reasoning`
- `extract_api_reasoning_from_message` / `_format_reasoning_details`
- engine `_run_judge_evaluation` の `api_reasoning` マージ
- frontend `apiReasoningSamples` / 「API thinking（モデル内部推論）」UI

## Engine Conflict Notes

Core-Feat-34 / Core-Feat-46 と共有しうる `benchmark_engine.py` / ResultDetail は未編集。
adapter ヘルパ拡張と stub テストのみ。既存の `bundling_metadata`、`has_subject_tools`、
`task_timing`、`subject_prompt=""` はそのまま。
