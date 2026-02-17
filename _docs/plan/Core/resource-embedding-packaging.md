---
title: Resource Embedding and Custom Path Packaging
status: active
draft_status: n/a
created_at: 2026-02-18
updated_at: 2026-02-18
references: []
related_issues: []
related_prs: []
---

## Overview
- リソース埋め込みに備えつつ、外部パス上書きの仕様と実装を整備する。
- ルーブリック/プロンプト/システムプロンプトの読み込み先を環境変数で分離指定できるようにする。

## Scope
- ルーブリック/プロンプト/システムプロンプトの配置方法と優先順位を定義する。
- 実行時に外部パスで上書きできる仕様を確定し、アプリ側の解決ロジックを実装する。
- ルーブリックとプロンプトは別ディレクトリで指定できるようにする。

## Non-Goals
- すべての配布形式に対する完全な対応。
- 既存のファイル構成やタスク形式の変更。
- バンドル埋め込みの実装（調査・選定後に別タスクで実施）。

## Requirements
- **Functional**:
  - 外部パス上書きの環境変数を定義する:
    - `LLM_BENCHMARK_RUBRICS_DIR`
    - `LLM_BENCHMARK_PROMPTS_DIR`
    - `LLM_BENCHMARK_JUDGE_SYSTEM_PROMPT_PATH`
  - ルーブリック/プロンプトは別ディレクトリで指定でき、片方のみの指定も許可する。
  - 指定パスが存在しない場合は警告を表示し、既定ローカルにフォールバックする。
  - 優先順位は「外部パス → 既定ローカル → （将来の埋め込み）」とする。
- **Non-Functional**:
  - 既存の開発用ディレクトリ構成を維持する。
  - 既存の挙動（既定ローカルのみで動作）を壊さない。

## Tasks
- 外部パス上書きの仕様をPlanに反映する。
- アプリのリソース解決ロジックを実装し、UIで警告を表示する。
- README/.env.example を更新し、環境変数の使い方を記載する。

## Test Plan
- `LLM_BENCHMARK_RUBRICS_DIR` のみ指定した場合、ルーブリックのみ外部から読み込まれる。
- `LLM_BENCHMARK_PROMPTS_DIR` のみ指定した場合、プロンプトのみ外部から読み込まれる。
- 両方指定した場合、それぞれの外部ディレクトリが使用される。
- `LLM_BENCHMARK_JUDGE_SYSTEM_PROMPT_PATH` 指定時に外部ファイルを読み込む。
- 指定パスが存在しない場合、警告を表示して既定ローカルへフォールバックする。

## Deployment / Rollout
- 既存利用者は追加設定なしで継続利用可能。
