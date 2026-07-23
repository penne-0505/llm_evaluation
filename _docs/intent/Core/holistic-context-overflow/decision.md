---
title: "Intent: Holistic bundled_responses context overflow handling"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-23
updated_at: 2026-07-23
references:
  - "_docs/archives/plan/Core/holistic-context-overflow/plan.md"
  - "_docs/qa/Core/holistic-context-overflow/test-plan.md"
  - "_docs/archives/survey/Core/holistic-context-overflow/survey.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# Intent: Holistic bundled_responses context overflow handling

## Context

包括評価は `run_holistic_task` が `non_creative_responses` を `_build_bundled_responses` で
連結し、`_run_judge_evaluation` へ `subject_response` として渡す。judge user prompt には
加えて trusted rubric、holistic eval prompt、trust envelope が含まれる。現行実装には
サイズ上限チェックがなく、タスク数・出力長の増加で judge provider の context length エラーが
起きうる。

adapter 層にはモデルごとの context window を返す共通 API がなく、OpenRouter 等のメタデータ
取得も run 時点では未利用である。したがって、見積もりと fallback の方針を Intent で固定する。

## Decisions

### DEC-001: judge 入力予算は固定 overhead を差し引いた残りを bundled answer に割り当てる

- **What**: holistic judge 呼び出し前に、system prompt + rubric + eval prompt + envelope +
  安全マージンを固定 overhead として見積もり、残りを `untrusted_subject_answer` の上限とする。
  サイズ見積もりは v1 では文字数ベース（例: 4 文字 ≈ 1 token）とし、将来 tiktoken 等へ
  差し替え可能にする。
- **Why**: provider へ送る前に予算を決めないと、連結テキスト全体が一括で拒否され、run が
  サイレントに近い失敗（judge error のみ）で終わる。
- **Change freedom**: overhead の内訳、安全マージン率、見積もり関数（chars vs tokenizer）は、
  誤拒否率と誤受け入れ率のバランスを保つ限り変更できる。
- **Why not**: API 呼び出し後のエラーだけに頼らない。エラー時点では truncation 判断に必要な
  構造情報（どの task を削ったか）を失いやすい。
- **Revisit when**: adapter が信頼できる input token 上限と usage 見積もりを返すようになった時。

### DEC-002: v1 の overflow 処理は単一 judge 呼び出し内の切り詰めに限定する

- **What**: 予算超過時は judge 呼び出しを分割せず、bundled subject answer を切り詰めて
  1 回の `_run_judge_evaluation` で完走する。分割評価と chunk 間スコア集約は本 Intent の
  対象外とする。
- **Why**: 分割は rubric 解釈・confidence・aggregated score の意味論を再定義する必要があり、
  overflow 防止の最小変更より scope が大きい。
- **Change freedom**: 切り詰め単位（task 丸ごと drop vs response body truncate）、削る順序
  （末尾 task 優先 vs 最短 response 優先）は、横断文体評価の証拠量を過度に損なわない限り
  変更できる。
- **Why not**: v1 から split + aggregate を入れない。集約方針未定のまま複数 judge スコアを
  合成すると、結果の再現性と UI 表示が曖昧になる。

### DEC-003: 切り詰めは task 境界と見出し構造を保ち、末尾から削る

- **What**: 超過時は bundled answer 内の **末尾 task** から順に完全除外する。全 task を
  残したまま 1 task も収まらない場合のみ、その task の `#### 被験LLMの回答` 本文を末尾から
  文字 truncate し、見出しと入力プロンプトは維持する。
- **Why**: 先頭 task だけ残すと後半文体の証拠が消え、包括評価の横断性が偏る。末尾優先 drop
  は execution order に沿い、メタデータで除外 task を明示すれば judge と利用者が解釈できる。
- **Change freedom**: 「creative 除外後の順序」以外の drop 優先度（例: 最短 response 優先）は
  Intent 更新と QA 再検証の上で変更できる。
- **Why not**: 単一巨大 response の先頭固定長 truncate だけにしない。task 境界が崩れると
  holistic rubric が要求する横断比較ができない。

### DEC-004: overflow 処理は holistic task メタデータへ必ず記録する

- **What**: truncation または task drop が発生した場合、holistic `TaskResult` に
  `bundling_metadata`（名称は実装で確定）を付与し、`truncated: true`、除外 task 一覧、
  推定 token / 文字数、適用上限、処理種別（`task_drop` / `response_truncate` / `none`）を
  含める。
- **Why**: スコアだけでは「入力不足で judge が見えていない」ことを利用者が判断できない。
  再現性と監査のため run artifact に残す。
- **Change freedom**: フィールド名、ログ verbosity、Result UI での表示位置は変更できる。
  記録必須の事実（truncated 有無、除外範囲）は維持する。
- **Why not**: ログのみに残さない。結果 JSON を見ない consumer では検知できない。

## Consequences / Impact

- holistic judge 入力は最大でもモデル予算内に収まり、context length exceeded の頻度が下がる。
- 超過 run では一部 task 証拠が欠落しうるため、judge `confidence` 低下やスコア解釈への
  注意が必要になる。
- `TaskResult.to_dict()` と frontend 型は optional metadata を additive に受け取れる。

## Quality Implications

- engine unit test で oversized fixture により truncation 分岐と metadata を直接確認する。
- 非超過 fixture では `_build_bundled_responses` 出力が従来と一致することを回帰確認する。

## Intent-derived Invariants

- INV-001 (from DEC-003): 非超過の bundled_responses について、`_build_bundled_responses` の出力形式（`### タスク:` 見出し、`---` 区切り）は変更しない。
- INV-002 (from DEC-004): overflow 処理が走った holistic task は `bundling_metadata.truncated === true` を必ず持つ。

## Rollback / Follow-ups

- rollback は budget check、truncation、metadata 付与を同時に戻す。旧 results は metadata なし
  として読める。
- 分割評価が必要になった場合は新 Intent で chunk 境界と score aggregation を定義してから
  実装する。
