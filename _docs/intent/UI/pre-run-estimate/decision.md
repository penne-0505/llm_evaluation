---
title: "Intent: Pre-run cost and duration estimate"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/plan/UI/pre-run-estimate/plan.md"
  - "_docs/qa/UI/pre-run-estimate/test-plan.md"
related_issues: []
related_prs: []
---

# Intent: Pre-run cost and duration estimate

## Context

結果画面には事後の推定コストがあり、実行中には残り ETA があるが、開始前に
「この設定でいくら・何分かかりそうか」を見る手段が無い。利用者は履歴があればそれを
信じたいが、タスク数や judge 構成が少し違うだけでも再計算の補助が欲しい。

## Decisions

### DEC-001: 履歴マッチは被検モデル一致を必須とし、タスク数・judge 数で近傍を選ぶ

- **What**: 候補は `subjectModelId`（または free-text と同等の id/name）が一致する過去 run
  に限る。その中で `|ΔtaskCount| + 2·|ΔjudgeCount|` が最小のものを採り、同点なら新しい方。
- **Why**: 被検が違うと単価・速度が入れ替わり見積の意味が壊れる。judge 集合の id は
  summary に無いため、judge 数で近似する。
- **Change freedom**: 距離の重み、同点タイブレークは変更できる。
- **Why not**: タスクセット完全一致必須にすると当たりが極端に減る。
- **Revisit when**: summary に judge id 集合や subject/judge run 回数が載った時。

### DEC-002: 所要見積の正典は wall-clock（待ち時間）

- **What**: 履歴所要は `executionDurationMs` を使う。処理時間合算（`timing_summary`）は
  使わない。
- **Why**: 開始前に知りたいのは「押してから終わるまで」であり、時間 ROI の処理時間定義とは
  別質問。
- **Change freedom**: 表示フォーマットは既存 duration formatter を再利用してよい。
- **Why not**: 処理時間合算は並列で wall-clock より長く、待ち感とずれる。

### DEC-003: 構成差は負荷ユニット比で補正し、履歴を主・構成を補助とする

- **What**:
  - 負荷 `L = taskCount × (subjectRunCount + judgeCount × judgeRunCount)`。
  - 履歴側の run 回数は summary に無いため **各 1** と仮定する
    （`L_hist = taskCount_h × (1 + judgeCount_h)`）。
  - `|log10(L_plan / L_hist)|` が閾値を超える、または task/judge 数が一致しないとき
    `value × (L_plan / L_hist)` を適用し source を `history_scaled` とする。
  - 一致十分なら source `history`。
- **Why**: 履歴を主に保ちつつ、構成だけ変えたときの過大／過小を緩和する。
- **Change freedom**: 閾値、judgeRun の扱い、補正をコスト／時間の片方だけにするかは変更可。
- **Why not**: タスクごと ROI 平均のような再定義は開始前 UX を複雑にする。

### DEC-004: 履歴無しは所要のみ粗い構成ヒューリスティック、コストは 0 埋めしない

- **What**: 被検一致履歴が無いとき、所要は `totalSteps × ASSUMED_MS_PER_STEP` の
  `heuristic`。コストはフロントに単価カタログが無いため `unavailable`（N/A）。
- **Why**: 誤った $0 はクレジット判断を誤らせる。待ち時間のオーダー感だけでも価値がある。
- **Change freedom**: step あたり ms、将来の単価 API 接続は可。
- **Revisit when**: モデル単価を frontend で安全に参照できるようになった時。

### DEC-005: 表示は idle の実行前に限定し、確度ラベルを必ず添える

- **What**: RunPage `status === 'idle'` のチェックリスト近傍に見積を出す。
  ラベルは履歴 / 履歴+構成補正 / 粗い推定 / 不明。
- **Why**: 実行中 ETA・事後コストと役割が違うことを明示するため。
- **Change freedom**: カードレイアウト、文言は変更できる。

## Consequences / Impact

- 初回被検や LM Studio（価格 none）ではコスト N/A が多くなる（意図的）。
- 履歴の judge_runs≠1 のとき補正がずれる（summary 制約）。

## Quality Implications

- マッチ・補正・ヒューリスティックを unit test する。
- 0 埋め禁止をテストする。

## Intent-derived Invariants

- INV-001 (from DEC-004): コスト見積が不明なとき数値 0 を推定成功として表示してはならない。

## Rollback / Follow-ups

- UI カードと helper を除去すればロールバック可能。
- follow-up: summary への run 回数・judge id・並列フラグ追記、単価カタログ接続。
