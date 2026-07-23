---
title: "QA Test Plan: Run presence observation"
status: active
draft_status: n/a
qa_schema: 2
qa_status: planned
risk: Medium
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/plan/UI/run-presence-observation/plan.md"
  - "_docs/intent/UI/run-presence-observation/decision.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Run presence observation

## Source of Intent

- `_docs/intent/UI/run-presence-observation/decision.md`

## Decision Review Scope

- `DEC-001`: presence が active 局所に置かれ、ボードが帰還用地図として残ること。
- `DEC-002`: 緊張と変化の向きが分離し、絶対水準・途中点が常時出ないこと。
- `DEC-003`: 数値割込みが失敗と極端な崩壊に限られること。
- `DEC-004`: 内部シグナルが向き／異常へ畳み込まれ、通常 UI に生スコアが出ないこと。
- `DEC-005`: 緊張と向きが別 DOM／別変形語彙であり、点滅高速化やカード平行移動に頼らないこと。

## Quality Goal

実行中画面が、raw ログや途中点なしで観察可能な presence を持ち、待ちの誤読（長い＝悪い、
向き＝最終水準、緊張圧縮＝falling）と数値漏洩を起こさない。異常時だけ率直な数値割込みがある。

## Acceptance Criteria

- AC-001: active な評価カードに緊張ステージが滞留時間に応じて変わり、score-low 色相や
  opacity 点滅の高速化へ寄せて点の良し悪し／障害を暗示しない。
- AC-002: 採点確定の拍で rising / falling / unsettled のいずれかが専用 motif 上に短く表現され、
  具体点・暫定平均・絶対帯ラベルは出ない。カード全体は平行移動しない。
- AC-003: 実行失敗と、settled における 0 点過半（または Intent で許した同等閾値）のとき
  だけ数値付きの率直表示が出る。
- AC-004: subject フェーズでは変化の向きが発動せず緊張のみである。
- AC-005: `prefers-reduced-motion` で連続アニメに依存せず、静的な密度／向き表示へ落ちる。
- AC-006: 既存の進行ボード lane 集計、ETA、包括評価 dedicated 表示を壊さない。

## Intent-derived Invariants

- INV-001: 通常の実行中 UI 経路に途中の具体スコアまたは暫定平均を表示しない。
- INV-002: 緊張チャンネルを得点の絶対的良し悪し色へ使わない。
- INV-003: 緊張と変化の向きは別 DOM ターゲットに載せ、向きをカード全体の平行移動や緊張と同一の圧縮プロパティだけで表現しない。

## Risk Assessment

- Medium: 視覚語彙の混線で「待ちの長さ＝低得点」「向き＝最終点」「緊張＝falling」と誤読される。
- Medium: 内部スコアが DOM / コピーに漏洩すると DEC-002/003 が破綻する。
- Low: additive SSE field の欠落時に presence が無言で落ち、run 自体は継続する（許容だが
  デグレ検知はする）。

## Test Strategy

- 緊張ステージ・向き・異常判定の helper を決定的 fixture で unit / node test する。
- SSE / store が内部シグナルを保持しつつ、表示用 selector が生スコアを返さないことを
  test または diff review で確認する。
- RunPage の class / 文言に途中点・暫定平均・score-low-as-tension・カード全体 translate が
  無いことを review する（DEC-005）。
- frontend lint/build、必要な backend snapshot test、docs validator を通す。
- Manual QA で実 run またはモック進行の同席感と異常割込みを確認する。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | 緊張ステージと非アラート語彙 | node unit + review | presence helper test、RunPage / CSS diff | stage 変化が inset/scale 中心で、点滅高速化・score-low に依存しない | planned |
| AC-002 | TODO | motif 上の向きのみ・点数非表示 | node unit + review | presence helper test、RunPage diff | direction enum のみ。カード translate なし。点数文字列なし | planned |
| AC-003 | TODO | 異常割込み閾値 | node unit | presence helper test | 失敗と 0 点過半で割込み、通常点では非発火 | planned |
| AC-004 | TODO | subject は緊張のみ | node unit | presence helper test | 採点前は direction none | planned |
| AC-005 | TODO | reduced-motion | review / manual | CSS / component diff | motion クエリで静的フォールバック | planned |
| AC-006 | TODO | 既存 progress UI 回帰 | node + manual | runStore / RunPage tests、Manual QA | lane / ETA / holistic が従来どおり | planned |
| INV-001 | Intent | 途中点非表示 | review + helper test | RunPage 表示経路 | 通常経路にスコア数値なし | planned |
| INV-002 | Intent | 緊張≠絶対色 | review | CSS / class 使用 | 緊張が score-high/low へ読まれない | planned |
| INV-003 | Intent | チャンネル DOM/変形分離 | review | RunPage / CSS diff | 緊張ターゲットと向き motif が別。カード全体 translate なし | planned |

## Manual QA Checklist

- [ ] 約数分の run で、待ちが続くと動きが小さく／静止緊張へ寄り、確定拍で motif だけが短く動く。
- [ ] 長い待ちでも赤点滅や score-low っぽい緊張に見えない。
- [ ] rising と高緊張（圧縮）が別物として読める。
- [ ] 画面上に途中の 50 点表記や暫定平均が出ない。
- [ ] judge 失敗時に件数付きの失敗表示が出る。
- [ ] 0 点が多い状況（fixture または実 run）で崩壊バナーが出る。
- [ ] 包括評価カードと通常 lane の件数が従来どおり読める。
- [ ] OS の reduce motion 相当で点がチカチカし続けない。

## Regression Checklist

- [ ] standard-only run のキャンセル / 完了 / エラー遷移。
- [ ] holistic_progress dedicated 表示。
- [ ] ETA ラベル（measured / step_fallback / unavailable）。

## Out of Scope

- provider live smoke、採点精度そのもの。
- 結果詳細ページの reasoning 表示。
- ミニゲームやラン全体背景気候の代替案。

## Open Questions

None。閾値の微調整は DEC-003 Change freedom の範囲で実装中に決めて verification に記録する。
