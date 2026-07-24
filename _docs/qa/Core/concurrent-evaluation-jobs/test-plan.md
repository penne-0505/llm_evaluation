---
title: "QA Test Plan: Concurrent evaluation jobs with provider rate limits"
status: active
draft_status: n/a
qa_schema: 2
qa_status: in-progress
risk: High
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/plan/Core/concurrent-evaluation-jobs/plan.md"
  - "_docs/intent/Core/concurrent-evaluation-jobs/decision.md"
  - "_docs/qa/Core/concurrent-evaluation-jobs/verification.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Concurrent evaluation jobs with provider rate limits

## Source of Intent

- `_docs/intent/Core/concurrent-evaluation-jobs/decision.md`

## Decision Review Scope

- `DEC-001`: ジョブ同時上限 3 のサーバ強制。
- `DEC-002`: 進行ボード一式＝1 ジョブの縦積みとジョブ単位キャンセル。
- `DEC-003`: プロセス共有・プロバイダ ID キーのレート制限。
- `DEC-004`: Settings 編集可能 + 推奨デフォルト / 未知は保守的既定。
- `DEC-005`: レート待ちのキャンセル可能性と無言ハング回避。

## Quality Goal

設定違いの評価を最大 3 本まで同時に観測・操作でき、同一プロバイダへの発行が Settings で
定めた窓内上限を超えない。1 ジョブ時の既存体験を壊さない。

## Acceptance Criteria

- AC-001: 最大 3 本まで設定違いの評価を同時起動でき、4 本目はサーバが拒否する。
- AC-002: Run 画面で各ジョブが進行ボード一式として縦積み表示され、個別キャンセルできる。
- AC-003: 全ジョブの LLM 呼び出しがプロバイダ別レート制限を共有し、窓内上限を超えて発行しない。
- AC-004: Settings でプロバイダごとに制限を編集・保存でき、未設定時は推奨デフォルトが効く。
- AC-005: ジョブ 1 本のみのとき、進行ボード体験は現行と同等である。

## Intent-derived Invariants

- INV-001 (from DEC-001): 同一プロセスで同時に `running` な評価ジョブは最大 3 本である。
- INV-002 (from DEC-003): 評価ジョブの LLM 完了呼び出しは共有リミッタを経由する。
- INV-003 (from DEC-004): 未上書きプロバイダは推奨デフォルトまたは保守的既定が適用され、暗黙の無制限にならない。

## Risk Assessment

- High: 同時 3 本で制限を共有しないと 429 / コスト急増が起きる。
- High: サーバ未強制だとフロント迂回で 4 本目が立つ。
- Medium: multi-job UI で単一ジョブの進捗・キャンセル・完了導線が壊れる。
- Medium: レート待ちがキャンセル不能または無言ハングに見える。
- Low: 推奨デフォルトが厳しすぎて体感が遅い（Settings で緩和可能）。

## Test Strategy

- リミッタを fake clock / 決定的 fixture で unit し、窓内カウントと待ち解除を検証する。
- active run registry の 3 本成功・4 本目拒否を API / server test で検証する。
- Settings 保存・読込・デフォルト適用を API test で検証する。
- multi-job store と縦積み・個別キャンセルを frontend node test + Manual QA で確認する。
- 1 ジョブ回帰は既存 runStore / RunPage 相当のテストと Manual QA で確認する。
- High-risk: キャンセル中のレート待ち中断、同一 provider を使う 2 ジョブの直列化待ち。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | 同時 3 / 4 本目拒否 | API / unit | server または registry test | 3 本 active 可、4 本目 4xx | verified |
| AC-002 | TODO | 縦積み・個別キャンセル | node + manual | multi-job store / RunPage | ジョブ単位 UI と cancel | covered |
| AC-003 | TODO | 共有レート制限 | unit | rate limiter test | 窓内上限超過なし。2 ジョブ共有 | verified |
| AC-004 | TODO | Settings + デフォルト | API + node | settings API / UI | 保存反映、未設定は default | verified |
| AC-005 | TODO | 1 ジョブ回帰 | node + manual | RunPage / store | 単一ボード体験維持 | covered |
| INV-001 | Intent | running ≤ 3 | API / unit | registry test | サーバ保証 | verified |
| INV-002 | Intent | 呼び出しがリミッタ経由 | unit + review | adapter / engine hook test | 評価経路に acquire | verified |
| INV-003 | Intent | 無制限にならない | unit | default table test | builtin / unknown に既定 | verified |

## Manual QA Checklist

- [ ] 設定の違うジョブを 2〜3 本起動し、縦積みボードでそれぞれ進捗が見える。
- [ ] 1 本だけキャンセルし、他ジョブが継続する。
- [ ] 4 本目起動が UI と API の両方で拒否される。
- [ ] 同一プロバイダを使う 2 ジョブで、体感として発行が間引かれる（または待ち表示が出る）。
- [ ] Settings で窓を厳しくして待ちが増え、緩めて待ちが減る。
- [ ] 推奨デフォルトへリセットできる（UI にある場合）。
- [ ] ジョブ 1 本だけ回したとき、旧来の進行ボード操作感が維持される。

## High-risk Checklist

- [ ] レート待ち中にキャンセルすると待ちが解除され、ジョブが cancelled になる。
- [ ] リミッタ未適用の評価呼び出し経路がレビューで残っていない。
- [ ] 制限設定を極端な値（1 req / 60s）にしてもプロセスが死なず、操作で戻せる。
- [ ] 結果 JSON / run_id 衝突が同時完了でも起きない（data safety）。
- [ ] レート制限設定ファイルに API キー等の secret を混ぜない（security）。
- [ ] rollback: registry / limiter / multi-job UI / Settings 永続を外すと単一ジョブ体験に戻る。
- [ ] recovery: 4 本目拒否やレート待ち後も、既存ジョブのキャンセル・完了・再起動ができる。

## Regression Checklist

- [ ] 既存の task 並列・judge pacing・holistic progress が 1 ジョブで動作する。
- [ ] `subject_runs` / `judge_runs` / strict mode 開始条件が壊れていない。
- [ ] Layout の実行中インジケータが少なくとも 1 ジョブ実行中を示せる。
- [ ] `./scripts/check-docs.sh` と frontend lint/build、関連 pytest が通る。

## Out of Scope

- 永続キュー、再起動復帰、タブ間分散ロック。
- 実プロバイダの公式 RPM との完全一致保証。
- UI-Feat-61 presence 演出の新規要件。

## Open Questions

- None（推奨デフォルト初版数値は verification に記録済み）。
