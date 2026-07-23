---
title: "Intent: OpenAI judge reasoning and thinking capture"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/survey/Core/openai-judge-thinking/survey.md"
  - "_docs/archives/plan/Core/openai-judge-thinking/plan.md"
  - "_docs/qa/Core/openai-judge-thinking/test-plan.md"
related_issues: []
related_prs: []
---

# Intent: OpenAI judge reasoning and thinking capture

## Context

judge は `JudgeResponseParser` 通過後の JSON `reasoning` に採点根拠を書く。これはモデル内部の
thinking トークンとは別概念である。現行 `CompletionResult` は `text` のみで、OpenRouter アダプタも
`message.content` だけを返す。engine は opt-in モデルへ `reasoning.effort: high` を送るが、
レスポンス thinking は保存も表示もしない。Core-Feat-38 と `CompletionResult` / UI 契約は共有可能だが、
OpenAI 系の API 経路選択（Chat Completions vs Responses API vs タグ）は本 Intent で決める。

## Decisions

### DEC-001: API thinking と judge 採点根拠は別フィールドで永続化する

- **What**: API から得た thinking は judge run dict の `api_reasoning`（string または正規化済み
  構造）に保存する。既存 judge JSON `reasoning` と frontend `reasoningSamples` は採点根拠専用のまま
  維持する。
- **Why**: 同名 `reasoning` の混在は保存 JSON・UI・集計で意味が衝突し、採点根拠を thinking で
  上書きするデータ破壊リスクがある。
- **Change freedom**: 内部表現（string vs `{text, details}`）、frontend プロパティ名
  （`apiReasoningSamples` 等）は、採点根拠との分離と後方互換を保つ限り変更できる。
- **Why not**: judge JSON `reasoning` に API thinking をマージしない。パーサと UI が採点オブジェクト
  を期待しており、thinking 混入で schema 検証と表示が壊れる。

### DEC-002: OpenAI 系 judge は Chat Completions 経路を第一選択とし Responses API は defer する

- **What**: 現行 `OpenRouterAdapter` の `chat.completions.create` を維持し、レスポンスの
  `message.reasoning` / `message.reasoning_details` を抽出する。OpenRouter Responses API Beta への
  judge パイプライン移行は本タスクでは行わない。
- **Why**: 既存 SDK・リトライ・usage 計測・テスト stub が Chat Completions に揃っており、Survey で
  OpenRouter が reasoning フィールドを正規化している。Responses API は beta で breaking change と
  別パーサが必要で、High risk の本変更に対してコストが見合わない。
- **Change freedom**: o-series 等で CC 経路が可視 thinking を返さず、product が encrypted summary
  表示を必須とした場合のみ follow-up タスクで Responses API を Intent 更新のうえ追加できる。
- **Why not — Responses API 全面移行**: beta、stateless 制約、judge 並列 worker との統合コストが大きい。
- **Why not — タグ抽出のみ**: OpenRouter 正規化フィールドを無視すると、標準 thinking モデルで
  二重処理・取りこぼしが起きる。

### DEC-003: content 内 `<thinking>` タグ抽出は Chat Completions フィールド欠落時の fallback とする

- **What**: `message.reasoning` / `reasoning_details` が空のとき、`message.content` から
  `<thinking>...</thinking>`（大文字小文字・属性なしを第一対象）を抽出し `api_reasoning` に入れる。
  抽出後は judge JSON パース用 text から当該ブロックを除去する。
- **Why**: 一部モデル・ルーティングでは thinking が content に残る。パース前 strip をしないと
  採点 JSON 抽出が失敗する。
- **Change freedom**: タグパターン一覧、strip 順序は変更できる。fallback は thinking 欠落時のみ
  実行し、スコア取得を阻害しない。
- **Why not**: タグ抽出を第一選択にしない。プロンプト・モデル依存が強く、標準フィールドより
  脆い。

### DEC-004: `CompletionResult` 拡張は provider 非依存の optional フィールドとする

- **What**: `CompletionResult` に optional `api_reasoning: str | None`（必要なら `reasoning_details`
  の serialized 形式）を追加する。OpenAI 固有ロジックは adapter 内に閉じる。
- **Why**: Core-Feat-38（Claude / Gemini）が同型フィールドを再利用でき、engine / frontend 契約を
  一度だけ定義できる。hard dependency は設けない。
- **Change freedom**: フィールド名・詳細度は変更できるが、judge run へのマージ点は engine に一本化する。

## Consequences / Impact

- 保存 JSON に additive な `api_reasoning` が run 単位で増える。サイズ・secret 混入リスクは
  QA High-risk Checklist で確認する。
- o-series で CC 経路が thinking を返さない場合、UI は空表示のまま採点は成功する（AC-004）。
- frontend はラベル「API thinking（モデル内部推論）」等で `reasoningSamples`（採点根拠）と区別する。

## Quality Implications

- adapter stub で reasoning フィールドあり/なし/タグのみを検証する。
- engine テストで JSON パース成功と `api_reasoning` 共存を確認する。
- thinking 欠落時の judge 集計回帰を必須とする。

## Intent-derived Invariants

None

## Rollback / Follow-ups

- rollback: adapter 抽出・run マージ・UI を削除すれば、従来の `reasoning` のみの run に戻る。
- follow-up: o-series で可視 thinking が product 必須かつ CC が空のとき、Responses API 経路を
  別 Intent で検討する。
