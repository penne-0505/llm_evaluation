---
title: GitHub Release Binary Distribution
status: superseded
draft_status: n/a
created_at: 2026-02-18
updated_at: 2026-07-22
references:
  - "_docs/intent/DevOps/legacy-documentation-retirement/decision.md"
  - "_docs/archives/plan/DevOps/linux-appimage-release/plan.md"
  - "_docs/intent/DevOps/windows-portable-zip-distribution/decision.md"
related_issues: []
related_prs: []
---

## Overview
- GitHub Releases向けに単一バイナリを配布するための計画を定義する。
- この計画は配布方式の初期案であり、Windows portable ZIPとLinux AppImageの個別契約に置き換えられた。

## Scope
- GitHub Actionsでビルドとリリース用アーティファクト生成を行う。
- リリースに添付する成果物の命名規則を定義する。
- 初期リリースは Linux x86_64 の単一バイナリと AppImage を対象とする。
- Windows x86_64 向け EXE インストーラーを対象とする。

## Non-Goals
- パッケージング手法の詳細検証（別途調査が必要な場合はsurveyで行う）。
- OSごとの配布チャネル最適化。

## Requirements
- **Functional**:
  - タグ作成時にリリース用バイナリを生成する。
  - Releaseに単一バイナリを添付できる。
  - 成果物名は以下とする:
    - `prism-llm-eval-{tag}-linux-x86_64`
    - `prism-llm-eval-{tag}-linux-x86_64.AppImage`
    - `prism-llm-eval-{tag}-windows-x86_64-setup.exe`
- **Non-Functional**:
  - CIで再現可能なビルド手順を整備する。
  - GitHub Actionsのみで完結する。

## Tasks
- GitHub Actionsワークフローを追加し、ビルドと成果物アップロードを定義する。
- 成果物の命名・保存ルールを決める。
- PyInstallerのspecとエントリポイントを追加する。
- AppImage生成のためのAppDir構成とメタ情報を追加する。
- Windows EXEインストーラー用のスクリプトを追加する。

## Test Plan
- ダミータグでworkflowが成功し、Releaseにバイナリが添付されることを確認する。
- SHA256ファイルがReleaseに添付されることを確認する。
- AppImageとWindowsインストーラーがReleaseに添付されることを確認する。

## Deployment / Rollout
- mainへのマージ後、タグ運用を開始する。
