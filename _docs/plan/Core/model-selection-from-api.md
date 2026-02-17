---
title: Model Selection From Provider APIs
status: active
draft_status: n/a
created_at: 2026-02-18
updated_at: 2026-02-18
references:
  - _docs/draft/requirements.md
  - _docs/draft/judge_sys_instruction.md
related_issues: []
related_prs: []
---

## Overview
- 起動時に各プロバイダのモデル一覧を取得し、UIで検索可能なドロップダウンから被験/ judgeモデルを選択できるようにする。
- judgeモデルは複数選択を可能にし、最低1モデル必須、3未満の場合は警告表示を行う。

## Scope
- models APIからの取得処理を追加し、`models/models.json` にキャッシュ保存する。
- UIで被験モデル（単一）とjudgeモデル（複数）を選択できる。
- judgeはプロバイダ固定ではなく「モデル名」単位で評価する。
- OpenRouterは `openrouter/...` の完全名表示で選択できる。
- UIに「再取得」ボタンを追加し、手動でモデル一覧を更新できる。

## Non-Goals
- models APIの認可方式の自動補完やトークン発行。
- モデル一覧の自動定期更新（起動時と手動更新のみ）。
- モデル選択を永続化するユーザー設定機能。

## Requirements
- **Functional**
  - 起動時にOpenAI/Anthropic/Gemini/OpenRouterのmodels APIを呼び出し、取得結果を正規化して保存する。
  - APIキーが未設定のプロバイダはスキップし、UIに警告を表示する。
  - UIで被験モデルの単一選択、judgeモデルの複数選択ができる。
  - judgeモデルは重複不可、最低1モデル必須。3未満の場合は強い警告を表示する。
  - judge結果の表示はモデル名をそのまま使い、UIで判別可能にする。
- **Non-Functional**
  - API取得エラー時は既存キャッシュを使用し、アプリ起動を継続する。
  - モデル一覧の取得は起動時に1回、手動再取得時に実行する。

## Tasks
- `models/` ディレクトリと `models/models.json` のキャッシュ構造を設計・実装
- models API取得の統合ローダーを追加（OpenAI/Anthropic/Gemini/OpenRouter）
- UIに被験モデル/ judgeモデルの検索ドロップダウンを追加
- judgeモデル選択数のバリデーション（重複禁止・3未満警告）
- 既存エンジンをモデル単位のjudgeに切り替え（adapter解決/結果キー変更）
- 再取得ボタン・取得失敗時の警告表示

## Test Plan
- APIキーが未設定のプロバイダがスキップされることを確認
- 取得成功時に `models/models.json` が更新されることを確認
- judgeモデルの重複禁止・3未満警告のUI動作確認
- OpenRouterの完全名表示を確認

## Deployment / Rollout
- ローカル動作確認後にREADMEへ設定方法を追記
- 既存E2Eテストは新UIで再実行する

## Implementation Notes
- 実装完了: `core/model_catalog.py` でmodels API取得と `models/models.json` へのキャッシュを追加
- UI更新: `ui/components.py` で被験/ judgeモデルの検索・複数選択・3未満警告・再取得ボタンを実装
- judge実行: `core/benchmark_engine.py` と `adapters/*` をモデル名単位で実行するよう変更
