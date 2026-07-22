---
title: Linux AppImage Guide
status: active
draft_status: n/a
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/DevOps/linux-appimage-release/decision.md"
  - "_docs/reference/DevOps/linux-appimage-runtime.md"
related_issues: []
related_prs: []
---

## Overview

- Linux x86_64向けAppImageの取得、検証、起動、トラブルシュートをまとめる。
- AppImageはfrontendとPython runtime、bundled evaluation resourcesを含むため、通常はPython、Node.js、uvを別途導入しない。

## Prerequisites

- Linux x86_64環境。
- GitHub Releasesから取得したAppImageと対応する`.sha256`。
- 利用するLLM providerのAPI key。

## Setup / Usage

1. GitHub Releaseから次の2ファイルを同じdirectoryへ取得する。
   - `prism-llm-eval-<tag>-linux-x86_64.AppImage`
   - `prism-llm-eval-<tag>-linux-x86_64.AppImage.sha256`
2. checksumを確認する。

   ```bash
   sha256sum --check prism-llm-eval-<tag>-linux-x86_64.AppImage.sha256
   ```

3. 実行権限を付けて起動する。

   ```bash
   chmod +x prism-llm-eval-<tag>-linux-x86_64.AppImage
   ./prism-llm-eval-<tag>-linux-x86_64.AppImage
   ```

4. 既定browserで開いたUIからAPI keyを保存する。

Linuxでは通常、実行結果とcacheは`${XDG_DATA_HOME:-~/.local/share}/prism-llm-eval/`、
secretとprovider設定は`${XDG_CONFIG_HOME:-~/.config}/prism-llm-eval/`に保存される。
AppImage本体を置き換えてもapp dataは維持される。

## FUSEを利用できない環境

AppImage runtimeがFUSEを利用できない場合は、組み込みの展開実行を使う。

```bash
./prism-llm-eval-<tag>-linux-x86_64.AppImage --appimage-extract-and-run
```

launcherの引数もその後へ続けて指定できる。

```bash
./prism-llm-eval-<tag>-linux-x86_64.AppImage \
  --appimage-extract-and-run \
  --no-browser \
  --port 8765
```

## Support Boundary

- 配布対象architectureはLinux x86_64のみ。
- CIのbuildとsmoke testはUbuntu 22.04 runnerで行う。
- AppImageはdistribution差を軽減するが、host kernel、glibc、desktop環境との完全な互換性は保証しない。
- Linux ARM、macOS、repository package、desktop menuへの自動登録、自動更新は対象外。

## Troubleshooting

- `Permission denied`: `chmod +x <AppImage>`を実行する。
- FUSE関連のerror: `--appimage-extract-and-run`を指定する。
- browserが開かない: consoleに表示された`http://127.0.0.1:<port>/`を手動で開く。
- 起動前診断が失敗する: console出力とapp data配下の`logs/app.log`を確認する。
- 指定portが使用中: launcherが選んだ代替portをconsole出力で確認する。

## Local Build / Verification

```bash
./scripts/build_linux_appimage.sh dev-local
./scripts/smoke_test_linux_appimage.sh \
  dist/prism-llm-eval-dev-local-linux-x86_64.AppImage
```

build scriptは固定versionとSHA256で`appimagetool`とtype2 runtimeを検証してからAppImageを生成する。

## References

- `_docs/intent/DevOps/linux-appimage-release/decision.md`
- `_docs/reference/DevOps/linux-appimage-runtime.md`
- `README.md`
