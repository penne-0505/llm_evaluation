---
title: "Survey: Exclude unreliable judges from aggregate score"
status: archived
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "TODO.md"
  - "_docs/archives/plan/Core/exclude-unreliable-judges/plan.md"
related_issues: []
related_prs: []
---

# Survey: Exclude unreliable judges from aggregate score

## Background

Core-Feat-43 は、ばらつき・低信頼・judge 間乖離などで信頼性が低い judge 系統を総合得点から
除外する toggle を追加する。Inbox 由来の要望であり、現状は警告表示のみで集計へは反映されない。

調査対象:

- `core/result_aggregator.py` — 単一 judge 内集計と cross-judge 警告
- `server.py` — `average_score` / `best_score` 算出
- `frontend/src/components/ResultDetail.tsx` — `computeReviewFlags` と横断サマリー

## Objective

1. 既存の信頼性シグナルがどこまで実装されているかを特定する。
2. 除外 toggle を backend 集計と frontend 表示のどちらに置くべきか、永続化の制約を整理する。
3. cross-judge 乖離の判定が現行コードに存在するか確認する。

## Method

- 2026-07-23 時点の `core/result_aggregator.py`、`server.py`（L1511–1528）、
  `ResultDetail.tsx`（`computeJudgeSummaries` / `computeReviewFlags`）を静的読解。
- holistic の `runHolistic` toggle（RunPage / settings store）を UI 先例として参照。
- TODO AC-001〜005 と照合。

## Results

### `ResultAggregator.aggregate`

- 単一 judge × 単一 task の `judge_runs` 結果を集計する。
- 出力 `aggregated` に `total_score_mean`、`total_score_std`、`critical_fail`、
  `confidence_distribution` を含む。
- 無効 run は `_is_valid_run` で除外されるが、judge 系統自体の除外は行わない。

### `ResultAggregator.aggregate_all_judges`

- judge ファミリー横断の `by_judge` サマリーと `cross_judge` 警告を返す。
- 警告条件（backend 固定閾値）:
  - `total_score_std > 5` → `score_variance_warnings`
  - `confidence_distribution.low > 0` → `low_confidence_tasks`
  - `critical_fail == True` → `critical_fail_tasks`
- **集計から judge を除外する処理はない。** 警告リストの生成のみ。

### `server.py` の `average_score` / `best_score`

```python
# completed tasks × judge families の total_score_mean を単純平均
for task_data in completed:
    for judge_result in jr.values():
        agg = judge_result.get("aggregated")
        if agg:
            ts = agg.get("total_score_mean", 0)
            if ts:
                all_total_scores.append(float(ts))
benchmark_result["average_score"] = round(sum(...) / len(...), 1) if ... else 0
benchmark_result["best_score"] = round(max(...), 1) if ... else 0
```

- holistic task は `completed` ではなく `holistic_results` 側のため、現行の hero スコアには含まれない
  （既存挙動）。
- 信頼性フィルタなし。`ts == 0` は falsy 判定で平均から落ちるが、これは「全除外時 N/A」とは別問題。
- 保存 JSON に toggle 状態や除外メタデータは存在しない。

### `ResultDetail.tsx` の frontend 側

**`computeReviewFlags`** — task × judge 単位で以下を検出し UI 警告を出す:

| 条件 | 理由文字列 |
| --- | --- |
| `je.totalScore.sd > 5` | ばらつき大（SD …） |
| `je.criticalFail.detected` | 重大な失敗を検出 |
| `je.confidenceDistribution.low > 0` | 低信頼レビュー N 件 |

**`computeJudgeSummaries`** — judge モデル ID ごとに task 横断の単純平均を算出。除外ロジックなし。

**乖離**: frontend/backend で SD 閾値 `> 5` は一致。ただし **judge 間スコア乖離**
（同一 task で judge A と B の mean が大きく離れる）は、現行コードに明示的判定がない。
TODO AC-002 が要求する第 4 条件は新規実装が必要。

### UI toggle 先例

- `runHolistic` は settings store + RunPage toggle + `RunRequest.run_holistic` で run 時に固定。
- 結果画面側の post-hoc 再計算 toggle は先例なし。

## Discussion

### 整合すべき判定軸

| シグナル | backend (`aggregate_all_judges`) | frontend (`computeReviewFlags`) | 除外候補 |
| --- | --- | --- | --- |
| run 内 SD > 5 | task 横断 mean/std ベース | task × judge の sd | 要設計（粒度差あり） |
| low confidence | judge ファミリー単位 | task × judge 単位 | 一致方向 |
| critical fail | judge ファミリー単位 | task × judge 単位 | 一致方向 |
| judge 間乖離 | **未実装** | **未実装** | Intent で閾値定義が必要 |

backend の `aggregate_all_judges` は task を横断した judge ファミリー統計であり、
frontend の flags は task × judge 粒度。除外単位を **judge 系統（モデル ID / ファミリー）**
に統一し、task 内で 1 回でも flag 条件を満たせば系統全体を除外する方針が UI と整合しやすい。

### 永続化の分岐

- **Run 時固定**: `RunRequest` に `exclude_unreliable_judges` を載せ、保存 JSON にも記録。
  再表示は保存値をそのまま使う。AC-005 を満たしやすい。
- **閲覧時再計算**: 生データのみ保存し、toggle は UI 状態。同一 run を OFF/ON 比較できるが、
  デフォルト状態の再現には UI 初期値または run メタデータが必要。

Plan / Intent では run 時固定 + 結果 JSON に toggle と除外メタデータを保存する案を推奨する
（`runHolistic` と同型、再現性が高い）。

### 全除外時

現行 `average_score` は空集合で `0` を返す。AC-004 要求どおり `null` / N/A + 警告へ変更が必要。

## Recommended Actions

1. Intent で除外基準（SD / low confidence / critical fail / cross-judge divergence）と閾値を
   単一モジュールに集約する（`DEC-*`）。
2. `ResultAggregator` に judge 系統除外判定と除外メタデータ生成を追加し、
   `server.py` と frontend が同じ関数を参照する。
3. toggle は run 設定 + 保存 JSON に `exclude_unreliable_judges` と `score_aggregation` メタを載せる。
4. `computeReviewFlags` の理由文字列と除外理由を共通化し、表示の二重定義を避ける。
5. cross-judge 乖離は「同一 task の judge mean の range または std が閾値超」の系統フラグとして新規定義する。
