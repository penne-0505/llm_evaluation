---
title: Windows Portable ZIP Guide
status: active
draft_status: n/a
created_at: 2026-04-01
updated_at: 2026-04-01
references:
  - ../../intent/DevOps/windows-portable-zip-distribution.md
  - ../../reference/DevOps/windows-portable-runtime.md
related_issues: []
related_prs: []
---

## Overview
- Windows 向け配布物 `prism-llm-eval-{tag}-windows-x86_64.zip` の利用手順をまとめた guide。
- 対象読者は、GitHub Releases から ZIP を取得して使うエンドユーザーと、配布前の確認を行う開発者。

## Prerequisites
- Windows x86_64 環境
- GitHub Releases から取得した portable ZIP
- 利用する LLM プロバイダの API キー

## Setup / Usage
1. GitHub Releases から `prism-llm-eval-{tag}-windows-x86_64.zip` と `prism-llm-eval-{tag}-windows-x86_64.zip.sha256` を取得する。
2. 必要に応じて SHA256 を照合する。
3. ZIP を任意のフォルダへ展開する。
4. 展開先の `prism-llm-eval.exe` を実行する。
5. 初回起動後、既定ブラウザで開いた設定画面から API キーを保存する。

保存先は ZIP の展開先ではなく app data 配下を使用する。Windows では通常 `%LOCALAPPDATA%\Prism\prism-llm-eval\` 以下の data/config 領域が使われる。

- API キー: app data / config 配下の `secrets.toml`
- モデルキャッシュ: `%LOCALAPPDATA%\Prism\prism-llm-eval\models\models.json`
- 前回の選択状態: `%LOCALAPPDATA%\Prism\prism-llm-eval\models\last_selection.json`
- 実行結果: `%LOCALAPPDATA%\Prism\prism-llm-eval\results\`
- user override: `%LOCALAPPDATA%\Prism\prism-llm-eval\overrides\`

user override は以下の優先順位で解決される。
1. 環境変数 override
2. user override
3. bundled resource

配置先:
- prompt override: `%LOCALAPPDATA%\Prism\prism-llm-eval\overrides\prompts\<task_id>.md`
- rubric override: `%LOCALAPPDATA%\Prism\prism-llm-eval\overrides\rubrics\<task_id>.md`
- judge system prompt override: `%LOCALAPPDATA%\Prism\prism-llm-eval\overrides\judge_system_prompt.md`

環境変数 override:
- `LLM_BENCHMARK_PROMPTS_DIR`
- `LLM_BENCHMARK_RUBRICS_DIR`
- `LLM_BENCHMARK_JUDGE_SYSTEM_PROMPT_PATH`

## Best Practices
- ZIP は毎回新しいフォルダへ展開する。既存展開先へ手作業で上書きするより、展開し直した方が不足ファイルを切り分けやすい。
- prompt / rubric の override は必要なファイルだけ置けばよい。未配置の task は bundled resource に自動フォールバックする。
- `task08` の local search tool-use は bundled の `task_configs/08.json` と `task_fixtures/08.json` を使うため、portable ZIP でもそのまま動作する。
- support 用には `http://127.0.0.1:<port>/api/resources` を開くと、judge system prompt の解決元と候補 layer を確認できる。
- 開発環境で portable 相当の起動確認をするときは `npm run build --prefix frontend` 後に `uv run prism-llm-eval --no-browser --port 8765` を使う。

## Troubleshooting
- ブラウザが自動で開かない:
  - コンソールに表示された URL を手動で開く。
- 起動前チェックで `frontend/dist/index.html` が見つからない:
  - 開発環境では `npm run build --prefix frontend` を実行する。
  - 配布 ZIP では展開し直し、`frontend/dist` が含まれているか確認する。
- 起動前チェックで task が 0 件になる:
  - `overrides/prompts` と `overrides/rubrics` のファイル名が同じ task id で揃っているか確認する。
  - override が不要なら `LLM_BENCHMARK_PROMPTS_DIR` / `LLM_BENCHMARK_RUBRICS_DIR` の設定を外す。
- 指定したポートで起動しない:
  - そのポートが使用中。launcher は空きポートへフォールバックするため、コンソール出力の URL を利用する。

## References
- `_docs/intent/DevOps/windows-portable-zip-distribution.md`
- `_docs/reference/DevOps/windows-portable-runtime.md`
- `README.md`
