---
title: "Intent: User-registered OpenAI-compatible providers + Anthropic"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-23
updated_at: 2026-07-24
references:
  - "_docs/archives/draft/Core/openai-compat-anthropic-providers/notes.md"
  - "_docs/archives/survey/Core/openai-compat-anthropic-providers/survey.md"
  - "_docs/archives/plan/Core/openai-compat-anthropic-providers/plan.md"
  - "_docs/qa/Core/openai-compat-anthropic-providers/test-plan.md"
related_issues: []
related_prs: []
---

# Intent: User-registered OpenAI-compatible providers + Anthropic

## Context

OpenRouter 経由の評価は credit 消費が重い。公式プロバイダの credit / 無料枠を subject / judge に
直結させたい。目標は「OpenAI / Anthropic / Google ネイティブ3社を全部揃える」ではなく、
**OpenAI 互換を名前付きで増やせ、Anthropic も使える。OpenRouter も同じ registry の一インスタンス**。
課金表示を誤ると credit 節約判断を損なうため、コスト推定は特に制約を強める。

## Decisions

### DEC-001: Adapter は2系統、プロバイダはユーザー登録 registry

- **What**: 実装クラスは `openai_compatible` と `anthropic` の2種。ユーザーは display_name 付き
  エントリを複数登録する。よく使う公式経路は組み込みプリセットとして同一 registry に載せる
  （詳細は DEC-010）。
- **Why**: ベンダー数ではなくプロトコル差で分岐する方が、任意 OpenAI 互換（AI Studio 含む）を
  増やせる。
- **Change freedom**: ストア実装（単一 JSON vs 分割）は変えられる。kind 追加は別 DEC。
- **Why not**: OpenAI / Google / Anthropic を3ネイティブ固定 — Google は互換 endpoint で足りる。

### DEC-002: LM Studio は初版で registry に吸収しない

- **What**: `lmstudio/` prefix、`LMStudioAdapter`、`/api/lmstudio/config`、Settings の LM Studio
  カードを現状どおり別枠で維持する。
- **Why**: key 不要・base_url 正規化・reasoning capability API が openai_compatible 一般と衝突する。
- **Change freedom**: 第2段で `profile=lmstudio` 吸収可。
- **Revisit when**: registry UX が安定し、LM Studio 固有を profile フラグで表現できるとき。

### DEC-003: モデル ID は `{provider_id}/{upstream_model_id}`、`or/` は openrouter エイリアス維持

- **What**: ルーティングは候補 A。既存 `openrouter/...` はそのまま。`or/` は openrouter プリセット
  へのエイリアスとして維持（非推奨表示は任意）。
- **Why**: 現行 ID・preset・strict・fixture との差分が最小。
- **Change freedom**: 表示ラベルは display_name。内部 id スキーマ変更は migration DEC が必要。
- **Why not**: 明示スキーム `openai-compat:...` — 既存資産の書き換えコストが大きい。

### DEC-004: provider id は slug 自動生成、display_name は自由

- **What**: id は `[a-z0-9-]+` slug（display_name から生成、衝突時サフィックス）。reserved:
  `openrouter`、`openai`、`google-ai-studio`、`anthropic`、`lmstudio`、`or`。
  ユーザーは display_name を編集、id は作成後不変。
- **Why**: モデル ID prefix と secrets キーに安全な識別子が必要。自由文字列 id は衝突・path 汚染のリスク。
- **Change freedom**: slug 生成アルゴリズム（正規化規則）は変えられる。

### DEC-005: OpenRouter 固有は `kind=openai_compatible` + `profile=openrouter`

- **What**: reasoning catalog gate、`:thinking`、公開 models、management key / credits は
  `profile=openrouter` のときだけ有効。汎用 openai_compatible には載せない。
- **Why**: 汎用パスに OR 固有を混ぜると、AI Studio 等で誤ゲートや不要リクエストが起きる。
- **Change freedom**: profile 名やフックの配置（サブクラス vs strategy）は実装裁量。

### DEC-006: Anthropic 初版は subject + judge + tool-use + thinking

- **What**: Messages API で complete、native tool_use、thinking ブロックを `api_reasoning` に正規化。
  prompt caching / Batches は非保証。
- **Why**: 公式 Claude を OpenRouter 抜きで評価に使う動機に、tool タスクと thinking 表示が含まれる。
- **Change freedom**: thinking の effort / budget パラメータ形状は SDK 追従で変更可。
- **Why not**: judge のみ / complete のみ — 公式経路の価値を削る。

### DEC-007: 推定コストは明示 `pricing_profile` のみ。公式3社は静的表。OR フォールバック禁止

- **What**: 各 registry エントリに `pricing_profile`:
  `openrouter` | `openai` | `anthropic` | `google` | `none`。
  - `openrouter` → 現行 catalog 価格
  - `openai` / `anthropic` / `google` → リポジトリ内静的表（`as_of` 日付付き）
  - `none` または表に無いモデル → 推定不可（`partial` / `unavailable`）。**0 にしない**
  - `openai`/`anthropic`/`google` 経路では OpenRouter カタログへのフォールバックを行わない
  OpenRouter プリセットの default profile は `openrouter`。ユーザーが OpenAI 公式を登録するときの
  default は `openai`（base_url ヒューリスティック + 明示上書き可）。
