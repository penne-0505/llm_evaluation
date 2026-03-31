---
title: Windows Portable ZIP Execution Breakdown
status: proposed
draft_status: n/a
created_at: 2026-04-01
updated_at: 2026-04-01
references:
  - windows-portable-zip-finalization.md
  - windows-local-browser-distribution.md
  - ../Core/resource-embedding-packaging.md
related_issues: []
related_prs: []
---

## Overview
- `DevOps-Feat-17` を、別の作業者がそのまま着手できる実行単位に分解した handoff 用 plan。
- 本ドキュメントは、各子タスクの対象ファイル、実装内容、確認方法、完了条件を明確にすることを目的とする。

## Scope
- Windows portable ZIP 最終化の残作業を 4 つの子タスクに分割する。
- 各子タスクごとに変更対象、想定実装、検証方法、依存関係を明文化する。
- 子タスク完了後に `DevOps-Feat-17` を close できる判定基準を定義する。

## Non-Goals
- この plan 自体で実装を行うこと。
- Linux/macOS 配布の設計追加。
- installer 形式の再検討。

## Requirements
- **Functional**:
  - 各子タスクは TODO 上で独立着手可能であること。
  - 各子タスクについて、最低限の対象ファイルと確認コマンドが提示されていること。
  - `DevOps-Feat-17` 完了時に必要な acceptance criteria が分かること。
- **Non-Functional**:
  - 現行コードベースの実装状態に即した内容であること。
  - TODO の Steps と plan の説明が過不足なく対応していること。

## Current State
- frontend build は `server.py` から静的配信できる。
- `launcher.py` でローカルサーバー起動とブラウザ起動ができる。
- 保存先は `core/app_paths.py` 経由で app data/config に寄せられている。
- Windows 向け PyInstaller spec と GitHub Actions workflow の土台は追加済み。
- 未完了なのは主に以下。
  - user override ディレクトリの実装
  - launcher / packaged UX の最終調整
  - Windows 実機での配布確認
  - Release 成果物・ユーザー向けガイドの仕上げ

## Work Packages

### WP1: user override 実装
- **TODO**: `Core-Enhance-18`
- **目的**: prompt/rubric/judge system prompt を user override で差し替え可能にする。
- **対象ファイル**:
  - `core/app_paths.py`
  - `server.py`
  - 必要なら `tests/test_server_frontend.py` に加えて新規 test
  - `README.md`
- **想定変更**:
  - app data 配下に `overrides/` 系パスを追加
  - 解決優先順位を `env override > user override > bundled` に変更
  - 読み込み元を確認しやすいログまたは API 応答を追加
- **完了条件**:
  - user override に置いた prompt/rubric/system prompt が bundled より優先される
  - 環境変数 override が user override より優先される
  - テストで優先順位が固定されている
- **確認コマンド**:
  - `uv run --with pytest pytest`

### WP2: portable 起動 UX 調整
- **TODO**: `Core-Enhance-19`
- **目的**: portable 実行時の起動失敗やポート競合時に、ユーザーが原因を理解できる状態にする。
- **対象ファイル**:
  - `launcher.py`
  - `server.py`
  - `README.md`
- **想定変更**:
  - ブラウザ起動失敗時のメッセージ整備
  - ポート競合時の案内改善
  - `frontend/dist` 不足時のエラーメッセージを配布利用者向けに調整
  - 必要なら launcher 用の smoke test 追加
- **完了条件**:
  - 起動成功/失敗時のメッセージが portable 利用者向けに明確
  - `prism-llm-eval` 起動の基本 smoke test がある、または既存 smoke 手順が README に明記されている
- **確認コマンド**:
  - `npm run build --prefix frontend`
  - `timeout 8s uv run prism-llm-eval --no-browser --port 8765`

### WP3: Windows 実機配布検証と packaging 修正
- **TODO**: `DevOps-Test-20`
- **目的**: Windows クリーン環境で ZIP 展開後の実利用フローを確認し、不足を詰める。
- **対象ファイル**:
  - `packaging/windows/prism-llm-eval.spec`
  - `scripts/build_windows_bundle.ps1`
  - `.github/workflows/windows-bundle.yml`
  - 実機検証結果に応じて `launcher.py`, `server.py`
- **想定変更**:
  - hidden import / DLL / 同梱ファイル不足の修正
  - Windows 向け build 手順の修正
  - 必要なら smoke test 手順を docs 化
- **完了条件**:
  - Windows 上で ZIP 展開後に exe 実行だけで起動できる
  - API キー保存、モデル取得、評価実行、履歴表示が通る
  - 実機で発見した packaging 不備が docs またはコードに反映されている
- **確認コマンド**:
  - `./scripts/build_windows_bundle.ps1`
  - 実機で `dist/prism-llm-eval/` を ZIP 化して起動確認

### WP4: Release 成果物とユーザーガイドの最終化
- **TODO**: `DevOps-Doc-21`
- **目的**: portable ZIP を release できる状態にし、ユーザー向け利用手順を確定する。
- **対象ファイル**:
  - `.github/workflows/windows-bundle.yml`
  - `README.md`
  - 必要なら `_docs/guide/` 配下の新規ガイド
- **想定変更**:
  - artifact 名を portable ZIP 前提で固定
  - SHA256 を追加するか判断して反映
  - ZIP 展開、起動、保存先、override 方法、トラブルシュートをドキュメント化
- **完了条件**:
  - Release 生成物名が固定されている
  - エンドユーザー向けガイドだけで ZIP 配布の利用を開始できる
  - prompt 差し替え方法が明記されている
- **確認コマンド**:
  - `uv run --with pytest pytest`
  - workflow の dry-run 相当確認、または Actions 実行結果確認

## Parent Task Completion Criteria
- `Core-Enhance-18`, `Core-Enhance-19`, `DevOps-Test-20`, `DevOps-Doc-21` が完了している。
- Windows 上で portable ZIP からの起動確認が取れている。
- user override の挙動と利用方法が docs に反映されている。
- GitHub Releases に載せる成果物名が固定されている。

## File Map
- 実行入口: `launcher.py`
- frontend 配信・resource 解決: `server.py`
- app data/config 解決: `core/app_paths.py`
- 永続化: `core/secrets_store.py`, `core/model_catalog.py`, `core/selection_store.py`, `core/result_storage.py`
- packaging: `packaging/windows/prism-llm-eval.spec`, `scripts/build_windows_bundle.ps1`, `.github/workflows/windows-bundle.yml`
- 既存方針: `_docs/plan/DevOps/windows-portable-zip-finalization.md`, `_docs/plan/Core/resource-embedding-packaging.md`

## Handoff Notes
- まず WP1 と WP2 を先に片付けると、Windows 実機検証の手戻りが減る。
- WP3 は Windows 環境を使える作業者に寄せる。
- WP4 は WP3 の結果を受けて最終文言を固める。
- 親タスク `DevOps-Feat-17` は、上記 4 タスクの完了確認後に close する。
