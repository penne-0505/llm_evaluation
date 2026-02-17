---
title: GitHub Release Binary Distribution
status: active
draft_status: n/a
created_at: 2026-02-18
updated_at: 2026-02-18
references: []
related_issues: []
related_prs: []
---

## Overview
- GitHub Releases向けに単一バイナリを配布するための計画を定義する。

## Scope
- GitHub Actionsでビルドとリリース用アーティファクト生成を行う。
- リリースに添付する成果物の命名規則を定義する。
- 初期リリースは Linux x86_64 の単一バイナリを対象とする。

## Non-Goals
- パッケージング手法の詳細検証（別途調査が必要な場合はsurveyで行う）。
- OSごとの配布チャネル最適化。

## Requirements
- **Functional**:
  - タグ作成時にリリース用バイナリを生成する。
  - Releaseに単一バイナリを添付できる。
  - 成果物名は `llm-benchmark-{tag}-linux-x86_64` とする。
- **Non-Functional**:
  - CIで再現可能なビルド手順を整備する。
  - GitHub Actionsのみで完結する。

## Tasks
- GitHub Actionsワークフローを追加し、ビルドと成果物アップロードを定義する。
- 成果物の命名・保存ルールを決める。
- PyInstallerのspecとエントリポイントを追加する。

## Test Plan
- ダミータグでworkflowが成功し、Releaseにバイナリが添付されることを確認する。
- SHA256ファイルがReleaseに添付されることを確認する。

## Deployment / Rollout
- mainへのマージ後、タグ運用を開始する。
