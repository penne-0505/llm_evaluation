---
title: "QA Test Plan: Subject multi-run judge batch evaluation"
status: active
draft_status: n/a
qa_schema: 2
qa_status: in-progress
risk: High
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/survey/Core/subject-multi-run-judge-batch/survey.md"
  - "_docs/archives/plan/Core/subject-multi-run-judge-batch/plan.md"
  - "_docs/intent/Core/subject-multi-run-judge-batch/decision.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Subject multi-run judge batch evaluation

## Source of Intent

- TODO: Core-Feat-44
- Plan: `_docs/archives/plan/Core/subject-multi-run-judge-batch/plan.md`
- Intent: `_docs/intent/Core/subject-multi-run-judge-batch/decision.md`
- Survey: `_docs/archives/survey/Core/subject-multi-run-judge-batch/survey.md`

## Quality Goal

`subject_runs` で被験を N 回実行し、出力を 1 judge 入力に bundled して評価する。
`judge_runs` とは独立に制御され、`subject_runs=1` では現行と後方互換である。
結果 JSON / UI に run 別データと usage が残り、コスト・時間・コンテキスト影響が bounded である。

## Acceptance Criteria

- AC-001: Run リクエスト / preset / UI に `subject_runs`（1 以上）を指定できる。
- AC-002: `run_task` が N 回被験し、judge 入力を束ねる。`judge_runs` と独立。
- AC-003: judge プロンプト契約が複数被験出力を明示。`subject_runs=1` で後方互換。
- AC-004: 結果 JSON / frontend に複数 run 保存・表示。usage / cost / 時間を追跡。
- AC-005: コスト・コンテキスト影響が Intent に記録され、代表ケース（1 / N / エラー混在）を検証。

## Decision Review Scope

- DEC-001: list-eval bundled で 1 スコアセットが返るか（per-run judge になっていないか）。
- DEC-002: `subject_runs` と `judge_runs` の独立性（INV-001）。
- DEC-003: run 配列 + 代表 `response` の後方互換（INV-003）。
- DEC-004: 部分失敗 run の bundled 列挙と judge 続行。
- DEC-005: 上限 5 clamp とコスト線形増の文書化。

## Intent-derived Invariants

- INV-001: judge outer 呼び出し回数は `judge_runs` × judge 数（N 倍にならない）。
- INV-002: bundled builder が holistic multi-task と subject multi-run を混同しない。
- INV-003: `subject_runs=1` は新 field 除き従来 schema と意味同等。

## Risk Assessment

- Risk level: High
- Risk rationale: 評価意味論変更（judge が見る evidence 構造の変更）、被験 API コスト・
  所要時間の増加、長回答 × 多 run による judge コンテキスト上限。
- Regression risk: `subject_runs=1` でもプロンプト・スコアが変わる、旧 JSON 読込失敗。
- Data safety risk: 低。additive schema。既存 run 不変。
- Security / privacy risk: 低。bundled 内容は既存 untrusted envelope 内。
- UX risk: run 別 usage の合算表示ミス、N run 表示の過密。
- Agent misbehavior risk: per-run judge 実装への逸脱、上限未 clamp、失敗 run 黙殺。

## Test Strategy

