---
title: "QA Test Plan: Linux AppImage Release"
status: active
draft_status: n/a
qa_status: in-progress
risk: High
qa_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/DevOps/linux-appimage-release/decision.md"
  - "_docs/archives/plan/DevOps/linux-appimage-release/plan.md"
related_issues: []
related_prs: []
---

# QA Test Plan: `Linux AppImage Release`

## Source of Intent

- TODO: `DevOps-Feat-32`
- Plan: `_docs/archives/plan/DevOps/linux-appimage-release/plan.md`
- Intent: `_docs/intent/DevOps/linux-appimage-release/decision.md`

## Quality Goal

Linux x86_64利用者が開発用Python / Node.jsを導入せず、resourceを欠かない単一AppImageを取得・検証・起動でき、追加pipelineが既存Windows releaseを妨げない状態にする。

## Acceptance Criteria

- AC-001: Linux PyInstaller onedirと必要resourceを含む命名済みAppImageを生成する。
- AC-002: FUSE非依存のextract-and-runでpreflightとHTTP応答を確認する。
- AC-003: workflow artifactおよびtag release assetとしてAppImageとSHA256を公開する。
- AC-004: build tool pinningと利用ドキュメントを整備する。

## Decision Review Scope

- DEC-001: onedirをAppImageへ格納することで単一ファイル配布と診断可能性を両立しているか。
- DEC-002: LinuxとWindowsのbuild failure境界が分離されているか。
- DEC-003: appimagetoolと埋め込みruntimeのversionとdigestを検証してからbuild入力に使用しているか。

## Intent-derived Invariants

- INV-001: Linux build failureはWindows portable ZIP buildを実行不能にしない。
- INV-002: AppImage生成toolと埋め込みruntimeはdigest照合前にbuild入力として使用しない。

## Risk Assessment

- Risk level: High
- Risk rationale: tag releaseへassetを公開するCI/CD変更であり、外部binaryをbuild時に実行する。
- Regression risk: resource同梱漏れ、AppRun引数欠落、Release asset競合、Windows releaseへの干渉。
- Data safety risk: なし。runtime dataはapp dataへ保存され、buildは既存ユーザーデータを扱わない。
- Security / privacy risk: external build toolの改変とGitHub tokenのwrite権限。digest固定とjob限定permissionsで軽減する。
- UX risk: 実行権限不足、FUSE非対応、未検証distributionでのglibc不整合。
- Agent misbehavior risk: workflow変更時にWindows jobへLinux dependencyを混在させる、またはtool pinningをmoving latestへ戻す可能性。

## Test Strategy

- Unit: なし。artifact境界をintegrationで検証する。
- Integration: build scriptを実行し、AppImage、SHA256、AppDir metadata、bundled resourcesを検査する。
- E2E: AppImageを`--appimage-extract-and-run --no-browser`で起動し、HTTP endpointへ接続する。
- Manual QA: filename、executable bit、checksum、desktop entry、AppRun引数透過を確認する。
- Validator / static check: `bash -n`、GitHub Actions構造review、backend / frontend / docs標準gateを実行する。
- Diff review: Windows workflowは共通concurrency guard以外のbuild / upload手順が不変であること、Windows specが不変であること、tool digest checkが実行より前にあることを確認する。

## Test Matrix

| ID | Source | Requirement / Optional Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | 完全なLinux AppImageを生成する | integration | `./scripts/build_linux_appimage.sh v-test` | AppImageとSHA256が生成され、resourceが含まれる | verified |
| AC-002 | TODO | FUSEなしでlauncherとHTTP endpointが動作する | E2E | `<AppImage> --appimage-extract-and-run --no-browser --port 8765` | preflight成功後にHTTP 200を返す | verified |
| AC-003 | TODO | artifactとtag release uploadを定義する | static / live CI | `.github/workflows/linux-appimage.yml` / GitHub Actions | upload構造はcovered、live asset確認はpush前のため保留 | covered |
| AC-004 | TODO | tool pinningと利用契約を記載する | static / docs | build script、README、guide、docs validators | version/digest固定と利用方法が検証される | verified |
| INV-001 | DEC-002 | Linux失敗境界をWindowsから分離する | diff review | `.github/workflows/*.yml` | 独立workflowで、共有はRelease concurrency guardのみ | verified |
| INV-002 | DEC-003 | digest検証前にtoolとruntimeを使用しない | static / negative check | `scripts/build_linux_appimage.sh` | 不一致digestでbuildが停止する | verified |

AC-003のlive CI確認は変更がremoteへpushされていないためdeferredとする。workflow構造とupload条件はstatic check済み。

## Manual QA Checklist

- [ ] AppImageのファイル名と実行権限が正しい。
- [ ] `.sha256`を`sha256sum --check`で検証できる。
- [ ] AppRunがlauncher引数を透過する。
- [ ] `/api/resources`でbundled resourceが解決される。
- [ ] Release assetsがWindows成果物と同じtagへ集約される。

## Regression Checklist

- [ ] backend testが成功する。
- [ ] frontend lint / buildが成功する。
- [ ] Windows workflowのbuild / upload手順とPyInstaller specに意図しない差分がない。
- [ ] docs validatorが成功する。

## High-risk Checklist

- [x] Rollback or recovery path is documented.
- [x] Data safety has been checked.
- [x] Security / privacy implications have been checked.
- [x] Failure mode is understood.

## Out of Scope

- Linux ARM、macOS、installer、repository package、自動更新、raw onefile binary。

## Open Questions

- distribution互換性のsupport範囲はCI基盤でのsmoke後にguideへ確定する。
