---
title: Linux AppImage Runtime Reference
status: active
draft_status: n/a
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/DevOps/linux-appimage-release/decision.md"
  - "_docs/guide/DevOps/linux-appimage.md"
  - "_docs/reference/DevOps/windows-portable-runtime.md"
related_issues: []
related_prs: []
---

## Overview

- Linux AppImageのruntime layout、build入力、成果物、検証interfaceを定義する。
- アプリ内のresource解決とapp data保存契約はWindows portable runtimeと共有する。

## Runtime Layout

- `AppRun`: AppImage runtimeから渡された`APPDIR`を基準にlauncherを起動し、全引数を透過する。
- `usr/lib/prism-llm-eval/`: PyInstaller onedir bundle。
- `usr/bin/prism-llm-eval`: bundled launcherへのrelative symlink。
- `prism-llm-eval.desktop`: desktop metadata。
- `prism-llm-eval.svg` / `.DirIcon`: application icon。

PyInstaller bundleには次を含める。

- `frontend/dist/`
- `prompts/`
- `rubrics/`
- `task_configs/`
- `task_fixtures/`
- `judge_system_prompt.md`
- 存在する場合は`models/models.json`

## Build Inputs

| Input | Version | SHA256 |
| --- | --- | --- |
| PyInstaller | `6.21.0` | Python package index / uv resolution |
| `AppImage/appimagetool` x86_64 | `1.9.1` | `ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0` |
| `AppImage/type2-runtime` x86_64 | `20251108` | `2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d` |

`scripts/build_linux_appimage.sh`は両方のdigest照合後にのみAppImage生成を行う。

## Build Interface

```bash
./scripts/build_linux_appimage.sh <version>
```

- **Input**: 成果物名へ含めるversion。省略時は`dev-local`。
- **Output**:
  - `dist/prism-llm-eval-<version>-linux-x86_64.AppImage`
  - `dist/prism-llm-eval-<version>-linux-x86_64.AppImage.sha256`
- **Errors**:
  - host architectureがx86_64でない。
  - 同名outputが既に存在する。
  - dependency install、frontend build、PyInstaller buildが失敗する。
  - external build inputのdigestが一致しない。

## Smoke Test Interface

```bash
./scripts/smoke_test_linux_appimage.sh <appimage-path> [port]
```

- FUSEに依存しない`APPIMAGE_EXTRACT_AND_RUN=1`で起動する。
- launcher preflightを通過して`/api/resources`と`/api/tasks`がHTTP successを返し、judge prompt、prompt / rubric layer、taskが解決されることを確認する。
- 既定portは`8765`。

## Release Contract

- `.github/workflows/linux-appimage.yml`は`workflow_dispatch`と`v*` tag pushで起動する。
- 全実行でAppImageとSHA256をworkflow artifactへuploadする。
- tag push時は同じ2ファイルをtagのGitHub Releaseへuploadする。
- Linux workflowはWindows workflowから独立しており、一方のjob failureを他方のjob dependencyにしない。
- 両workflowは`release-assets-${{ github.ref }}` concurrency groupを共有し、同一tagのRelease更新だけを直列化する。

## Compatibility Boundary

- architecture: Linux x86_64。
- CI build / smoke environment: Ubuntu 22.04、Python 3.12、Node.js 22。
- AppImageはhost kernelとglibcの互換性を完全には抽象化しない。
- runtime dataはplatformdirsが解決するXDG data / config directoryへ保存する。