- Unit: bundled builder、run loop、clamp、エラー混在、prompt 契約静的検証。
- Integration: `BenchmarkEngine.run_task` mock adapter で N 被験 + 1 judge 入力。
- Integration: `server.py` RunRequest 配線、保存 JSON schema。
- Node unit: RunPage / Settings preset、`subject_runs` UI、ResultDetail multi-run 表示。
- Manual QA: 短い task で N=3 run、usage 合算の目視（live API は任意）。
- Validator: backend pytest suite、frontend lint/build、docs validator。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | RunRequest subject_runs | unit | `tests/test_server_frontend.py` | field 受理、default 1 | verified |
| AC-001 | TODO | preset / settings 永続化 | node unit | `frontend/src/lib/executionPresets.node.test.ts` | capture/resolve に subjectRuns | verified |
| AC-001 | TODO | Run UI 入力 | preset + body + review | `executionPresets.node.test.ts` / `client.node.test.ts` + RunPage diff | 1–5 入力・clamp は preset/body。`RunPage.node.test.ts` に subject_runs カバレッジなし | covered |
| AC-002 | DEC-001 | N 被験 + bundled judge 入力 | unit | `tests/test_benchmark_engine.py` | 被験 N 回、judge 1 bundled 文字列 | verified |
| AC-002 | DEC-002 / INV-001 | judge_runs 独立性 | unit | `tests/test_benchmark_engine.py` | judge 呼び出し = judge_runs × judges | verified |
| AC-002 | DEC-004 | エラー混在 run | unit | `tests/test_benchmark_engine.py` | 成功 run ありで judge 続行、[ERROR] 列挙 | verified |
| AC-003 | DEC-001 | 複数出力プロンプト契約 | static unit | `tests/test_prompt_contracts.py` | system/rubric に multi-run 指示 | verified |
| AC-003 | INV-003 | subject_runs=1 後方互換 | unit | `tests/test_benchmark_engine.py` | bundled が単一 run 相当 | verified |
| AC-004 | DEC-003 | 保存 schema subject_runs 配列 | integration | `tests/test_result_storage.py` | run 別 response/usage 保存 | verified |
| AC-004 | TODO | ResultDetail multi-run 表示 | convert + review | `frontend/src/api/client.node.test.ts`（`subjectRuns` map）+ ResultDetail diff | N run 表示は convert 契約と UI code review。`ResultDetail.node.test.ts` は空 `subjectRuns` fixture のみで multi-run assert なし | covered |
| AC-004 | TODO | usage 合算 | unit | `tests/test_cost_estimator.py`（`test_summarize_subject_usage_prefers_subject_runs_array`） | subject_runs[] 優先で usage 合算 | verified |
| AC-005 | DEC-005 | 上限 clamp | unit | server + frontend tests | subject_runs > 5 → 5 | verified |
| AC-005 | Survey | コンテキスト長 sanity | unit | bundled builder fixture | 極端長でも builder 例外なし | verified |
| INV-002 | DEC-001 | holistic vs subject builder 分離 | unit | `tests/test_benchmark_engine.py` | 関数/分岐が混同しない | verified |
| AC-001--005 | Plan | 回帰安全 | regression | `uv run pytest` | backend suite pass | verified |
| AC-001--005 | Plan | frontend 型安全 | lint/build | `npm run lint --prefix frontend`, `npm run build --prefix frontend` | pass | verified |
| AC-001--005 | Plan | docs contract | validator | `./scripts/check-docs.sh` | pass | verified |

## Manual QA Checklist

- [ ] `subject_runs=1` で従来 run と同等に完了する。
- [ ] `subject_runs=3` で被験 progress が 3 回分見える（またはメッセージで識別可能）。
- [ ] 結果画面に run #1..#N の回答が表示される。
- [ ] usage / 推定コストが run 数に応じて増える。
- [ ] 1 run だけ `[ERROR]` の混在ケースで judge が実行され、bundled に ERROR が含まれる。

## Regression Checklist

- [ ] holistic `run_holistic_task` / `_build_bundled_responses` が回帰しない。
- [ ] `judge_runs` preset / strict mode 検証が壊れない。
- [ ] tool trace task で run 別 trace が保存される。
- [ ] 旧結果 JSON（`subject_runs` なし）が単一 response として表示される。

## High-risk Checklist

- [ ] Rollback or recovery path is documented（Plan Deployment / Intent Rollback）。
- [ ] Data safety has been checked（additive schema、旧 run 読取）。
- [ ] Security / privacy implications have been checked（untrusted envelope 維持）。
- [ ] Failure mode is understood（全 run 失敗、context 上限、コスト N 倍）。

## Out of Scope

- live judge API smoke（外部モデル依存）。
- best-of / per-run judge average モード。
- 動的コンテキスト分割・truncate。
- strict mode hash への subject run 取込（未決時は現状維持）。

## Open Questions

- ~~strict mode が `subject_runs > 1` を許可するか~~ → 初版は許可（独立ノブ）。strict preset に `subject_runs` 固定は含めない。
