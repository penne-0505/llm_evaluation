---
title: Local Search Tool-Use Runtime
status: active
draft_status: n/a
created_at: 2026-04-07
updated_at: 2026-04-07
references:
  - ./grounding-corpus-pipeline.md
related_issues: []
related_prs: []
---

## Overview
- `task08` をはじめとする Deep Research 系タスクで、モデルプロバイダ固有の web 検索機能に依存せずに tool-use を評価できる runtime を追加する。
- 実装方針は、各社 API の native tool calling ではなく、被験モデルとの複数ターン対話を `BenchmarkEngine` 側で管理する provider 共通の擬似 tool protocol を採用する。
- 初期対象は `task08` とし、ローカルに保存した検索結果 JSON / document 本文を `web-search` と `open-document` で参照させる。

## Scope
- 被験モデル実行を単発 completion から「tool call を挟める複数ターン実行」に拡張する。
- task ごとに有効な tool と参照データを切り替えられる最小の task context を導入する。
- `grounding_corpus` または bundled fixture を検索対象として使う local search tool を実装する。
- 実行結果 JSON に tool trace を保存し、後から挙動を検証できるようにする。
- `task08` の prompt / rubric / fixture を tool-use 前提に更新する。

## Non-Goals
- OpenAI / Anthropic / Gemini / OpenRouter の native tool calling への個別対応。
- 実際の外部 web 検索 API やクローラ接続。
- 任意コマンド実行やファイルシステム操作のような汎用ツール追加。
- judge モデル側での tool-use 実行。
- 全 task の一括 tool-use 化。

## Requirements
- **Functional**:
  - 被験モデルは、指定フォーマットの tool call を返すことで `web-search` と `open-document` を利用できる。
  - runtime は tool call を検出したら対応ツールを実行し、その結果を次ターンの会話履歴に追加して再度被験モデルを呼び出す。
  - tool call がなく最終回答のみ返った場合は、既存 task と同様にそのまま採点へ進む。
  - tool 呼び出しは task 単位で有効化し、未対応 task では現行の単発実行を維持する。
  - `web-search` は検索結果一覧だけを返し、本文参照は `open-document` で別途取得させる。
  - `task08` では複数の検索候補と本文を与え、機能追加記事と内部モデル据え置き記事を区別しないと正答に到達しづらいデータ構成にする。
  - 実行結果には `tool_trace` を保存し、少なくとも `tool_name`, `arguments`, `result_summary`, `step_index` を残す。
  - ループ回数、1 回あたりの tool 実行件数、返却文字数に上限を設ける。
- **Non-Functional**:
  - provider 依存の API 差分を吸収できるよう、tool runtime は adapter 抽象の上位で実装する。
  - 同一 fixture に対する search 結果は deterministic であること。
  - 外部ネットワーク不要で再現可能な評価にする。
  - tool call のパース失敗や未知ツール要求があっても、無限ループせず安全に終了する。
  - 既存 task のレスポンス形式、judge 呼び出し、Strict Mode 互換性を壊さない。

## Architecture
### 1. Tool protocol
- 被験モデルには system ではなく task prompt 内、または engine 側で付与する補助 instruction で次の契約を伝える。
- 途中で情報取得が必要な場合のみ、以下のような単一 JSON オブジェクトを専用タグで返させる。

```text
<tool_call>
{"name":"web-search","arguments":{"query":"..."}}
</tool_call>
```

- tool 実行結果は assistant ではなく tool message 相当の履歴として、例えば以下の形式で次ターンへ返す。

```text
<tool_result>
{"name":"web-search","ok":true,"results":[...]}
</tool_result>
```

- 最終回答はタグなしの通常テキストとし、runtime は「tool_call が 1 個だけ含まれる場合のみ継続、それ以外は最終回答」と解釈する。

### 2. Runtime placement
- 変更の中心は `core/benchmark_engine.py` とし、既存の `_call_subject_llm()` を単発実行から tool loop 対応へ拡張する。
- `adapters/base.py` の抽象は維持し、各 adapter は引き続き「1 回の completion」を提供するだけに留める。
- これにより provider ごとの native tool calling 差分を実装せずに済ませる。

### 3. Tool registry
- `core/tool_runtime.py` を新設し、以下を責務として持たせる。
  - tool 定義の registry
  - tool call パース
  - 1 step 実行と trace 生成
  - max_steps / max_errors / max_result_chars の制御
- task から runtime へ渡す設定は最小限とし、例として `ToolRuntimeConfig(enabled_tools, corpus_record_id, max_steps)` を持つ。

