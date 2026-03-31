---
title: Windows Local Browser App Distribution
status: proposed
draft_status: n/a
created_at: 2026-03-31
updated_at: 2026-03-31
references:
  - ../Core/resource-embedding-packaging.md
  - github-release-binary.md
related_issues: []
related_prs: []
---

## Overview
- 現行の `FastAPI + React/Vite` 実装を維持したまま、普通のユーザーが Python や Node.js を個別導入せずに使える Windows 向けローカルアプリとして配布可能にする。
- 初期リリースは Windows を最優先とし、起動時にローカルサーバーを立ち上げて既定ブラウザを開く「ブラウザ起動型ローカルアプリ」を採用する。
- Linux は次点候補として残すが、本計画の初期スコープには含めない。

## Scope
- Windows 向けのローカル配布アーキテクチャを定義する。
- フロントエンドを build し、FastAPI から静的配信する単一オリジン構成へ移行する。
- API キー、モデルキャッシュ、選択状態、結果 JSON の保存先を配布向けのユーザーデータ領域へ移行する。
- ルーブリック、プロンプト、judge system prompt の bundled resource と外部上書きの優先順位を整理する。
- ローカルアプリ起動用 launcher と Windows 向け配布物生成手順を定義する。
- GitHub Releases で Windows 向け成果物を継続配布できる方針を定義する。

## Non-Goals
- macOS 向け配布。
- 初期リリース時点での Linux 向け配布物提供。
- Electron / Tauri / Flutter などへの全面移行。
- マルチユーザーサーバー運用や SaaS 化。
- モバイル対応。

## Requirements
- **Functional**:
  - 配布物の起動だけでアプリ本体を利用開始できること。
  - 起動時にローカル HTTP サーバーを立ち上げ、既定ブラウザで UI を開くこと。
  - フロントエンドは開発用 Vite サーバーなしで動作すること。
  - `/api` とフロントエンド配信を同一プロセス・同一オリジンで提供すること。
  - API キーを UI から保存・削除でき、再起動後も復元できること。
  - API キー以外の永続データ（モデルキャッシュ、前回選択、結果 JSON）はユーザーごとの app data 配下に保存されること。
  - ルーブリック、プロンプト、judge system prompt は bundled resource から読めること。
  - `LLM_BENCHMARK_RUBRICS_DIR`、`LLM_BENCHMARK_PROMPTS_DIR`、`LLM_BENCHMARK_JUDGE_SYSTEM_PROMPT_PATH` による外部上書きが継続利用できること。
  - Windows 向け配布物を GitHub Releases に載せられること。
- **Non-Functional**:
  - 現行の Python 評価ロジックと React UI をできるだけ再利用すること。
  - 開発時の `uvicorn + vite dev` 体験は維持し、配布用構成と共存させること。
  - 秘密情報の保存方式は、実装 ROI とサポート負荷を優先して決定すること。
  - Windows 向け初期リリースではインストールと起動の単純さを優先すること。

## Architecture

### 配布形態
- 初期リリースは Windows 向けのブラウザ起動型ローカルアプリとする。
- アプリ起動用 launcher がローカルの FastAPI サーバーを起動し、既定ブラウザでアプリ URL を開く。
- フロントエンドは事前 build した静的ファイルを FastAPI から配信し、API は同じサーバーの `/api/*` で処理する。

### フロントエンド配信
- 開発時は既存の Vite dev server を維持する。
- 配布時は `frontend/dist` を生成し、FastAPI で静的配信する。
- SPA ルーティングを成立させるため、非 `/api` パスは `index.html` fallback を返す。

### 永続化方針
- 非秘密情報は app data 配下に保存する。
  - 結果 JSON
  - モデルカタログキャッシュ
  - 前回選択状態
- 秘密情報である API キーは、**初期リリースでは app data 配下の専用ファイル保存を採用する**。
- 判断理由:
  - Windows のみを対象にしても、OS キーチェーン連携は backend 依存、ビルド差異、障害切り分けのコストが増える。
  - 初期リリースでは「確実に配布して動かす」ことの ROI が高い。
  - ただし将来の Windows Credential Manager 対応に備えて、秘密情報保存は抽象化レイヤーを設け、置き換え可能な設計にする。
