---
title: Windows Portable ZIP Distribution Decisions
status: active
draft_status: n/a
created_at: 2026-04-01
updated_at: 2026-04-01
references:
  - ../../guide/DevOps/windows-portable-zip.md
  - ../../reference/DevOps/windows-portable-runtime.md
  - ../../plan/DevOps/windows-local-browser-distribution.md
  - ../../plan/Core/resource-embedding-packaging.md
related_issues: []
related_prs: []
---

## Context
- Windows 配布の最終形として、Python / Node.js / uv の個別導入を不要にしつつ、既存の `FastAPI + React/Vite` 実装を大きく崩さない配布方式が必要だった。
- 既存実装では frontend 静的配信、launcher 起動、app data 保存までは成立していたが、portable 配布に必要な user override、診断、成果物命名、利用ガイドが未確定だった。
- 配布対象はまず Windows を優先し、Linux/macOS や installer 形式は初期スコープから外す方針だった。

## Decision
- Windows 向け正式配布形態は installer ではなく portable ZIP とする。
- 成果物名は `prism-llm-eval-{version}-windows-x86_64.zip` に統一し、同名 ZIP に対応する `.sha256` を同時生成する。
- prompt / rubric / judge system prompt の解決順は `env override > user override > bundled` とする。
- user override は app data 配下の `overrides/` を採用し、未配置ファイルは bundled resource へフォールバックさせる。
- portable 起動時は launcher が事前診断を行い、frontend build 不足、task 0 件、judge system prompt 不足を起動前に検知して停止する。
- runtime の解決状態は `/api/resources` で参照できるようにし、`/api/tasks` でも prompt / rubric の解決元を返す。
- 実行データと API キーは ZIP 展開先ではなく app data 配下へ保存する。

## Alternatives
- Windows installer を正式配布形態にする案:
  - インストール体験は改善できるが、初期配布の実装コストとサポート負荷が増えるため不採用。
- bundled resource のみを使い user override を持たない案:
  - 配布物の自己完結性は高いが、運用時の prompt / rubric 差し替えが困難なため不採用。
- override を環境変数のみに限定する案:
  - 開発者向けには十分だが、配布利用者にとって設定コストが高いため不採用。
- ZIP 展開先へ設定と結果を保存する案:
  - 配布物の更新や再展開時にデータを壊しやすく、ユーザーごとの永続化にも不向きなため不採用。

## Rationale
- portable ZIP は GitHub Releases と相性が良く、Windows 実行ファイルを単純な配布手順で提供できる。
- app data 保存により、ZIP の再展開や別ディレクトリへの移動を行っても設定と結果を維持できる。
- `env > user override > bundled` の順序にすると、開発・運用・配布利用者の三者を同じ実装で扱える。
- 起動前診断と `/api/resources` を用意することで、配布後のサポート時に不足ファイルや override 設定の切り分けが容易になる。
- `.sha256` を成果物に含めることで、GitHub Releases 経由の配布物整合性を最低限確認できる。

## Consequences / Impact
- 影響範囲:
  - runtime resource 解決: `core/app_paths.py`, `server.py`
  - launcher UX: `launcher.py`
  - packaging / release: `.github/workflows/windows-bundle.yml`, `scripts/build_windows_bundle.ps1`
  - user guide: `README.md`, `_docs/guide/DevOps/windows-portable-zip.md`
- portable 配布の運用では `_docs/reference/DevOps/windows-portable-runtime.md` の runtime 仕様を単一参照点として扱う。
- `plan` ドキュメントは実装判断の根拠としての役割を終えたため archive へ移す。

## Rollback / Follow-ups
- portable ZIP 配布を取りやめる場合でも、app data 保存と resource override 自体は開発起動で維持できる。
- 将来のフォローアップ:
  - Windows Credential Manager 対応の再評価
  - installer 形式の追加是非の再検討
  - Windows 以外の配布形態拡張
