---
title: "Plan: Run presence observation"
status: active
draft_status: n/a
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/UI/run-presence-observation/decision.md"
  - "_docs/qa/UI/run-presence-observation/test-plan.md"
related_issues: []
related_prs: []
---

# Plan: Run presence observation

## Overview

実行中の Run 画面は進行ボードとして状態は伝わるが、フェーズ間の待ちが静止し、
観察する対象が薄い。本変更は raw ログや途中の具体点を出さず、active な評価まわりに
「緊張（滞留）」と「変化の向き（直近差分）」の二チャンネルを置き、異常時だけ数値で
割込む。待ちの体験を「結果が立ち上がる手前の観察」にする。

## Scope

- RunPage の実行中レーン（active task card / 稼働中 judge セグメント）に局所 presence を追加する。
- 緊張チャンネル: 現在の呼び出し滞留時間に応じて気配が張り詰める（時間の話であり点の良し悪しではない）。
- 変化の向きチャンネル: 採点確定の拍で rising / falling / unsettled の短い反応だけを出す。絶対水準は出さない。
- 異常割込み: 実行失敗と、0 点偏りなどの極端な崩壊だけ数値・率直文言で表示する。
- 変化の向きと異常判定のため、progress SSE に UI 非表示の採点シグナル（内部用）を additive に載せる。
- 既存進行ボード（待機 / 実行中 / 完了レーン、ETA、包括評価カード）は土台として残す。
- unit / node test、frontend lint/build、docs validator、必要な backend test を追加・更新する。

## Non-Goals

- raw reasoning / subject 出力のストリーミング表示。
- 途中の具体スコア、暫定平均、絶対的な良し悪し帯（順調 / 厳しい等）の常時表示。
- ミニゲームや、観察と無関係な暇つぶし UI。
- 完了後の結果画面（CountUp 等）の再設計。
- SSE 再接続、run キャンセル意味論、評価 engine の採点方式変更。

## Requirements

- 通常ラン中、active カードは緊張と変化の向きの二チャンネルを同時に持てる。両チャンネルは視覚語彙を共有しない。
- subject フェーズ（採点前）は緊張のみ。変化の向きは最初の採点確定以降に有効化する。
- 画面上に途中の具体点・暫定平均を出さない。内部シグナルは store / helper に閉じる。
- 失敗（error / timeout 相当の task / judge failure）と極端な 0 点偏りだけが数値割込みを起こす。
- `prefers-reduced-motion` では連続アニメを止め、静的な密度・向きインジケータへ落とす。
- 進行ボードの lane 集計・包括評価 dedicated 表示を壊さない。

## Expression Technique (自己レビュー反映)

初稿の語彙を現行 Run UI（amber pulse、pipeline bar、scroll lane）と照合し、衝突と誤読を潰した版。

### 自己レビューで捨てた案

1. **緊張の主軸を「opacity 点滅の高速化」にすること** — 既存 `pulse-amber` の延長で周期だけ
   短くすると、アラート／障害の点滅に読める。長い待ち＝悪い、へ滑る。
2. **カード全体の `translateY` で rising/falling** — レーン内スクロールと競合し、並べ替えに見える。
3. **緊張の「縮む」と falling の「締まる」を同じ変形で兼ねること** — 高緊張と得点下降が区別できない。
4. **向きに score-high / score-low 色を使うこと** — 絶対水準の漏洩そのもの。
5. **judge セグメントごとに独立した緊張パルス** — 並列時にノイズ化し、どの待ちが主か分からない。

### チャンネル分離（必須）

| チャンネル | DOM ターゲット | 変形・材質 | 時間構造 |
| --- | --- | --- | --- |
| 緊張 | カードの inset 圧力 + **いま最長の active セグメント 1 本** | inset shadow、segment の scaleY / 呼吸。色相は amber 系のみ | 継続。ステージは CSS transition で割込可能 |
| 変化の向き | カード内の **専用 presence motif**（細いレール or 針。pipeline とは別要素） | motif のみ `translateY` / `scale` / `translateX`。カードや lane は動かさない | 単発 420–650ms。新拍は旧拍を置換（キューしない） |
| 異常 | カード下部バナー（既存 error 語彙） | score-low / danger はここだけ可 | 持続。向き拍より文言を優先 |

### 緊張ステージ（継続音）

メタファーは「息が浅くなる点滅」ではなく **ばねが巻かれて動きが小さくなる**。