- 将来拡張:
  - Phase 2 以降で `keyring` などを用いた Windows Credential Manager 対応を再評価する。

### リソース解決方針
- 優先順位は以下とする。
  1. 環境変数による外部指定
  2. 配布物に同梱された bundled resource
  3. 開発環境の相対パス
- bundled resource の仕様は `_docs/plan/Core/resource-embedding-packaging.md` を前提として統合する。

### 配布物方針
- 初期リリース成果物は Windows x86_64 を対象とする。
- まずは `onedir` ベースの配布を優先し、挙動を安定化させる。
- その後、必要に応じて setup 形式のインストーラーを追加する。
- リリース自動化は `_docs/plan/DevOps/github-release-binary.md` と整合させ、Windows 向け成果物を優先実装する。

## Tasks
1. 配布用アプリ構成の基盤整備
   - FastAPI から build 済み frontend を静的配信できるようにする。
   - SPA fallback を追加し、`BrowserRouter` のまま配布可能にする。
   - 開発用構成と配布用構成の切り替え方法を整理する。
2. 保存先の app data 移行
   - 結果、モデルキャッシュ、選択状態、API キーの保存先を app data 配下に統一する。
   - API キー保存処理は専用インターフェース経由にし、将来の keychain 対応余地を残す。
3. bundled resource 対応
   - rubrics/prompts/judge_system_prompt の解決ロジックを packaged 実行で動く形にする。
   - 環境変数による外部パス上書きとの優先順位を実装に反映する。
4. launcher 実装
   - FastAPI をローカルで起動し、ブラウザを自動起動する専用エントリポイントを追加する。
   - ポート競合や起動失敗時のユーザー向けメッセージを定義する。
5. Windows 配布パッケージ作成
   - PyInstaller などで Windows 向け配布物を生成する。
   - 必要な hidden import や bundled file を定義する。
   - 初期版は `onedir` を成立させる。
6. リリース自動化
   - Windows 向け成果物を GitHub Actions でビルドできるようにする。
   - Release 添付物と命名規則を既存 plan に沿って整理する。
7. 配布ドキュメント整備
   - README と配布ガイドを、エンドユーザー向けの起動・保存先・トラブルシュートを含む内容に更新する。

## Test Plan
- 開発環境で frontend build 後、FastAPI 単体で UI と `/api` が動作することを確認する。
- packaged 実行時に、設定画面・評価実行・履歴参照・結果詳細表示まで一連の操作が通ることを確認する。
- API キー保存後にアプリを再起動し、キー状態が復元されることを確認する。
- モデルキャッシュ、前回選択、結果 JSON が app data 配下に保存されることを確認する。
- `LLM_BENCHMARK_RUBRICS_DIR`、`LLM_BENCHMARK_PROMPTS_DIR`、`LLM_BENCHMARK_JUDGE_SYSTEM_PROMPT_PATH` の各上書きが packaged 実行でも有効であることを確認する。
- rubrics/prompts を外部指定しない場合でも bundled resource から正常に読み込めることを確認する。
- launcher が空きポートで起動し、既定ブラウザを開けることを確認する。
- ポート競合や resource 読み込み失敗時に、ユーザーが理解可能なエラーになることを確認する。
- Windows x86_64 のクリーン環境で、Python/Node 未導入でもアプリが起動できることを確認する。

## Deployment / Rollout
- Phase 1: ローカル実行時に `uvicorn + built frontend` が成立する状態まで実装する。
- Phase 2: launcher と app data 保存へ移行し、Windows で手動配布テストを行う。
- Phase 3: Windows 向け packaged 配布物を生成し、GitHub Releases に載せる。
- Phase 4: 初期運用後に API キー保存の UX とサポート負荷を確認し、Windows Credential Manager 対応の必要性を再評価する。
- Linux 対応は Windows 初期配布後の別フェーズとして扱う。
