---
title: Grounding Corpus Pipeline
status: active
draft_status: n/a
created_at: 2026-04-04
updated_at: 2026-04-04
references: []
related_issues: []
related_prs: []
---

## Overview
- Deep Research 系評価のために、検索結果 JSON と本文テキストを対応付けて保存するコーパス作成フローを定義する。
- 実装として、ローカル JSON ストアと FastAPI endpoint を追加し、一覧・保存・取得を可能にする。

## Scope
- コーパス 1 件のデータモデル
- 収集 / 正規化 / 保存フロー
- grounding / 因果飛躍チェックでの利用方法

## Non-Goals
- 実際の外部クローラや検索 API 接続実装
- 大規模配布用データセットの整備

## Requirements
- **Functional**:
  - 検索クエリ、検索結果 JSON、採用記事 URL、本文テキスト、取得時刻を 1 レコードとして保持する。
  - 本文は検索結果と紐付け可能な形で保存する。
  - 後続の評価で、根拠有無と因果飛躍をチェックできる参照単位を持つ。
- **Non-Functional**:
  - データ品質確認と再取得のための provenance を残すこと。

## Tasks
- コーパスレコードの JSON スキーマを定義する。
- 収集から保存までの最小パイプラインを定義する。
- 評価での参照方法と品質チェック観点を整理する。

## Test Plan
- store unit test で保存・一覧・取得を確認する。
- API test で POST/GET round trip を確認する。

## Deployment / Rollout
- 保存領域は app data 配下の `grounding_corpus/` を使用する。
- 収集元の検索 API 接続や UI 取り込みは別タスクとする。
