---
title: Windows Portable ZIP Distribution Finalization
status: proposed
draft_status: n/a
created_at: 2026-04-01
updated_at: 2026-04-01
references:
  - windows-local-browser-distribution.md
  - windows-portable-zip-execution-breakdown.md
  - github-release-binary.md
  - ../Core/resource-embedding-packaging.md
related_issues: []
related_prs: []
---

## Overview
- Windows 向け配布の最終形を「installer」ではなく「portable ZIP」に固定し、展開後に実行ファイルを起動するだけでアプリがフル起動する状態を完成させる。
- 既存の `FastAPI + built frontend + launcher + PyInstaller onedir` をベースに、Windows 実機での成立性、ユーザー差し替えリソース運用、リリース成果物の整備を詰める。

## Scope
- Windows x86_64 向け portable ZIP の完成条件を定義する。
- 展開後に `prism-llm-eval.exe` を実行するだけでアプリが起動する UX を確定する。
- bundled resource と user override の優先順位を portable 運用向けに具体化する。
- Windows 実機での packaged 実行検証項目と不具合修正方針を整理する。
- GitHub Releases 向けに portable ZIP 成果物の命名・生成・添付手順を定義する。
- エンドユーザー向けドキュメントに ZIP 配布前提の使用手順を反映する。

## Non-Goals
- MSI / setup.exe / インストーラー形式の提供。
- macOS / Linux 向け portable 配布。
- Windows Credential Manager 対応の本実装。
- 自動更新機構の導入。
- prompt/rubric を UI から直接編集するエディタ機能。

## Requirements
- **Functional**:
  - ユーザーは ZIP を展開し、`prism-llm-eval.exe` の実行だけでアプリを起動できること。
  - Python、Node.js、uv を個別導入していない Windows 環境でも起動できること。
  - 起動時にローカルサーバーが立ち上がり、既定ブラウザで UI が開くこと。
  - API キー、モデルキャッシュ、前回選択、結果 JSON は app data 配下に保存されること。
  - prompt/rubric/judge system prompt は以下の優先順位で解決されること。
    1. 明示的な外部指定（環境変数）
    2. user override ディレクトリ
    3. portable ZIP に同梱された bundled resource
  - user override を利用するための保存場所と差し替え方法がドキュメント化されていること。
  - portable ZIP が GitHub Releases へ添付できること。
- **Non-Functional**:
  - 配布物は portable として自己完結し、インストールを前提にしないこと。
  - 既存の開発用起動フロー（`uvicorn + vite dev`）は維持すること。
  - 既存ユーザーの app data 保存内容を壊さないこと。
  - 配布物名、実行ファイル名、README 上の表記を統一すること。

## Tasks
1. user override 仕様の完成
   - app data 配下に `overrides/prompts`、`overrides/rubrics`、`overrides/judge_system_prompt.md` を置けるようにする。
   - 環境変数 override と bundled resource の間に user override を挿入した優先順位を実装へ反映する。
   - 現在どのソースを読んでいるかをログまたは API 応答で追跡しやすくする。
2. portable 起動 UX の仕上げ
   - launcher の起動メッセージ、ブラウザ起動失敗時の挙動、ポート競合時の説明を整理する。
   - frontend build 不足や resource 欠落時のエラーメッセージを配布利用者向けに調整する。
3. Windows 実機検証と packaged 調整
   - Windows のクリーン環境で ZIP 展開後の起動、API キー保存、評価実行、履歴参照を通す。
   - PyInstaller の hidden import / DLL / runtime 依存を Windows 実機の結果に合わせて調整する。
4. Release 成果物の固定化
   - GitHub Actions で Windows portable ZIP を安定生成できるようにする。
   - 成果物名を `prism-llm-eval-{tag}-windows-x86_64.zip` に統一する。
   - 必要に応じて SHA256 も同時生成する。
5. 配布ドキュメントの最終化
   - README を portable ZIP 配布前提で仕上げる。
   - user override の保存先、差し替え方法、トラブルシュートを guide として追加する。

## Execution Breakdown
- 着手単位への分解と handoff 情報は `_docs/plan/DevOps/windows-portable-zip-execution-breakdown.md` を参照する。
- TODO 上では `Core-Enhance-18`, `Core-Enhance-19`, `DevOps-Test-20`, `DevOps-Doc-21` に分解して進める。

## Test Plan
- Windows x86_64 の Python/Node 未導入環境で ZIP 展開後に `prism-llm-eval.exe` が起動することを確認する。
- 起動時に既定ブラウザが開き、`/settings` から通常操作を開始できることを確認する。
- API キー保存後に再起動して、キー状態が復元されることを確認する。
- モデル取得、評価実行、履歴参照、詳細表示まで一連の操作が packaged 実行で通ることを確認する。
- bundled resource のみで動作することを確認する。
- user override を配置した場合に bundled resource より優先されることを確認する。
- 環境変数 override を指定した場合に user override より優先されることを確認する。
- ZIP を別ディレクトリへ再配置しても、app data 側の永続データが引き続き利用できることを確認する。
- GitHub Actions 生成物をダウンロードし、手元 Windows 環境で起動できることを確認する。

## Deployment / Rollout
- Phase 1: user override 実装と launcher UX の調整を行う。
- Phase 2: Windows 実機で portable ZIP の手動検証を実施し、packaging の不足を修正する。
- Phase 3: GitHub Releases 向け portable ZIP 生成を固定し、成果物命名を確定する。
- Phase 4: README と配布ガイドを portable 運用前提で更新し、installer 前提の記述を整理する。
