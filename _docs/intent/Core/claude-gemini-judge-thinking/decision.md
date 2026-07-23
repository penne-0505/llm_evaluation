---
title: "Intent: Claude and Gemini judge reasoning capture"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/survey/Core/claude-gemini-judge-thinking/survey.md"
  - "_docs/archives/plan/Core/claude-gemini-judge-thinking/plan.md"
  - "_docs/qa/Core/claude-gemini-judge-thinking/test-plan.md"
  - "_docs/qa/Core/claude-gemini-judge-thinking/verification.md"
  - "_docs/intent/Core/openai-judge-thinking/decision.md"
related_issues: []
related_prs: []
---

# Intent: Claude and Gemini judge reasoning capture

## Context

OpenRouter 経由の Claude / Gemini judge では、`is_reasoning_opt_in` により opt-in モデルへ
`reasoning.effort: high` が送られるが、`:thinking` suffix モデルは always-on のため extra_params なし
で呼ばれる。いずれも adapter は `message.content` のみ返し、Anthropic thinking ブロックや Gemini
thinking 出力は破棄される。Core-Feat-37 と `CompletionResult` / `api_reasoning` / UI 分離は共有するが、
provider 別の取得可否と no-support 境界は本 Intent で決める。

## Decisions

### DEC-001: Anthropic / Gemini judge は OpenRouter 正規化 Chat Completions フィールドから thinking を取る

- **What**: `OpenRouterAdapter` は Anthropic / Gemini judge レスポンスの `message.reasoning` と
  `message.reasoning_details` を読み、共通ヘルパで plaintext `api_reasoning` に正規化する。
  ネイティブ Messages API / Gemini SDK 直叩きは行わない。
- **Why**: 本アプリの judge 経路は OpenRouter に統一されており、OpenRouter が provider 差を
  `reasoning` / `reasoning_details` に flatten する。二重の provider パーサは保守コストだけ増やす。
- **Change freedom**: `reasoning_details` の serialize 形式、複数 chunk の join 順序は変更できる。
- **Why not**: Anthropic SDK 直読み — judge adapter 抽象と設定（API キー・モデル ID）が OpenRouter
  前提のため。

### DEC-002: Gemini 非 thinking モデルは no-support とし空 api_reasoning で完走する

- **What**: OpenRouter catalog で `reasoning` 非サポートの Gemini judge モデルは thinking 抽出を
  試みない。run には `api_reasoning` を付けない（または null）。judge 採点は従来どおり。
- **Why**: Survey 上、thinking 出力は thinking 対応モデルに限定される。非対応モデルで content から
  推測抽出すると誤表示リスクが高い。
- **Change freedom**: catalog に `reasoning` が追加されたモデルはサポート対象へ移行できる。
- **Revisit when**: Google が非 thinking Gemini でも `reasoning_details` を返すことが OpenRouter
  ドキュメントで確認された時。

### DEC-003: `:thinking` suffix と opt-in reasoning は同一抽出経路で扱う

- **What**: `is_reasoning_opt_in` が False でも（`:thinking` always-on）、レスポンスに
  `message.reasoning` があれば `api_reasoning` に保存する。opt-in モデルは effort high 送信 +
  同一抽出。
- **Why**: opt-in 判定は **リクエスト** 制御であり、**レスポンス** 抽出条件ではない。`:thinking`
  モデルは effort 未送信でも thinking が返るため、抽出を opt-in True に限定すると取りこぼす。
- **Change freedom**: モデル ID  suffix による特別扱いは不要。レスポンスフィールドの有無だけで判定。
- **Why not**: `:thinking` だけ別 API 経路 — OpenRouter 上は同一 Chat Completions レスポンス形状。

### DEC-004: 永続化・UI 契約は Core-Feat-37 の DEC-001 / DEC-004 に追随する

- **What**: run dict キー `api_reasoning`、frontend の採点根拠 `reasoningSamples` とのラベル分離は
  37 Intent と同一。38 は adapter provider 分岐と Gemini no-support rationale を追加する。
- **Why**: 二重の JSON / UI 契約を避け、engine / frontend を provider 非依存に保つ。
- **Change freedom**: 37 未実装時は 38 が同一 DEC を再掲してよいが、マージ後は 37 を正典とする。

## Consequences / Impact

- Claude `:thinking` judge で初めて API thinking が UI に現れる。
- Gemini thinking モデルは 37 と同 UI。非 thinking は thinking セクション非表示。
- 37 への hard dependency なし。UI 先行/後追いは QA verification で PARTIAL 可能。

## Quality Implications

- stub: `anthropic/claude-3.7-sonnet:thinking`（reasoning あり、extra_params なし）。
- stub: opt-in Claude（effort high + reasoning あり）。
- stub: Gemini thinking / 非 thinking。
- 全ケースで aggregated スコア取得成功（AC-005）。

## Intent-derived Invariants

None

## Rollback / Follow-ups

- rollback: Anthropic / Gemini 向け adapter 分岐を削除。37 共通フィールドが空になるだけ。
- follow-up: Gemini 側 OpenRouter 仕様変更時は DEC-002 を revisit。
