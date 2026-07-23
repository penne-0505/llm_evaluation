---
title: "Survey: Local subject effort/reasoning passthrough"
status: active
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "https://lmstudio.ai/docs/developer/rest/list"
  - "https://lmstudio.ai/changelog/lmstudio-v0.4.8"
related_issues: []
related_prs: []
---

# Survey: Local subject effort/reasoning passthrough

## Background

Inbox 由来の Core-Chore-45 は、ローカル被験（LM Studio）で `reasoning.effort: high` が実際に
送られているのか、送られず LM Studio 側デフォルトに委ねられているのかが不明、という報告である。

## Objective

- 被験呼び出し経路で `extra_params` / `extra_body` が付与される条件を確定する。
- LM Studio モデルの `capabilities.reasoning.default` と opt-in 判定の対応を整理する。
- 代表モデル種別ごとに「effort high を渡す / 意図的に未送信でデフォルト依存」を判定する。
- trivial fix / Bug follow-up の要否を決める。

## Method

- コード静的調査（`LMStudioAdapter` / `OpenRouterAdapter` / `BenchmarkEngine` 被験経路）。
- 既存・追加ユニットテストで catalog stub × `extra_body` 付与を突合
  （`test_is_reasoning_opt_in_lmstudio`、`test_extra_body_passed_to_lmstudio`、
  `test_lmstudio_effort_passthrough_by_capability`、engine 側 reasoning opt-in テスト）。
- LM Studio 公開ドキュメント（`GET /api/v1/models`、0.4.8 changelog、chat completions 互換）を照合。
- ライブ LM Studio への実推論呼び出しは本 Survey の必須スコープ外（ローカルサーバ依存）。
  アプリがレスポンスから reasoning 本文を抽出していない点はコード上で確定済み。

## Results

### A. 被験呼び出し経路（engine）

`BenchmarkEngine._complete_subject_once` および `_call_subject_llm_native` は、次のときだけ
`extra_params = {"reasoning": {"effort": "high"}}` を adapter へ渡す。

```text
subject_adapter.is_reasoning_opt_in(subject_model) is True
```

それ以外は `extra_params=None`。adapter は `extra_params` が truthy のときだけ
OpenAI SDK の `extra_body` に載せる（`LMStudioAdapter.complete_with_model_result` /
`complete_with_model_native_tools`）。

judge 経路（`_call_judge_with_retry`）も同パターン。本タスク主対象は被験。

### B. `LMStudioAdapter.is_reasoning_opt_in`

`GET {base_without_/v1}/api/v1/models` のキャッシュを参照する。

| catalog 状態 | `is_reasoning_opt_in` | engine の `extra_params` |
| --- | --- | --- |
| `capabilities.reasoning.default == "off"` | **True** | `{"reasoning": {"effort": "high"}}` |
| `default == "on"`（または `"off"` 以外） | False | なし（LM Studio モデルデフォルト） |
| `capabilities.reasoning` 自体が無い | False | なし |
| モデル key 不明 / models fetch 失敗 | False | なし |

LM Studio 公式の reasoning capability は主に **on/off**（`allowed_options`）であり、
OpenRouter の `supported_parameters: ["reasoning"]` + `:thinking` always-on とは判定軸が異なる。

### C. OpenRouter との差分

| 項目 | OpenRouter | LM Studio |
| --- | --- | --- |
| opt-in 判定 | `reasoning` ∈ `supported_parameters` かつ `:thinking` でない | `capabilities.reasoning.default == "off"` |
| always-on 扱い | `:thinking` suffix → opt-in False（effort 未送信） | `default == "on"` → opt-in False（effort 未送信） |
| 送信 payload 形 | `extra_body={"reasoning": {"effort": "high"}}` | **同一形を流用** |
| catalog の意味 | effort 系パラメータ対応の有無 | reasoning の default on/off |

### D. 代表モデル種別 × payload × 観測される reasoning 出力

テスト stub（上記 capability 表）とコード経路から確定した対応:

| 種別 | 代表例（テスト / docs） | リクエスト `extra_body` | アプリが観測する reasoning 出力 |
| --- | --- | --- | --- |
| **default off（opt-in）** | `qwen3-30b-a3b`（テスト） | **あり**: `{"reasoning": {"effort": "high"}}` | **未観測**。`CompletionResult` は `message.content` のみ。API の thinking フィールドは未抽出 |
| **default on** | `deepseek-r1`、docs の gemma-4 系 | **なし**（意図的未送信） | 同上。サーバ側はデフォルトで reasoning ON になりうるが、アプリは content 以外を見ない |
| **capability なし** | `llama-3`（テスト） | **なし**（意図的未送信） | 同上。reasoning 制御パラメータ自体を送らない |

結論（AC-003）:

1. **default off**: アプリは effort high を **渡している**（OpenRouter 同型の nested payload）。
2. **default on**: アプリは **意図的に未送信**し、LM Studio のモデルデフォルトに依存。
3. **capability なし**: アプリは **意図的に未送信**。

### E. Payload 形に関する未検証リスク（非 trivial）

- LM Studio 0.4.8 changelog は chat completions で `reasoning_effort` / `reasoning_tokens` を追加と記載。
- 公式 chat completions パラメータ一覧にはまだ列挙されていない。
- `/v1/responses` は `reasoning: { effort: "low"|"medium"|"high" }` を明示サポート。
- 現行アプリは **chat completions + nested `reasoning.effort`**（OpenRouter 向け形）を LM Studio にも送る。
  default off モデルでこの形がサーバに受理・反映されるかは、ライブ検証なしでは未確定。
  flat `reasoning_effort` が正しい経路である可能性が残る → follow-up Bug 候補。

## Discussion

- ユーザー観測「reasoning は ON に見えるが effort high かは不明」は、**default on** モデルでは
  アプリが effort を送っていないことと整合する。
- 「high を渡せない」のではなく、「opt-in 条件を満たさないため意図的に未送信」が現行契約。
- default off では high を送る実装だが、**LM Studio が nested `reasoning.effort` を解釈するか**は
  別問題。ここを変えるのは adapter 契約変更であり trivial ではない。
- レスポンス thinking の永続化は Core-Feat-37/38 系の別スコープ。

## Recommended Actions

1. ~~Core-Chore-45 で代表モデルの stub 突合と Survey 追記~~（本更新で完了）。
2. trivial: `LMStudioAdapter.is_reasoning_opt_in` の docstring で「default on / 無 capability は未送信」を明示（実施済み）。
3. 非 trivial follow-up: LM Studio chat completions 向けに nested `reasoning.effort` と
   top-level `reasoning_effort` のどちらが効くかをライブ検証し、必要なら adapter の payload 正規化を行う
   （**Core-Bug-48** を Backlog 起票済み）。
4. default on モデルへも常に effort high を強制したい場合は、別 Enhance（opt-in 定義変更）とする。
