---
title: "Survey: Claude and Gemini judge reasoning capture"
status: completed
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/plan/Core/claude-gemini-judge-thinking/plan.md"
  - "_docs/intent/Core/claude-gemini-judge-thinking/decision.md"
  - "_docs/qa/Core/claude-gemini-judge-thinking/test-plan.md"
  - "_docs/archives/survey/Core/openai-judge-thinking/survey.md"
related_issues: []
related_prs: []
---

# Survey: Claude and Gemini judge reasoning capture

## Background

Core-Feat-38 は Anthropic Claude および Google Gemini を judge に指定したとき、API レベルの
thinking / reasoning を取得・永続化・表示することを目的とする。Core-Feat-37（OpenAI 系）と
`CompletionResult` 拡張および frontend 表示契約は共有可能だが、本 Survey / Plan / Intent /
QA は独立ドキュメントとする。

## Objective

- Anthropic / Gemini（OpenRouter 経由）が judge 呼び出しで何を返すか整理する。
- 現行 adapter / engine / UI が何を extract・表示しているかを対照する。
- `:thinking` suffix（常時 ON）と opt-in reasoning モデルの差分を実装方針へ反映する。

## Method

- 2026-07-23 時点のコードベース静的解析。
- OpenRouter Reasoning Tokens ドキュメント（Anthropic `max_tokens`、Gemini thinking モデル）。
- 既存 `is_reasoning_opt_in` テスト（Claude 3.7、`:thinking` suffix）の確認。

## Results

### A. 外部 API が expose するもの（Anthropic / Gemini / OpenRouter）

| Provider | リクエスト制御 | レスポンス thinking | OpenRouter 正規化 |
| --- | --- | --- | --- |
| **Anthropic Messages**（OR 経由） | `reasoning.max_tokens` または `reasoning.effort` | thinking ブロック → `message.reasoning` / `reasoning_details` | Chat Completions 互換レスポンスへ正規化 |
| **Claude `:thinking` suffix** | 常時 reasoning ON（opt-in 不要） | 同上 | `is_reasoning_opt_in` は False（`:thinking` で always on 判定） |
| **Claude opt-in**（例: claude-3.7-sonnet） | `reasoning.effort: high`（engine が送信） | 同上 | catalog `supported_parameters` に `reasoning` |
| **Gemini thinking** | `reasoning.effort` または `reasoning.max_tokens` | `message.reasoning` / `reasoning_details`（モデル依存） | 一部モデルは mandatory reasoning |
| **Gemini 非 thinking** | — | なし | 通常 content のみ |

OpenRouter モデルエントリの `reasoning` オブジェクトは effort 一覧、`mandatory`、`default_enabled`
等を返しうる。Gemini 3.x thinking 系は effort 選択または token budget をサポート。

### B. アダプタが今日 extract するもの

| コンポーネント | Anthropic / Gemini 向け動作 | ギャップ |
| --- | --- | --- |
| `OpenRouterAdapter.is_reasoning_opt_in` | catalog で `reasoning` サポートかつ `:thinking` でない → True | レスポンス抽出とは無関係 |
| `OpenRouterAdapter.complete_with_model_result` | `message.content` のみ → `CompletionResult.text` | `message.reasoning`、`reasoning_details` 未読 |
| `BenchmarkEngine._call_judge_with_retry` | opt-in 時 `{"reasoning":{"effort":"high"}}` | `:thinking` モデルは extra_params なし（always on） |
| `_run_judge_evaluation` | judge JSON `runs[].reasoning` のみ | API thinking 未保存 |

Claude `:thinking` モデルは engine が effort を送らないが、プロバイダ側 reasoning は ON のため、
**取得しないだけで thinking がレスポンスに含まれる可能性が高い**（Survey 上の主要ギャップ）。

### C. frontend（Core-Feat-37 と共有 UI 契約）

| 表示 | データ源（現行） | Core-Feat-38 後（37 と整合） |
| --- | --- | --- |
| `reasoningSamples` | judge JSON `reasoning` | 変更なし（採点根拠） |
| API thinking UI | なし | `api_reasoning` → 専用折りたたみ（37 で定義した契約を再利用） |

Core-Feat-37 が UI 契約を先行実装した場合、38 は adapter 抽出と provider 別 stub に集中できる。

### D. Gemini 取得可否（調査結論）

| 区分 | 結論 |
| --- | --- |
| Gemini thinking モデル（OpenRouter 上 `reasoning` サポート） | **取得可能** — OpenRouter 正規化フィールド経由で 37 と同型抽出 |
| Gemini 非 thinking モデル | **no-support** — `api_reasoning` 欠落、Intent に rationale を記録 |
| 形状差 | `reasoning_details` 内 `type: reasoning.text` 等。adapter は string 正規化が必要 |

## Discussion

- **`:thinking` vs opt-in**: テスト `test_is_reasoning_opt_in_openrouter` は `:thinking` → False を
  固定。judge は effort を送らないが、thinking 抽出はレスポンス側の問題であり opt-in 判定と独立。
- **Anthropic thinking ブロック**: ネイティブ API では `type: thinking` ブロックだが、OpenRouter
  Chat Completions では `message.reasoning` に flatten される想定（37 Survey と同一経路）。
- **Graceful skip**: Gemini 非 thinking・thinking 空・パースのみ成功は AC-005 の要件。
- **独立性**: 37 への hard dependency は設けない。UI 未実装時は 38 も backend まで先行可能だが、
  表示 AC は 37 UI 契約または 38 内の最小 UI で満たす。

## Recommended Actions

1. Intent で Anthropic / Gemini とも **OpenRouter Chat Completions + `message.reasoning` /
   `reasoning_details` 抽出** を第一選択とする（37 DEC-002 と整合、provider ロジックは adapter 内分岐）。
2. Gemini 非 thinking モデルは **no-support rationale** を Intent に記録し、空 `api_reasoning` で完走。
3. `:thinking` と opt-in の両方を stub テスト（AC-004）。
4. UI は Core-Feat-37 の `ResultDetail` 契約を再利用（独立 QA 行で provider 別 stub を検証）。
