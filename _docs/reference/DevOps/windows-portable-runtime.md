---
title: Windows Portable Runtime Reference
status: active
draft_status: n/a
created_at: 2026-04-01
updated_at: 2026-04-01
references:
  - ../../intent/DevOps/windows-portable-zip-distribution.md
  - ../../guide/DevOps/windows-portable-zip.md
related_issues: []
related_prs: []
---

## Overview
- Windows portable ZIP 配布における runtime resource 解決、診断 API、成果物命名の実装仕様をまとめる。
- 実装の単一参照点は `core/app_paths.py`, `server.py`, `launcher.py`, `.github/workflows/windows-bundle.yml`, `scripts/build_windows_bundle.ps1`。

## API
### Runtime Resource Resolution
- **Summary**: prompt / rubric / judge system prompt は `env override > user override > bundled` の順で解決される。local search runtime 用の `task_configs/` と `task_fixtures/` は bundled resource として配布される。
- **Parameters**:
  - `LLM_BENCHMARK_PROMPTS_DIR` (dir path) — prompt 上書きディレクトリ
  - `LLM_BENCHMARK_RUBRICS_DIR` (dir path) — rubric 上書きディレクトリ
  - `LLM_BENCHMARK_JUDGE_SYSTEM_PROMPT_PATH` (file path) — judge system prompt 上書きファイル
- **Returns**:
  - prompt override: app data 配下の `overrides/prompts/<task_id>.md`
  - rubric override: app data 配下の `overrides/rubrics/<task_id>.md`
  - judge system prompt override: app data 配下の `overrides/judge_system_prompt.md`
  - task config: bundled の `task_configs/<task_id>.json`
  - task fixture: bundled の `task_fixtures/<task_id>.json`
  - 未配置ファイルは bundled resource へフォールバック
- **Errors**:
  - 環境変数のパスが不正な場合は警告ログを出し、次の layer へフォールバック
- **Examples**:
  - `01.md` の prompt だけ user override に置いた場合、rubric は bundled を使い、prompt だけ user override を使う

### `GET /api/tasks`
- **Summary**: 利用可能な task 一覧を返す。portable runtime では解決元の source も返す。
- **Parameters**: なし
- **Returns**:
  - `id` (string) — task id
  - `type` (string) — task type
  - `prompt` (string) — 解決済み prompt 本文
  - `prompt_source` (string) — `env_override | user_override | bundled`
  - `rubric_source` (string) — `env_override | user_override | bundled`
- **Errors**:
  - 有効な prompt / rubric の組が 0 件の場合は空配列
- **Examples**:
  - `{"id":"01","type":"fact","prompt":"...","prompt_source":"user_override","rubric_source":"bundled"}`

### `GET /api/resources`
- **Summary**: runtime resource の解決状態と候補 layer を返す。
- **Parameters**: なし
- **Returns**:
  - `rubrics.layers[]` — rubric 解決候補。各要素は `source`, `path`, `exists`
  - `prompts.layers[]` — prompt 解決候補。各要素は `source`, `path`, `exists`
  - `judge_system_prompt.resolved_path` (string) — 実際に使われた path
  - `judge_system_prompt.resolved_source` (string) — `env_override | user_override | bundled | missing`
  - `judge_system_prompt.exists` (bool) — 実在有無
  - `judge_system_prompt.layers[]` — judge system prompt の候補 layer
- **Errors**:
  - endpoint 自体は 200 を返し、欠損は `exists: false` と `resolved_source: "missing"` で表現する
- **Examples**:
  - support 時に `http://127.0.0.1:<port>/api/resources` を開き、user override が実際に読まれているか確認する

### Portable Launcher Preflight
- **Summary**: launcher 起動前に frontend build と resource の不足を検査する。
- **Parameters**:
  - `--host` (string) — bind host
  - `--port` (int) — 希望ポート。使用中なら空きポートへフォールバック
  - `--no-browser` (flag) — ブラウザ自動起動を抑止
- **Returns**:
  - frontend / resource が揃っていれば server を起動
  - 指定ポートが使用中なら代替ポートを採用して stderr に案内
- **Errors**:
  - `frontend/dist/index.html` 不足
  - task 0 件
  - `judge_system_prompt.md` 不足
- **Examples**:
  - `timeout 8s uv run prism-llm-eval --no-browser --port 8765`

### Release Artifact Naming
- **Summary**: Windows 配布成果物は portable ZIP と `.sha256` を生成する。
- **Parameters**:
  - workflow tag push: `v*`
  - local build script: `-Version <string>`
- **Returns**:
  - ZIP: `prism-llm-eval-{version}-windows-x86_64.zip`
  - hash: `prism-llm-eval-{version}-windows-x86_64.zip.sha256`
- **Errors**:
  - GitHub Releases 添付には workflow 側で `contents: write` が必要
- **Examples**:
  - `./scripts/build_windows_bundle.ps1 -Version v0.1.0`

## Notes
- app data 配下の永続データは ZIP 展開先と独立しているため、再展開や配置換えを行っても継続利用できる。
- `task08` の local search runtime は bundled の `task_configs/08.json` と `task_fixtures/08.json` を参照するため、portable ZIP には両方が同梱される必要がある。
- `.sha256` は `sha256sum` 互換の `"<hash>  <filename>"` 形式で生成する。
