---
title: "QA Test Plan: Exclude unreliable judges from aggregate score"
status: active
draft_status: n/a
qa_schema: 2
qa_status: planned
risk: Medium
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/survey/Core/exclude-unreliable-judges/survey.md"
  - "_docs/archives/plan/Core/exclude-unreliable-judges/plan.md"
  - "_docs/intent/Core/exclude-unreliable-judges/decision.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Exclude unreliable judges from aggregate score

## Source of Intent

- TODO: Core-Feat-43
- Plan: `_docs/archives/plan/Core/exclude-unreliable-judges/plan.md`
- Intent: `_docs/intent/Core/exclude-unreliable-judges/decision.md`
- Survey: `_docs/archives/survey/Core/exclude-unreliable-judges/survey.md`

## Quality Goal

toggle OFF 時は現行と同一の hero スコアを維持し、toggle ON 時は定義済み信頼性基準に該当する
judge 系統を横断集計から除外する。除外理由と除外前後スコアが結果 UI で追跡でき、全除外時は
N/A を返す。保存済み run の toggle 状態と集計が再表示で一貫する。

## Acceptance Criteria

- AC-001: 実行設定または結果表示に toggle（`runHolistic` 同型 ON/OFF）があり、OFF 時は現行どおり
  全 judge 系統を平均に含める。
- AC-002: ON 時、定義済み基準（SD > 5、低信頼、critical fail、cross-judge 乖離）に該当する
  judge 系統を `average_score` / `best_score` およびタスク横断サマリーから除外する。
- AC-003: 除外 judge 系統・理由・除外前後スコアが結果詳細で確認できる。
- AC-004: 全 judge 除外時、スコア N/A と警告。サイレント 0 点や空平均を出さない。
- AC-005: 保存済み run 再表示で toggle 状態と再計算結果が一貫する。

## Decision Review Scope

- DEC-001: 除外粒度が judge 系統全体であり UI flags と一致するか。
- DEC-002: 理由コードと閾値が単一モジュールに集約されているか。
- DEC-003: toggle が run 時確定 + JSON 保存されているか。
- DEC-004: 全除外時 null / N/A 契約が backend / frontend 両方で守られるか。

## Intent-derived Invariants

- INV-001: 除外 ON で有効 judge スコア 0 件 → hero スコアは null（N/A）。
- INV-002: 除外条件の正典は backend。frontend は理由表示のみ。

## Risk Assessment

- Risk level: Medium
- Risk rationale: 集計ロジック変更により hero スコアとダッシュボード比較が変わるが、
  judge 実行・採点意味論は変えない。
- Regression risk: toggle OFF でもスコアが変わる、旧 JSON 読込失敗。
- Data safety risk: 低。additive field のみ。既存 run 削除なし。
- Security / privacy risk: なし。
- UX risk: 除外理由が flags と矛盾、N/A 表示が不明瞭。
- Agent misbehavior risk: 閾値の二重定義、全除外時 0 返却、cross-judge 未実装のまま AC 充足と誤認。

## Test Strategy

- Unit: `judge_reliability` モジュール、集計関数、全除外 N/A、toggle OFF 回帰。
- Integration: `server.py` run 保存 JSON に `exclude_unreliable_judges` / `score_aggregation`。
- Node unit: ResultDetail toggle 表示、除外理由、N/A hero。
- Manual QA: 代表 run で flags 付き judge を除外し hero が変わることを目視。
- Validator: `./scripts/check-docs.sh`、`npx markdownlint-cli2`。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | toggle OFF で現行平均 | unit | `uv run pytest tests/test_judge_reliability.py` | OFF 時全 judge mean が従来と一致 | verified |
| AC-001 | TODO | Run / Result toggle UI | node unit + review | `frontend/src/pages/RunPage.node.test.ts`, ResultDetail diff | toggle 操作可能、default OFF | verified |
| AC-002 | DEC-002 | high_variance 除外 | unit | `tests/test_judge_reliability.py` | SD > 5 の judge 系統が除外 | verified |
| AC-002 | DEC-002 | low_confidence / critical_fail 除外 | unit | `tests/test_judge_reliability.py` | 各理由コードで除外 | verified |
| AC-002 | DEC-002 | cross_judge_divergence 除外 | unit | `tests/test_judge_reliability.py` | 同一 task range > 15 で該当 judge フラグ | verified |
| AC-002 | TODO | server average_score / best_score | integration | `tests/test_server_frontend.py` | 除外後 hero スコアが期待値 | verified |
| AC-003 | TODO | 除外理由・前後スコア表示 | node unit | `frontend/src/components/ResultDetail.node.test.ts` | 理由文字列と before/after | verified |
| AC-003 | INV-002 | flags と理由コード整合 | unit + review | `computeReviewFlags` vs backend mapper | 同一条件で同系統が flagged / excluded | verified |
| AC-004 | DEC-004 / INV-001 | 全除外 N/A | unit | `tests/test_judge_reliability.py` | null スコア、0 非返却 | verified |
| AC-004 | INV-001 | frontend N/A 表示 | node unit | ResultDetail test | hero が `—` / N/A + 警告 | verified |
| AC-005 | DEC-003 | 保存 toggle 再現 | integration | `tests/test_result_storage.py` | JSON `exclude_unreliable_judges` 読込一致 | verified |
| AC-001--005 | Plan | 型・lint 回帰 | lint/build | `npm run lint --prefix frontend`, `npm run build --prefix frontend` | pass | verified |
| AC-001--005 | Plan | docs contract | validator | `./scripts/check-docs.sh` | pass | verified |

## Manual QA Checklist

- [ ] toggle OFF で既存 run の hero スコアが変わらない。
- [ ] toggle ON で flags 付き judge 系統が横断サマリーから消える。
- [ ] 除外 judge 名と理由（ばらつき / 低信頼 / CF / 乖離）が読める。
- [ ] 除外前後の average が並記される。
- [ ] 全 judge 除外 run で hero が N/A かつ警告が出る。

## Regression Checklist

- [ ] `computeReviewFlags` の既存警告が toggle OFF 時も表示される。
- [ ] holistic task が hero 平均に含まれない（現行維持）。
- [ ] `ResultAggregator.aggregate` の per-judge run 集計が変わらない。
- [ ] 旧 JSON（toggle フィールドなし）が OFF として読める。

## High-risk Checklist

Risk Medium のため対象外。

## Out of Scope

- judge プロンプト変更、再採点、ML 信頼性推定。
- 除外 judge の task 別詳細の非表示。
- 動的閾値チューニング UI。

## Open Questions

None。