| ステージ | 滞留 | 表現 |
| --- | --- | --- |
| T0 calm | 0–4s | active セグメントのみ、現行に近い緩い呼吸（周期 ≈ 2.0s、opacity 振幅は控えめ） |
| T1 coiled | 4–14s | 周期はほぼ維持。inset 圧力を追加。segment の scaleY をわずかに圧縮（例: 1 → 0.92） |
| T2 taut | 14–28s | 呼吸振幅をさらに小さく（動かない方向へ）。inset を一段強く。glow は amber-glow の範囲内 |
| T3 held | 28s+ | **脈動を止め**、圧縮と inset を保持した静止緊張。高原でも赤へ行かない |

実装メモ:

- ステージ遷移は keyframes 連打ではなく、CSS 変数（`--tension-inset`, `--tension-scale`, `--tension-period`）への transition（≈ 400ms、`cubic-bezier(0.2, 0, 0, 1)`）。
- カード内に active が複数あっても、緊張は **最長滞留の 1 セグメント** にだけ乗せる。他の running は静止 amber。
- Loader2 の spin（レーン見出し）は現状維持。presence と役割が違うので競合とみなさない。

### 変化の向き（確定の拍）

motif は pipeline bar の直上またはカード右縁の 2–3px レール。普段は低 opacity。拍のときだけ動く。

| 状態 | 動き | 長さ | 備考 |
| --- | --- | --- | --- |
| rising | motif が `translateY(-3px)` + `scale(1.06)`、ease-out | ≈ 480ms | 色は amber / text-primary。緑にしない |
| falling | motif が `translateY(3px)` + `scale(0.94)` | ≈ 480ms | 緊張の scaleY 圧縮より変位を明確に「下方向」へ。赤にしない |
| unsettled | motif が `translateX` ±2px を 2 往復 | ≈ 640ms | 必要なら ice を 1 拍だけ混色可。score 色は禁止 |

向きの算出（表示は enum のみ）:

- 直近確定スコアと、その直前の確定スコア（同一 run・同一カード優先、なければ run 全体の直近）の差分符号。
- rising / falling: 符号が明確で、直近 3 件が同符号、または |Δ| が小さいノイズ帯を超える。
- unsettled: 直近 3 件の符号が混在、またはばらつきが急増。
- ヒステリシス: 1 件だけの微差では向きを出さず、motif を短く flash（neutral tick）してもよい。neutral tick は上下しない。

連打: judge が連続完了しても **最新 1 拍だけ**再生。進行中の拍は `motion` で中断して置換（bounce: 0）。

### 異常割込み

- 失敗: 既存の `score-low` チップ／文言。件数を出す。
- 崩壊: settled のうち 0 点が過半でバナー「0点が N/M 件」。カード内、向き motif より下。
- 割込み中: 向き拍は抑制可。緊張（T-stage）は継続してよい（時間チャンネルのため）。

### reduced-motion

- 緊張: 脈動なし。T-stage に応じた静的 inset / scaleY のみ。
- 向き: 移動なし。motif の opacity クロスフェード、または ↑ ↓ ≈ の静的グリフを ≈ 1.2s 表示。
- 異常: アニメ不要。バナー即時表示。

### 既存トークンとの関係

- 使う: `--color-amber*`, `--color-amber-glow`, `--color-ice`（unsettled 限定）、既存 border / surface。
- 使わない（緊張・向き）: `--color-score-high`, `--color-score-low`, `.glow-high/mid/low`。
- 完了時 CountUp / score glow は結果画面のまま。実行中 presence とは語彙を共有しない。

## Tasks

1. progress snapshot に内部用採点シグナルと、緊張用の phase / call 開始時刻を additive で載せる。
2. frontend に緊張ステージ・変化向き・異常判定の helper を置き、数値を UI に漏らさない。
3. `ActiveTaskCard` に inset / segment 緊張、専用 motif の向き拍、異常バナーを接続する。
4. CSS 変数 transition + `motion` 単発拍、reduced-motion フォールバックを追加する。
5. helper / store / snapshot のテストと Manual QA 項目を満たす。

## QA Plan

- Risk: Medium。誤読（長い待ち＝低得点、向き＝絶対水準、緊張圧縮＝falling）と途中点数の漏洩が主リスク。
- AC は helper の決定的分岐、SSE / store の非表示シグナル、RunPage 差分レビュー、reduced-motion、Manual QA で確認する。
- 影響 DEC は verification で Why / Change freedom に対して review する。

## Deployment / Rollout

- bundled frontend + additive SSE fields。旧 frontend は未知 field を無視できる。
- rollback は presence UI と内部シグナル field を戻す。保存 JSON schema の破壊的変更は行わない。
