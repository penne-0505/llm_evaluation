---
title: "Intent: OpenRouter preferred host selection"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/archives/plan/Core/openrouter-preferred-host/plan.md"
  - "_docs/qa/Core/openrouter-preferred-host/test-plan.md"
  - "_docs/guide/Core/openrouter-preferred-host/usage.md"
related_issues: []
related_prs: []
---

# Intent: OpenRouter preferred host selection

## Context

同一 OpenRouter モデルでも upstream ホスト（Together / Fireworks 等）で価格・スループット・
品質が異なる。利用者は特定ホストを優先したいが、障害時に評価全体が止まると困る。
モデルピッカーにホストを混ぜると選択 UI が肥大化するため、別ピッカーで必要時のみ操作する。

## Decisions

### DEC-001: ホスト指定は優先であり、同じホストへ最大 3 回試したあと unrestricted にフォールバックする

- **What**: 優先ホストがある呼び出しは `provider.only=[slug]` + `allow_fallbacks=false` で最大 3 回試す。
  いずれも失敗したらホスト指定なしで再試行する。
- **Why**: 「できればこのホスト」を守りつつ、単一ホスト障害で run 全体を落とさない。
  OpenRouter の即時他ホスト切替ではなく、アプリ側で同じ優先ホストを再試行する明示要求に合わせる。
- **Change freedom**: 試行回数（3）やバックオフ間隔は変更できる。ピン留め時の `provider` 形は
  OpenRouter 契約を満たす限り変更できる。
- **Why not**: `order` + fallback true だけだと、1 回目失敗で即別ホストへ飛び、同じホスト再試行にならない。
- **Revisit when**: OpenRouter が同一ホスト再試行を公式に表現できるようになった時。

### DEC-002: 設定単位はモデル ID → host slug のマップとし、実行プリセットにも含める

- **What**: `preferredHosts: Record<modelId, hostSlug>` を Settings 永続化し、execution preset
  config に保存・復元する。subject / judge / holistic が参照する。
- **Why**: ホスト嗜好はモデルに紐づく。プリセットで再現できないと比較 run の条件が欠ける。
- **Change freedom**: キー正規化や未選択時のキー削除方針は変更できる。schemaVersion は
  後方互換を保てるなら据え置きでよい。
- **Why not**: run 限りの一時指定だけだと再現性が落ちる。

### DEC-003: ホストピッカーはモデルピッカーと分離し、常時表示・endpoints≥2 で enabled

- **What**: ホスト UI は show/hide せず disabled/enabled で切り替える。judge / holistic は
  共有ピッカー1つと、編集対象を切り替えるチップ（現在ホスト表示付き）を使う。
- **Why**: レイアウトの予測可能性を保ちつつ、指標つきリストの複製を避ける。
- **Change freedom**: チップの見た目やフォーカス操作は変更できる。非 OpenRouter 時に枠を
  disabled のまま残すか枠ごと畳むかは、disabled/enabled 原則を壊さない範囲で調整できる。
- **Why not**: モデルピッカー内選択はホスト比較指標と相性が悪い。行ごとフルピッカー複製は密度過多。

### DEC-004: ホスト一覧の指標は endpoints API の tps(p50) と $/M 価格を表示する

- **What**: 各リスト要素に throughput p50、prompt/M、completion/M、input_cache_read/M を出す。
  欠落は `—`。routing には endpoint `tag`（slug）を使う。
- **Why**: ホスト選択の判断材料が価格と速度だから。OpenRouter endpoints が正準情報源。
- **Change freedom**: 表示桁・並び替え・追加指標（latency / uptime）は変更できる。
- **Why not**: 独自計測はコストが高く、カタログ価格と乖離しやすい。

## Consequences / Impact

- RunRequest / preset / Settings に `preferredHosts` が加わる。
- OpenRouter 呼び出し経路に preferred-host 試行ループが入る。
- Settings のモデル選択 UI がホスト枠を持つ。

## Quality Implications

- preferred 試行と unrestricted フォールバックの順序をテストで固定する。
- legacy preset（フィールドなし）が空マップとして読めること。
- ホスト1件以下でピッカーが disabled であること。

## Intent-derived Invariants

- INV-001 (from DEC-001): 優先ホスト指定時、unrestricted 呼び出しの前に同じホストへのピン留め試行が先行する。
- INV-002 (from DEC-002): preferredHosts の欠落は空マップとして扱い、既存 preset 読込を壊さない。

## Rollback / Follow-ups

- rollback は `preferred_hosts` RunRequest フィールド、engine 試行ループ、endpoints proxy、
  Settings / HostPicker / preset フィールドを同時に戻す。
- 既存結果 JSON の破壊は不要。ホスト未指定 run は従来どおり動く。
- follow-up 候補: ホスト別実測コスト表示、latency/uptime 指標、Manual QA の実 API 確認。
