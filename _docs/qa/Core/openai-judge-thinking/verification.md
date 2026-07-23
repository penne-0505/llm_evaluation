---
title: "QA Verification: OpenAI judge reasoning and thinking capture"
status: active
draft_status: n/a
qa_schema: 2
qa_status: partial
risk: High
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/intent/Core/openai-judge-thinking/decision.md"
  - "_docs/qa/Core/openai-judge-thinking/test-plan.md"
  - "_docs/archives/plan/Core/openai-judge-thinking/plan.md"
related_issues: []
related_prs: []
---

# QA Verification: OpenAI judge reasoning and thinking capture

## Summary

OpenRouter Chat Completions 経路で `message.reasoning` / `reasoning_details` を抽出し、
欠落時のみ `<thinking>` タグ fallback とパース前 strip を行う実装を入れた。
`CompletionResult.api_reasoning` と judge run の `api_reasoning` は採点 JSON `reasoning` と
分離して永続化し、frontend は `apiReasoningSamples` を
「API thinking（モデル内部推論）」折りたたみで表示する。Responses API は Intent どおり未採用。
backend / frontend の自動テストは成功。live OpenRouter reasoning モデルでの Manual QA は未実施。

## Verification Verdict

Verdict: PARTIAL

## Commands Run

```bash
uv run pytest tests/test_adapters.py tests/test_benchmark_engine.py -q
uv run pytest -q
node --test frontend/src/api/client.node.test.ts
npm run lint --prefix frontend
npm run build --prefix frontend
git diff --check
```

Result:

```text
adapter + engine targeted: 38 PASS
backend full pytest: 107 PASS (+ 23 subtests)
frontend client.node.test.ts: 3 PASS
frontend lint: PASS
frontend production build: PASS
git diff --check: PASS
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `tests/test_adapters.py`（reasoning / details / tag / empty） | PASS | AC-001, AC-004 |
| `tests/test_benchmark_engine.py`（api_reasoning 分離・strip・欠落） | PASS | AC-002, AC-004 |
| backend full suite | PASS | 107件 |
| `client.node.test.ts` api_reasoning 分離 | PASS | AC-003 変換契約 |
| frontend lint / build | PASS | ResultDetail 型・UI 含む |
| Intent DEC-002 / DEC-003 diff review | PASS | AC-005 |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| OpenRouter reasoning 対応 judge で API thinking 折りたたみ表示 | DEFERRED | live API smoke 未実施 |
| 採点根拠と API thinking のラベル分離 | PASS（code review） | 「採点根拠を表示」と「API thinking（モデル内部推論）」 |
| 非 reasoning judge で thinking セクション非表示 | PASS（stub） | `api_reasoning` 欠落時は `apiReasoningSamples=[]` |
| thinking 欠落 run の再読み込みで UI エラーなし | PASS（変換テスト） | 空配列フォールバック |

## High-risk Checklist

- [x] Rollback: adapter 抽出・engine マージ・UI を戻すのみ。既存 `reasoning` unchanged
- [x] Data safety: additive `api_reasoning`。旧 run は frontend が空配列扱い
- [x] Security / privacy: ResultDetail に内部推論へ個人情報が含まれうる旨を表示
- [x] Failure mode: thinking 欠落・非対応でも aggregated 成功（engine stub 確認）

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | adapter stub: `message.reasoning` / `reasoning_details` / `<thinking>` fallback |
| AC-002 | PASS | engine が run に `api_reasoning` を保存し、judge JSON `reasoning` とキー衝突なし |
| AC-003 | PARTIAL | client 変換と ResultDetail ラベル実装済み。live 視覚確認は deferred |
| AC-004 | PASS | thinking 欠落 stub でも aggregated 成功 |
| AC-005 | PASS | Intent DEC-002 / DEC-003 が CC 第一・Responses defer・タグ fallback を明記 |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | `api_reasoning` と採点根拠 `reasoning` / `reasoningSamples` を分離。同名マージなし |
| DEC-002 | PASS | Chat Completions 維持。Responses API への judge 移行なし |
| DEC-003 | PASS | 正規フィールド空時のみタグ fallback。strip 後に JSON パース |
| DEC-004 | PASS | `CompletionResult.api_reasoning` は provider 非依存 optional |

## Invariant Coverage

None

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| AC-003 live visual | OpenRouter live reasoning モデルでの折りたたみ表示未確認 | Core-Test-49 |
| Responses API | Intent で defer | o-series 可視 thinking 必須時に別 Intent |

## Residual Risks

- live OpenRouter（o-series / deepseek-r1 等）で CC 経路の thinking 可視性が製品要件を満たすかは未確認。
  o-series で常に空なら Intent follow-up（Responses API）検討が必要。
- OpenRouter の `reasoning_details` 形状差分で抽出テキストが粗くなる可能性（stub は代表形のみ）。

## Follow-up TODOs

- Core-Test-49: OpenRouter reasoning 対応 judge 1 件で ResultDetail の API thinking /
  採点根拠の両方表示を live 確認する（test-plan Manual QA Checklist）。

## Engine Conflict Notes

Enhance-35（holistic overflow）と同一ファイルを編集した。マージ時に再読し、
`subject_prompt=""`（Bug-36）、`has_subject_tools`（Feat-42）、`bundling_metadata`（Enhance-35）を
保持したまま `_run_judge_evaluation` の parse / merge のみ変更した。