- **Why**: 現行 `_lookup_pricing` の OR フォールバックは、公式 credit 経路に別社価格を付け得る。
  誤った安価/高価表示は credit 配分判断を壊す。
- **Change freedom**: 表の更新方法（手動コミット）、モデル ID エイリアス解決は変更可。自動同期は別タスク。
- **Why not**: 常に N/A — 公式3社の概算が見えないと動機（credit 消化）の効果測定ができない。
- **Revisit when**: 公式が機械可読価格 API を安定提供したとき。

### DEC-008: Secrets は registry id 単位。既存 openrouter key をプリセットへ写像

- **What**: secret キーを固定 enum だけに依存させない。環境変数は
  `PROVIDER_<ID_UPPER_UNDERSCORE>_API_KEY`（例: `PROVIDER_OPENAI_CREDIT_API_KEY`）。
  既存 `OPENROUTER_API_KEY` / secrets.toml `openrouter` は初回起動で openrouter プリセットへ写像。
  `LMSTUDIO_*` は従来どおり別枠。API key は結果 JSON / SSE / ログに出さない。
- **Why**: 複数 openai_compatible を表現するには動的 id が必要。既存ユーザーの OpenRouter 設定を壊さない。
- **Change freedom**: ファイル形式・暗号化はセキュリティ標準の範囲で変更可。

### DEC-009: 欠損プロバイダは表示耐性と実行時エラー

- **What**: 削除・key 欠落後も preset / 過去 run の読取表示はクラッシュしない（欠損ラベル）。
  実行時は明確なエラー（再実行不可の理由）。
- **Why**: 履歴と設定の寿命が異なる。表示破壊はデータ損失に見える。
- **Change freedom**: UI 文言・エラーコードは変更可。

### DEC-010: ビルドインプリセットは OpenRouter / OpenAI / Google AI Studio + Anthropic（集合 A）

- **What**: 初回 seed（欠落時の再 seed）で次を常駐させる。いずれも `builtin=True`、削除不可、
  key のみクリア可。display_name / pricing_profile の上書きは可（OpenRouter の `profile=openrouter`
  と公式 base_url 初期値は維持方針）。
  | id | kind | 既定 base_url | pricing_profile | profile |
  | --- | --- | --- | --- | --- |
  | `openrouter` | openai_compatible | `https://openrouter.ai/api/v1` | openrouter | openrouter |
  | `openai` | openai_compatible | `https://api.openai.com/v1` | openai | （なし） |
  | `google-ai-studio` | openai_compatible | `https://generativelanguage.googleapis.com/v1beta/openai/` | google | （なし） |
  | `anthropic` | anthropic | 公式デフォルト（省略可） | anthropic | （なし） |
  ユーザーはこれ以外の openai_compatible / anthropic を追加登録できる。Groq / DeepSeek 等は初版に含めない。
- **Why**: 動機の公式 credit 経路（OpenAI / Google / Anthropic）と既存 OpenRouter を、手打ち
  base_url なしで選べるようにする。網羅リストは保守コストと誤った pricing_profile 付与を増やす。
- **Change freedom**: display_name 文言、Anthropic の明示 base_url 有無、Settings での「プリセットから追加」UI 形。
- **Why not**: DeepSeek / Groq 等を同時搭載 — 価格表が `none` になりやすく、初版の検証範囲を散らす。
- **Revisit when**: 利用頻度の高い互換エンドポイントが増え、静的価格または明示 `none` 運用が安定したとき。

## Consequences / Impact

- Settings の cloud は「openrouter 1枠」から「builtin 4 + ユーザー追加」の registry 一覧へ。
- usage.provider は registry id（openrouter プリセットは `openrouter` を維持し既存集計と整合）。
- 公式経路のコストは静的表の鮮度に依存（`as_of` と partial で明示）。
- Anthropic ネイティブ thinking は OpenRouter Claude 経路（Feat-38）と並存。
- AC-004 の Google 手順は、主に builtin `google-ai-studio` の存在と key 設定で満たせる。

## Quality Implications

- Migration / secrets / cost 誤表示を High risk として AC と Test Matrix に載せる。
- Anthropic tools/thinking は stub で AC カバー。live Manual QA は任意 follow-up。

## Intent-derived Invariants

- INV-001 (from DEC-007): `pricing_profile` が `openai` / `anthropic` / `google` の usage について、推定コストの `pricing_source` は静的表由来であり、`openrouter_catalog` であってはならない。価格不明なら推定額は `None`（ゼロ埋め禁止）。
- INV-002 (from DEC-008): run 結果 JSON、SSE イベント、catalog キャッシュに API key 文字列を書き出さない。

## Rollback / Follow-ups

- rollback: registry を無効化し openrouter/lmstudio 固定ルーティングに戻す（seed のみ残す選択可）。
- follow-up: LM Studio 吸収、価格表自動更新、connection test の強化、`or/` 非推奨化。
