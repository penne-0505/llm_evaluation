---
title: "Intent: Run presence observation"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/plan/UI/run-presence-observation/plan.md"
  - "_docs/qa/UI/run-presence-observation/test-plan.md"
related_issues: []
related_prs: []
---

# Intent: Run presence observation

## Context

評価 run はおおよそ数分で終わることが多く、実行中画面を見続ける需要がある。一方で
進行ボードは状態一覧として機能するが、API 待ちのあいだに観察対象がなく静止する。
raw ログの垂れ流しや途中の具体点表示は、報酬の先食いになりやすく、最後の結果開示の
楽しさを削る。本 Intent は、観察を目的とし、楽しさは質として副次的に扱う presence
層の判断を固定する。

## Decisions

### DEC-001: 実行中 presence の主舞台は active な評価の局所とする

- **What**: 緊張と変化の向きは、進行ボード全体の背景気候ではなく、実行中レーンの
  active task card（およびその稼働セグメント）に置く。ボード自体は帰還用の地図として残す。
- **Why**: やや同席寄りで、変化が起きている場所を見続ける理由を作るため。全体気候だけだと
  視線の焦点が定まらず、既存ボードの情報と競合しやすい。
- **Change freedom**: カード内の具体 DOM 構造、judge チップ単位か bar 単位かは、局所性が
  保たれる限り変更できる。
- **Why not**: ラン全体の背後色だけにすると、同席時の「いま動いているもの」が弱い。
- **Revisit when**: 並列 active タスクが常時多数になり、局所演出が視覚ノイズになった時。

### DEC-002: 常時表示は緊張（時間）と変化の向き（直近差分）の二チャンネルに限る

- **What**:
  - 緊張: 現在の subject / judge 呼び出しの滞留に応じて気配が張り詰める。色相を
    score-low へ寄せて「悪い点」と読ませない。
  - 変化の向き: 採点確定の拍で rising / falling / unsettled のみを短く出す。絶対水準・
    帯ラベル・具体点は出さない。
  - subject フェーズは緊張のみ。
- **Why**: 待ちの楽しさを「過程の継続音」と「確定の拍」に分け、数値による感情の早期着地を
  防ぐ。時間と得点を同一視覚語彙に混ぜると、長い待ちが低得点に誤読される。
- **Change freedom**: 滞留ステージの秒境界、拍の ms、具体 keyframes は Plan の語彙を満たす
  限り調整できる。向きの算出窓（直近 N 件など）も、絶対水準を漏らさない限り変更できる。
- **Why not**: 絶対的な暖色／寒色気候や暫定平均は、途中で良し悪しが確定して開示を殺す。
  raw ログは観察というより監視端末化し、本アプリの評価体験とずれる。
- **Revisit when**: 途中開示を明示オプトインする「ライブ採点モード」が必要になった時。

### DEC-003: 数値と率直文言は失敗および極端な崩壊の割込みにだけ使う

- **What**: judge / task の実行失敗（error 等）と、settled 採点における 0 点の過半（または
  同等に明らかな崩壊）のときだけ、件数などの数値と率直な文言を出す。通常の途中点は
  内部シグナルに閉じ、UI 文字列にも出さない。
- **Why**: 楽しみを守る制約と、壊れた run を最後まで隠さない率直さを両立するため。
- **Change freedom**: 過半以外の閾値（連続 0 の本数など）は、False positive を見ながら
  調整できる。バナーの配置（カード内 / ボード上）も変更できる。
- **Why not**: 失敗だけの割込みだと 0 点だらけを最後まで隠せる。常時数値は DEC-002 に反する。
- **Revisit when**: 信頼性除外や N/A 集計の途中シグナルを、利用者が run 中に知る必要が
  強くなった時。

### DEC-004: 内部採点シグナルは SSE / store に持てるが、表示契約の外とする

- **What**: 変化の向きと異常判定のため、progress に additive な内部用スコア情報を載せて
  よい。frontend は方向・異常フラグへ畳み込み、レンダリング経路に生スコアを流さない。
- **Why**: 向きは差分なしには作れない。一方で DOM やコピーに数値が出た瞬間、DEC-002/003
  の契約が壊れる。
- **Change freedom**: payload 形状、ハッシュ化や bucket 化の有無は、向きと異常が再現でき
  DevTools 以外の通常 UI に生スコアが出ない限り変更できる。
- **Why not**: スコア無しの擬似乱数演出は観察ではなく嘘になる。
- **Revisit when**: クライアントに生スコアを渡さず server が direction enum だけを送る形へ
  寄せたい時。

### DEC-005: 緊張と変化の向きは別 DOM ターゲットと別変形語彙を使う

- **What**: 緊張はカード inset と最長 active セグメントの圧縮／呼吸に閉じる。変化の向きは
  pipeline とは別の専用 motif の単発変位（上下・横揺れ）に閉じる。緊張の主軸を opacity
  点滅の高速化にしない。カード全体の translate で向きを出さない。
- **Why**: 初稿では「縮む」が緊張と falling で共有され、長い待ちと得点下降が区別できない。
  点滅高速化は障害アラートに読める。カード平行移動はレーンスクロールと競合する。
- **Change freedom**: motif の形（レール／針）、px 変位、ステージ秒境界は Plan の
  Expression Technique を満たす限り調整できる。
- **Why not**: 同一要素の scale だけに両方を載せる実装は、チャンネル分離を見た目で証明できない。
- **Revisit when**: 専用 motif が情報過多だと判明し、pipeline セグメント自体へ向きを畳む必要が
  出た時（その場合も緊張用 scaleY と向き用 translate はプロパティを分ける）。

## Consequences / Impact

- RunPage active カードの視覚密度が上がる。並列 active が多い設定では演出を間引く必要が
  出る可能性がある（DEC-001 Revisit）。
- progress SSE が additive に広がる。保存結果 JSON のスキーマ破壊は不要。
- 完了時の総合点開示が、絶対水準を知る主瞬間として残る。
- 実装は CSS 変数 transition（緊張）と既存 `motion` パッケージの単発拍（向き）を前提にする。

## Quality Implications

- helper が「向き」と「緊張ステージ」と「異常」を決定的に分け、UI 文字列へ生スコアを
  混ぜないこと。
- 緊張と向きが同一変形プロパティに載っていないこと（DEC-005）。
- reduced-motion で連続アニメに依存しないこと。
- 既存 lane / holistic progress / ETA 表示を回帰させないこと。

## Intent-derived Invariants

- INV-001 (from DEC-003): 通常の実行中 UI 経路に途中の具体スコアまたは暫定平均を表示せず、数値表示は失敗および極端な崩壊の割込みに限る。
- INV-002 (from DEC-002): 緊張チャンネルの視覚語彙を、得点の絶対的良し悪し（score-high / score-low への読み替え）に使わない。
- INV-003 (from DEC-005): 緊張と変化の向きは別 DOM ターゲットに載せ、向きをカード全体の平行移動や緊張と同一の圧縮プロパティだけで表現しない。

## Rollback / Follow-ups

- rollback は presence UI、内部シグナル field、関連 helper を戻す。
- 包括評価フェーズへの同様の局所演出は、本タスクで必須とせず follow-up としうる。
