---
title: Linux AppImage Release Decisions
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/archives/plan/DevOps/linux-appimage-release/plan.md"
  - "_docs/qa/DevOps/linux-appimage-release/test-plan.md"
  - "_docs/guide/DevOps/linux-appimage.md"
  - "_docs/reference/DevOps/linux-appimage-runtime.md"
  - "_docs/reference/DevOps/windows-portable-runtime.md"
related_issues: []
related_prs: []
---

## Context

- WindowsではPyInstaller onedirをZIP配布しているが、Linuxには開発環境を構築せず起動できるrelease artifactがない。
- 配布上の単一ファイルは望ましい一方、PyInstaller onefileまで重ねると二重展開、起動遅延、障害診断の複雑化が増える。
- AppImage生成には外部toolをCIで実行するため、再現性と供給元検証が必要である。

## Decisions

### DEC-001: PyInstaller onedirをAppImageへ格納する

- **What**: Linux runtimeはPyInstaller onedirとして構築し、AppDirへ配置してAppImage化する。
- **Why**: 利用者には単一ファイルを提供しながら、アプリ内部ではresourceとnative libraryの配置を明示的に保ち、起動失敗時の抽出・診断を可能にするため。
- **Change freedom**: 単一ファイル配布、resource完全性、診断可能性を維持する限り、PyInstaller option、AppDir layout、AppImage生成toolは変更できる。
- **Why not**: PyInstaller onefileをさらにAppImageへ格納すると二重の自己展開になり、配布上の利点を増やさず起動経路だけを複雑にするため採用しない。

### DEC-002: Linux成果物をWindows成果物と独立して生成する

- **What**: Linux AppImageはLinux runnerの独立workflowで生成し、tag push時に同じGitHub Releaseへ添付する。同一tagのRelease更新だけは共通concurrency groupで直列化する。
- **Why**: OS固有のbuild失敗を分離し、既存Windows portable ZIPの生成・検証経路へ回帰を持ち込まないため。
- **Change freedom**: OS固有jobの失敗境界と成果物の同一Release集約を維持する限り、workflowの分割・統合方法は変更できる。

### DEC-003: AppImage生成toolとruntimeをversionとdigestで固定する

- **What**: CIが取得する`appimagetool`と埋め込みtype2 runtimeはrelease versionとSHA256を固定し、実行前に照合する。
- **Why**: moving release assetの内容変化やdownload改変を検知し、同じsource tagから生成するrelease pipelineの入力を追跡可能にするため。
- **Change freedom**: provenanceとintegrityを同等以上に検証できれば、tool version、取得先、署名検証方式へ変更できる。

## Consequences / Impact

- Linux x86_64向けのPyInstaller spec、AppDir metadata、build script、GitHub Actions workflowが追加される。
- AppImageはホストkernelとglibc互換性の影響を完全には除去しない。build runnerの基盤versionがsupport boundaryの一部になる。
- Linux runtimeも既存app data、resource override、preflight diagnosticsを使用する。
- Windows portable ZIPのbuild script、spec、workflowは変更対象外とする。

## Quality Implications

- AppImage内部でfrontendと評価resourceが解決され、launcher preflightを通過する必要がある。
- AppImageはFUSEなしでもextract-and-runで検証できる必要がある。
- checksumの生成だけでなく、build toolと埋め込みruntimeのchecksumも実行前に検証する。
- Linux jobの追加によってWindows release jobを壊してはならない。共有してよいのは同一tagのRelease mutationを直列化する調停だけとする。

## Intent-derived Invariants

- INV-001 (from DEC-002): Linux向けbuildの失敗はWindows portable ZIPのbuild jobを実行不能にしない。
- INV-002 (from DEC-003): 外部から取得したAppImage生成toolと埋め込みruntimeはdigest照合に成功するまでbuild入力として使用しない。

## Enforced in (optional)

- DEC-001: `packaging/linux/`, `scripts/build_linux_appimage.sh`
- DEC-002 / INV-001: `.github/workflows/linux-appimage.yml`
- DEC-003 / INV-002: `scripts/build_linux_appimage.sh`

## Rollback / Follow-ups

- Linux workflowはWindows workflowと独立して無効化できる。
- support対象のdistribution拡張は、実際の互換性検証結果に基づく別decisionとして扱う。
