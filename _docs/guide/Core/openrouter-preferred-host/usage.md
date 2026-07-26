---
title: "Guide: OpenRouter preferred host selection"
status: active
draft_status: n/a
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/Core/openrouter-preferred-host/decision.md"
  - "_docs/qa/Core/openrouter-preferred-host/verification.md"
related_issues: []
related_prs: []
---

# Guide: OpenRouter preferred host selection

## 使い方

1. Settings で OpenRouter の被験 / 評価 / 包括モデルを選ぶ。
2. 各欄の「優先ホスト」ピッカーは常に表示される。ホストが 2 件以上あるときだけ操作できる。
3. 評価・包括はチップをクリックして編集対象を切り替えてからホストを選ぶ。
4. 実行プリセットを保存すると、モデルごとの優先ホストも一緒に保存される。

## 実行時の挙動

優先ホストを選んだ OpenRouter 呼び出しは、同じホストへ最大 3 回試す。それでも失敗したら
ホスト指定なしで再試行する。

## トラブルシューティング

- ピッカーが灰色のまま: ホストが 1 件以下、未選択、非 OpenRouter、または endpoints 取得失敗。
- 一覧が取れない: OpenRouter API キーが Settings に入っているか確認する。
