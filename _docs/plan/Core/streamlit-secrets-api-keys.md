---
title: Persist API Keys via Streamlit Secrets
status: active
draft_status: n/a
created_at: 2026-02-18
updated_at: 2026-02-18
references: []
related_issues: []
related_prs: []
---

## Overview
- UIからLLMプロバイダのAPIキーを入力し、`.streamlit/secrets.toml` に保存して再起動後も利用できるようにする。

## Scope
- APIキー入力フォームをサイドバーに追加する。
- 入力されたAPIキーを `.streamlit/secrets.toml` に保存し、保存直後に読み込みを反映する。
- 保存後にモデル一覧取得を再実行できるようにする。
- `.streamlit/secrets.toml` をgit管理対象外とする運用をREADMEに追記する。

## Non-Goals
- ホスティング環境でのsecrets書き換え対応（Streamlit Cloud等は対象外）。
- APIキーの暗号化や外部シークレットマネージャ連携。

## Requirements
- **Functional**:
  - UIでOpenAI/Anthropic/Gemini/OpenRouterのAPIキーを入力できる。
  - 保存操作で `.streamlit/secrets.toml` が更新される。
  - 保存後にAPIキーがアプリに反映され、モデル一覧取得が成功する。
  - UI上にはキーの平文を表示しない（password入力）。
- **Non-Functional**:
  - `.streamlit/secrets.toml` のファイル権限・git管理に注意する。
  - 既存 `.env` 設定との競合を避け、優先順位を明確にする。

## Tasks
- `core/secrets_store.py` を追加し、secretsの読み書きを管理
- UIにAPIキー設定パネル（保存/クリア）を追加
- 保存後に`load_dotenv`相当の再読込とModelCatalog更新を実施
- READMEに運用注意点を追記

## Test Plan
- APIキー入力→保存後に `models/models.json` が更新されることを確認
- 再起動後もAPIキーが利用できることを確認
- 空入力時のバリデーションと保存抑止を確認

## Deployment / Rollout
- ローカル環境向けにREADMEで注意点を案内
