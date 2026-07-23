---
title: "Survey: OpenAI judge reasoning and thinking capture"
status: archived
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/plan/Core/openai-judge-thinking/plan.md"
  - "_docs/intent/Core/openai-judge-thinking/decision.md"
  - "_docs/qa/Core/openai-judge-thinking/test-plan.md"
related_issues: []
related_prs: []
---

# Survey: OpenAI judge reasoning and thinking capture

## Background

Core-Feat-37 は OpenAI 系（o-series / reasoning モデル）を judge に使ったとき、API が返す
thinking / reasoning トークンを judge 採点 JSON の `reasoning`（採点根拠）とは別に取得・保存・
表示することを目的とする。現行実装は judge 呼び出しで reasoning を **リクエスト側** にだけ
opt-in しており、**レスポンス側** から thinking 本文は一切抽出していない。

## Objective

- OpenRouter / OpenAI 互換 API が OpenAI 系 judge 向けに何を返すか整理する。
- 本リポジトリのアダプタ・engine・frontend が今日何を保持・表示しているかを対照する。
- Chat Completions 継続、Responses API 移行、`<thinking>` タグ抽出の各経路の実現可能性と
  リスクを比較する。

## Method

- 2026-07-23 時点のコードベース静的解析（`adapters/`、`core/benchmark_engine.py`、frontend 変換）。
- OpenRouter 公開ドキュメント（Reasoning Tokens、Responses API Beta）の仕様確認。
- 既存テスト `tests/test_adapters.py`、`tests/test_benchmark_engine.py` の reasoning 関連
  ケースの確認。

## Results

### A. 外部 API が expose するもの（OpenAI 系 / OpenRouter 経由）

| 経路 | リクエスト制御 | レスポンス上の thinking / reasoning | 備考 |
| --- | --- | --- | --- |
| **Chat Completions**（現行） | `extra_body.reasoning`（例: `{"effort":"high"}`） | `choices[].message.reasoning`（plaintext string）、`choices[].message.reasoning_details`（構造化配列） | OpenRouter が provider 差を正規化。o-series 等は reasoning トークンを返さないモデルあり |
| **Chat Completions + include_reasoning** | `include_reasoning: true`（レガシー/一部モデル） | 同上 `message.reasoning` | DeepSeek R1 等で文書化。OpenAI o-series では非保証 |
| **Responses API Beta** | `reasoning.effort` 等 | `output[]` 内 `type: "reasoning"`（summary / encrypted_content） | 別エンドポイント・beta・stateless。OpenAI SDK の `chat.completions` とは別クライアント経路 |
| **Content 内タグ** | なし（モデル依存） | `message.content` 内 `<thinking>...</thinking>` 等 | プロバイダ非標準。JSON 採点パース前に strip が必要 |

OpenRouter モデルカタログ（`GET /api/v1/models`）は `supported_parameters` に `reasoning` を
列挙し、一部モデルは `reasoning` オブジェクト（effort 一覧、`mandatory` 等）を返す。
`:thinking` suffix モデルは reasoning が常時 ON とみなされる。

### B. アダプタが今日 extract するもの

| コンポーネント | 入力 | 抽出フィールド | 未抽出 |
| --- | --- | --- | --- |
| `OpenRouterAdapter.complete_with_model_result` | Chat Completions response | `choices[0].message.content` → `CompletionResult.text` | `message.reasoning`、`reasoning_details`、usage 内 `completion_tokens_details.reasoning_tokens` |
| `OpenRouterAdapter.is_reasoning_opt_in` | models catalog | opt-in 可否（`:thinking` は False） | レスポンス解析とは無関係 |
| `LLMAdapter` デフォルト | — | `CompletionResult(text, usage)` のみ | thinking 用フィールドなし |
| `BenchmarkEngine._call_judge_with_retry` | adapter result | `response.text` を JSON パースへ | `CompletionResult` 全体は run dict に未マージ |
| `BenchmarkEngine._run_judge_evaluation` | parsed judge JSON | `runs[].reasoning`（採点根拠オブジェクト） | API thinking |

judge 呼び出し時、`is_reasoning_opt_in(model)` が True のときのみ
`extra_params={"reasoning": {"effort": "high"}}` を `extra_body` に付与する（engine 側。
被験 subject も同パターン）。

### C. 永続化 JSON と frontend

| 層 | judge JSON `reasoning` | API thinking |
| --- | --- | --- |
| run dict / 保存 JSON | `judge_results[model].runs[].reasoning`（`JudgeResponseParser` 後） | フィールドなし |
| `client.ts` | `reasoningSamples` ← `normalizeReasoning(r.reasoning)` | 変換なし |
| `ResultDetail.tsx` | 折りたたみ「理由を表示」 | 専用 UI なし |

`reasoningSamples` のラベルは採点根拠であり、モデル内部 thinking とは UI 上もデータ上も
未分離。

### D. 経路比較（OpenAI 系 judge）

| 方式 | 実装コスト | 互換性 | 主なリスク |
| --- | --- | --- | --- |
| Chat Completions + `message.reasoning` / `reasoning_details` | 低（現行 SDK 経路の拡張） | OpenRouter 正規化に依存。o-series は空の可能性 | フィールド欠落時の graceful degradation |
| Responses API Beta | 高（別 API・パーサ・テスト） | beta breaking change | 本番 judge パイプラインの外部 API 契約変更 |
| `<thinking>` タグ strip + 抽出 | 中（content 前処理） | モデル・プロンプト依存 | 採点 JSON パースへの混入、二重カウント |

## Discussion

- **用語の衝突**: judge スキーマの `reasoning`（`core/json_parser.py`）と API の
  `message.reasoning` は同名だが意味が異なる。永続化では `api_reasoning` または run レベルの
  `thinking` 等で分離が必須。
- **o-series の空白**: OpenRouter ドキュメントは o-series が reasoning トークンを返さない場合があると
  明記。Responses API の encrypted summary のみ、というケースは Chat Completions だけでは
  可視 thinking を得られない可能性がある。
- **コスト**: reasoning トークンは output 課金対象。取得 ON は judge コスト増。既に effort high を
  送っている opt-in モデルでは、取得しないだけで課金は発生しうる。
- **Core-Feat-38 との共有**: `CompletionResult` 拡張と frontend の API thinking 表示契約は共有可能。
  OpenAI 固有の Responses API 判断は 37 に閉じる。

## Recommended Actions

1. Intent で **Chat Completions + OpenRouter 正規化フィールド抽出を第一選択** とし、
   Responses API は o-series で可視 thinking が必須かつ CC 経路が空のときの follow-up とする。
2. `<thinking>` タグ抽出は **第二 fallback**（content から分離し、JSON パース入力から除外）。
3. Plan で `CompletionResult` に optional thinking フィールド、run dict に per-run
   `api_reasoning` を追加する。
4. QA で非 reasoning モデル・thinking 欠落・パース成功の回帰を stub テストする。