### 4. Search backend
- 初期実装では `GroundingCorpusStore` の保存形式を直接使うか、task 専用 bundled fixture を `grounding_corpus` 互換 JSON で持つ。
- `web-search(query)` は検索結果一覧を返す。
  - 返却値には `doc_id`, `title`, `url`, `snippet`, `rank` を含める。
  - スコアリングはまず単純な token overlap / 部分一致で十分とし、必要なら後で改善する。
- `open-document(doc_id)` は本文テキスト、タイトル、URL、source_type を返す。
- `task08` は最低でも以下のノイズを含める。
  - Deep Research の機能追加記事
  - GPT-5.1 / 5.2 系の一般アップデート記事
  - Deep Research 内部モデルの更新時期に触れる記事
  - 期間外情報

### 5. Result schema
- `TaskResult` に `tool_trace` を追加する。
- `tool_trace` は judge には渡さず、まずは保存とデバッグ用途に限定する。
- 将来的に「回答は正しいが根拠参照が弱い」ケースを再判定したい場合に備え、tool trace を残す。

## Task08 Data Design
- `prompts/08.md` は単独質問ではなく、以下を明示する。
  - 検索が必要なら `web-search` と `open-document` を使ってよいこと
  - 最終回答では「賢くなったか」の結論と、モデル更新と機能追加の区別を述べること
  - 根拠として参照した document を URL か title で列挙すること
- fixture は bundled resource として管理し、Strict Mode でも同一データを使えるようにする。
- rubric は「provider 固有 web search の有無」ではなく、「与えられた検索環境を正しく使って根拠に到達できたか」を評価する文面へ寄せる。

## Implementation Tasks
- runtime と task 有効化方式を決める。
  - 候補 A: task metadata JSON を追加する。
  - 候補 B: prompt front-matter で tool 設定を持つ。
  - 初期実装は変更範囲が狭い task metadata JSON を推奨する。
- `core/tool_runtime.py` を追加し、tool call パーサ、registry、step 制御を実装する。
- `BenchmarkEngine` に subject 用 multi-turn loop を追加し、既存単発実行と共存させる。
- local search tool を追加し、`grounding_corpus` 互換 fixture から検索結果と本文を返す。
- `TaskResult` と result JSON に `tool_trace` を追加する。
- `task08` 用 fixture、prompt、rubric を更新する。
- 最低限の運用ドキュメントとして fixture 追加手順と task 有効化手順を `README.md` か reference に追記する。

## Test Plan
- unit test:
  - tool call 文字列から `name` / `arguments` を安全に抽出できる。
  - 不正 JSON、未知ツール、複数 tool call 混入時に安全に終了できる。
  - `web-search` が deterministic な順位で結果を返す。
  - `open-document` が正しい document を返す。
- engine test:
  - 1 回目で tool call、2 回目で最終回答を返す stub adapter で multi-turn 実行を確認する。
  - max_steps 超過時に打ち切って最終応答またはエラー文を返す。
  - tool trace が `TaskResult.to_dict()` に含まれる。
- integration test:
  - `task08` fixture を使い、検索なしでは難しいが tool-use ありで正答に到達できるケースを固定テストする。
  - 従来 task では tool runtime が無効で、単発 completion のまま動くことを確認する。

## Risks
- prompt ベースの擬似 tool protocol は、モデルによっては厳密に従わず通常テキストで検索を捏造する可能性がある。
- search backend を単純化しすぎると、実際の「検索して選ぶ」難しさより単なる読解 task に寄る。
- fixture の作り方が甘いと、検索 1 回目のトップ結果だけで機械的に解けてしまう。
- trace を judge に見せない場合、tool-use の質そのものはスコアに直接反映されない。

## Rollback
- tool runtime は task 単位の opt-in にするため、不具合時は `task08` の tool 設定を外すだけで現行単発運用へ戻せるようにする。
- `TaskResult` の `tool_trace` は追加フィールドに留め、既存 consumer が未知キーを無視できる形にする。

## Effort Estimate
- Phase 1: runtime 最小実装と unit test で 1-2 日。
- Phase 2: `task08` fixture / prompt / rubric 更新と integration test で 1-2 日。
- Phase 3: 結果可視化や task metadata 整備を含めて合計 3-5 日程度を見込む。
- native tool calling への拡張は別計画とし、本計画には含めない。

## Deployment / Rollout
- まずは `task08` のみで有効化し、既存 01-07, 09-11 には影響を与えない。
- 初回リリースでは UI 変更を伴わず、bundled task resource の差し替えと runtime 追加のみで導入する。
- 評価結果を数 run 比較し、tool trace と最終スコアの相関を確認してから他 task への展開を判断する。
