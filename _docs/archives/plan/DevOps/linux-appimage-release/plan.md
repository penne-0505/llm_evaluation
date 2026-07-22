---
title: Linux AppImage Release Plan
status: superseded
draft_status: n/a
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/DevOps/linux-appimage-release/decision.md"
  - "_docs/qa/DevOps/linux-appimage-release/test-plan.md"
  - "_docs/intent/DevOps/windows-portable-zip-distribution/decision.md"
related_issues: []
related_prs: []
---

## Overview

- Linux x86_64向けに、PyInstaller onedirを内包するAppImageをtag releaseで配布する。
- 既存のWindows portable ZIP workflowとRelease資産の命名・checksum運用を揃える。
- 本planは`v0.9.0`で実装・live release検証を完了したためarchiveした。

## Scope

- Linux x86_64用PyInstaller specとAppDir metadataを追加する。
- frontend build、PyInstaller bundle、AppImage生成、SHA256生成を一つのbuild scriptで再現可能にする。
- GitHub Actionsでbuild、起動smoke test、workflow artifact upload、tag release uploadを行う。
- READMEとLinux向け利用guideへ取得・起動・互換性境界を記載する。

## Non-Goals

- PyInstaller onefileによるraw単一binaryの配布。
- Windows portable ZIPのonedir構成変更。
- Linux ARM、macOS、installer、repository package、desktop環境への自動登録。
- AppImage内部からの自動更新。

## Requirements

- **Functional**:
  - 成果物名を `prism-llm-eval-<version>-linux-x86_64.AppImage` とする。
  - 同名の `.sha256` を生成する。
  - AppImage内にfrontend、prompt、rubric、judge prompt、task config / fixtureを含める。
  - launcherの引数をAppImageの引数として透過的に受け渡す。
  - tag pushでは既存のGitHub Releaseへ成果物を添付し、手動実行ではworkflow artifactを提供する。
- **Non-Functional**:
  - AppImage生成ツールと埋め込みruntimeはrelease versionとSHA256を固定する。
  - CI上でFUSEを前提にせず、`--appimage-extract-and-run`を使ってsmoke testできる。
  - Linux bundleのresource解決はWindows portable runtimeと同じアプリ契約を維持する。

## Tasks

- Linux PyInstaller specを追加する。
- AppRun、desktop entry、SVG iconを追加する。
- Linux build scriptへtool verification、AppDir構築、AppImage / SHA256生成を実装する。
- Linux release workflowを追加する。
- Windows / Linux workflowへ同一tagのRelease更新だけを直列化する共通concurrency groupを設定する。
- ローカルbundle build、resource診断、HTTP smoke test、checksum検証を行う。
- README、guide、reference、QA verificationを更新する。

## QA Plan

- QA document: `_docs/qa/DevOps/linux-appimage-release/test-plan.md`
- Risk level: High
- Test strategy:
  - Unit: AppImage固有の純粋ロジックはなく、build artifact検証を優先する。
  - Integration: Linux build scriptでPyInstaller bundleとAppImageを生成する。
  - E2E: AppImageをextract-and-runし、HTTP endpointとresource diagnosticsを確認する。
  - Manual QA: 成果物名、実行権限、desktop metadata、checksumを確認する。
  - Validator / static check: shell syntax、GitHub Actions YAML、docs validator、既存test suiteを実行する。
- AC-001 / AC-004はlocal buildとartifact inspection、AC-002は起動smoke、AC-003はworkflow構造reviewとtag release実行で確認する。
- DEC-001からDEC-003のWhyを満たし、Windows runtime契約を変更していないことをdiff reviewする。
- rollbackはLinux workflowとRelease asset生成の停止であり、Windows workflowを独立して維持する。

## Deployment / Rollout

- mainへ変更を反映後、手動workflowでartifactを検証する。
- 次のversion tagからWindows ZIPとLinux AppImageを同一Releaseへ添付する。
- Linux job失敗時もWindows jobとworkflowを分離し、共通concurrency groupは同一tagのRelease更新順序だけを調停する。
- 問題時はLinux workflowを無効化し、既存Releaseから該当AppImageを取り下げる。設定・実行結果はapp data側にあるため、成果物差し替えでユーザーデータは変更しない。
