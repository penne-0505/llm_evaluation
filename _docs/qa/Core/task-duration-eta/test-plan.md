---
title: "QA Test Plan: Task duration estimates and ETA on results"
status: active
draft_status: n/a
qa_schema: 2
qa_status: in-progress
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/plan/Core/task-duration-eta/plan.md"
  - "_docs/intent/Core/task-duration-eta/decision.md"
  - "_docs/archives/survey/Core/task-duration-eta/survey.md"
  - "_docs/qa/Core/task-duration-eta/verification.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Task duration estimates and ETA on results

## Source of Intent

- `_docs/intent/Core/task-duration-eta/decision.md`

## Decision Review Scope

- `DEC-001`: `task_timing` が subject / judge 内訳として保存 JSON の正典になっていること。
- `DEC-002`: ETA が完了タスク実測平均を優先し、不足時のみ step 比率フォールバックすること。
- `DEC-003`: fallback / unavailable 時に誤った確定値表示をしないこと。

## Quality Goal

実行中および結果画面で、タスク単位の所要時間内訳と残り時間予測が一貫した定義で表示され、
初回実行や実測不足時に誤解を招く確定値を示さない。

## Acceptance Criteria

- AC-001: 各通常タスク完了時に、被験 LLM 呼び出しと judge 評価それぞれの `duration_ms` が
  タスク結果 JSON に永続化される（run 全体の `execution_duration_ms` のみに依存しない）。
- AC-002: 実行中の進捗 UI（SSE progress）で、完了済みタスクの実測に基づく残り時間見積もり（ETA）
  が表示される。
- AC-003: 結果詳細画面で、タスクごとの所要時間目安（被検 / judge 内訳）が表示される。
- AC-004: 過去 run の実測データが存在しない初回実行では、ETA が「推定不可」または step ベースの
  フォールバック表示となり、誤った確定値を示さない。

## Intent-derived Invariants

None

## Risk Assessment

- Medium: 保存 JSON schema 追加と SSE payload 拡張の不一致は、run 自体は成功しても timing /
  ETA を誤表示する。
- Medium: multi-turn subject や parallel judge fixture 不足では `task_timing` 集計が実運用と
  ずれる。
- Out of scope: 外部 LLM API の live latency、時間 ROI 算出式（Enhance-41）、包括評価 judge
  入力の truncation。

## Test Strategy

- Python unit test で `TaskResult.to_dict()`、`task_timing` 集計、`_merge_subject_usage` の
  duration 合算、保存 JSON round-trip を確認する。
- Python unit test で progress ETA builder（measured / step fallback / unavailable）を確認する。
- Node test で `client.ts` の task timing 変換と RunPage ETA 表示 helper を確認する。
- Component / review で `ResultDetail` の per-task duration 表示を確認する。
- frontend lint/build、backend pytest、docs validator を実行する。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | subject / judge duration_ms を task JSON に永続化 | unit | `uv run pytest tests/test_benchmark_engine.py tests/test_result_storage.py` | `task_timing` が subject / judge 内訳を保持し round-trip 成功 | verified |
| AC-001 | DEC-001 | multi-turn subject duration 合算 | unit | `uv run pytest tests/test_benchmark_engine.py` | `_merge_subject_usage` が duration_ms を合算 | verified |
| AC-002 | TODO | SSE progress に実測ベース ETA | unit | `uv run pytest tests/test_server_frontend.py` | progress payload に ETA と status が含まれる | verified |
| AC-002 | DEC-002 | 完了タスク平均 × 残タスクの ETA | unit | ETA helper test（server または frontend） | 残タスク数と平均 ms が一致 | verified |
| AC-003 | TODO | ResultDetail per-task duration 表示 | node unit + review | `frontend/src/components/ResultDetail.tsx` diff / node test | 被検 / judge 内訳がタスクカードに表示 | verified |
| AC-003 | TODO | client 変換で task timing を保持 | node unit | `npx --prefix frontend tsx --test frontend/src/api/client.node.test.ts` | converted task に timing field がある | verified |
| AC-004 | TODO | 初回実行 ETA フォールバック | unit | ETA helper test | 完了 0 件で measured ETA なし、step または unavailable | verified |
| AC-004 | DEC-003 | 確定値風表示を禁止 | review + unit | RunPage / ETA helper | `eta_status` またはラベルで推定種別が区別される | verified |
| DEC-001 | Intent | usage 集計との整合 | unit | `uv run pytest tests/test_cost_estimator.py` | task 合算が usage `total_duration_ms` と一致（同一 fixture） | verified |
| DEC-002 | Intent | step 比率は measured 不可時のみ | unit | ETA helper test | 完了 1 件以上で step 比率に切り替わらない | verified |
| AC-001--004 | Plan | regression safety | lint/build | `npm run lint --prefix frontend` / `npm run build --prefix frontend` / `uv run pytest` | typecheck、build、backend suite success | verified |

## Manual QA Checklist

- [ ] 通常 run 実行中、1 タスク完了後に ETA が更新される。
- [ ] 初回（完了 0 件）では「推定不可」または step ベース表示であり、確定値風ラベルがない。
- [ ] 結果詳細で各タスクの被検 / judge 所要時間が読める。
- [ ] 旧フォーマット result（`task_timing` 欠落）を開いてもクラッシュしない。

## Regression Checklist

- [ ] 既存 SSE progress の lane 集計（holistic 分離含む）が変わらない。
- [ ] `execution_duration_ms` の保存と summary index が維持される。
- [ ] usage_summary / cost 表示が本変更だけでは退行しない。

## Out of Scope

- ダッシュボード時間 ROI（`Core-Enhance-41`）。
- 過去 run 横断の ETA 学習。
- adapter の計測方式変更。

## Open Questions

None。
