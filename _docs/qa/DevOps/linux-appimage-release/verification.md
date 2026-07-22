---
title: "QA Verification: Linux AppImage Release"
status: active
draft_status: n/a
qa_status: partial
risk: High
qa_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/intent/DevOps/linux-appimage-release/decision.md"
  - "_docs/plan/DevOps/linux-appimage-release/plan.md"
  - "_docs/qa/DevOps/linux-appimage-release/test-plan.md"
related_issues: []
related_prs: []
---

# QA Verification: `Linux AppImage Release`

## Summary

Linux x86_64 hostでAppImageを実buildし、checksum、FUSE非依存起動、HTTP resource / task診断、既存test suite、frontend gate、workflow構造を確認した。GitHub ActionsのUbuntu 22.04 runnerとtag Release uploadは未実施である。

## Verification Verdict

Verdict: PARTIAL

## Commands Run

```bash
./scripts/build_linux_appimage.sh local-20260722-r2
cd dist
sha256sum --check prism-llm-eval-local-20260722-r2-linux-x86_64.AppImage.sha256
./prism-llm-eval-local-20260722-r2-linux-x86_64.AppImage --appimage-version
cd ..
./scripts/smoke_test_linux_appimage.sh \
  dist/prism-llm-eval-local-20260722-r2-linux-x86_64.AppImage 8766
# FUSEを使う通常起動でも同じresource / task endpointを確認
uv run --with pytest python -m pytest
npm run lint --prefix frontend
npm run build --prefix frontend
uv run --with pyyaml python - <<'PY'
from pathlib import Path
import yaml

for name in ("linux-appimage.yml", "windows-bundle.yml"):
    data = yaml.load(
        (Path(".github/workflows") / name).read_text(),
        Loader=yaml.BaseLoader,
    )
    assert data["concurrency"]["group"] == "release-assets-${{ github.ref }}"
PY
bash -n scripts/build_linux_appimage.sh scripts/smoke_test_linux_appimage.sh
desktop-file-validate packaging/linux/prism-llm-eval.desktop
git diff --check
npx markdownlint-cli2 README.md TODO.md \
  _docs/plan/DevOps/github-release-binary.md \
  _docs/{plan,intent,qa}/DevOps/linux-appimage-release/*.md \
  _docs/guide/DevOps/linux-appimage.md \
  _docs/reference/DevOps/linux-appimage-runtime.md
# DD_SCOPE_PATHSに今回のchanged docsを指定してfrontmatter / TODO / link / intent / QA validatorを実行
# DD_SCOPE_PATHSを外してvalidator fixture suiteとworkflow hook testを実行
```

Result:

```text
AppImage build: PASS (29.74 MiB compressed filesystem)
SHA256: PASS
AppImage extract-and-run resource / task smoke: PASS
AppImage FUSE mount resource / task smoke: PASS
Backend: 90 passed
Frontend lint/build: PASS
Workflow YAML parse, shell syntax, diff whitespace: PASS
Changed-doc validators / validator fixtures / workflow hooks: PASS
```

`uv run pytest`はproject外のsystem pytestを実行してdependenciesを参照できずcollection errorになったため、pytestを明示的に追加する上記commandで再実行した。

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| Linux AppImage build script | PASS | AppImageとSHA256を生成 |
| AppImage checksum verification | PASS | `sha256sum --check`成功 |
| Extract-and-run HTTP smoke | PASS | judge prompt、prompt / rubric layer、taskを解決 |
| FUSE mount HTTP smoke | PASS | 通常起動でも同じresourceとtaskを解決 |
| Backend pytest | PASS | 90 tests passed |
| Frontend lint / build | PASS | ESLint、TypeScript、Vite build成功 |
| Workflow / shell static checks | PASS | YAML parse、`bash -n`、`git diff --check`成功 |
| Docs validators / fixtures / hooks | PASS | 差分scopeとfixture suiteを環境分離して成功 |
| GitHub Actions Ubuntu 22.04 build | DEFERRED | 未pushのためworkflow未実行 |
| Tag Release asset upload | DEFERRED | 新しいtagでのlive upload未実行 |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| AppImage filename / executable bit | PASS | canonical filenameで生成され実行可能 |
| AppRun argument forwarding | PASS | `--appimage-extract-and-run --no-browser --port 8766`で起動 |
| Bundled resource diagnostics | PASS | preflight通過後にresource layerとtaskを確認 |
| Pinned tool inputs | PASS | tool / runtime digest verification後にbuild |
| Windows release isolation | PASS | build / upload手順とspecは不変。共通concurrency guardのみ追加 |
| Same-tag GitHub Release assets | DEFERRED | live CI未実施 |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | local buildでAppImageとbundled resourceを確認 |
| AC-002 | PASS | extract-and-run HTTP smokeが成功 |
| AC-003 | PARTIAL | workflow定義は確認済み、artifact / Release uploadはlive未確認 |
| AC-004 | PASS | tool / runtime pinning、README、guide、referenceを確認 |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | onedirをAppDirへ収め、PyInstaller onefileを重ねていない |
| DEC-002 | PASS | Linuxを独立workflowにし、Windows側はRelease concurrency guard以外のbuild / upload手順とspecを維持した |
| DEC-003 | PASS | appimagetoolとtype2 runtimeのversion / SHA256を固定し、照合後にbuildしている |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | Linux workflowはWindows workflowへのdependencyを持たない |
| INV-002 | PASS | build logとscript順序で両digestの照合が生成前に完了 |

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| AC-003 live CI | 変更をまだpushしておらずGitHub Actionsを起動できない | push後に手動workflowを実行しartifactを確認する |
| AC-003 tag upload | 次version tagは未作成 | 次回tag releaseでAppImageとSHA256を確認する |

## Residual Risks

- Ubuntu 22.04 runnerでのPyInstaller / AppImage buildは未確認。
- 共通concurrency groupによる同一tag Release更新の直列化はlive確認していない。

## Follow-up TODOs

- `DevOps-Feat-32`をIn Progressに維持し、push後のworkflow artifact確認でPASS可否を判断する。
- 次回version tagで同一ReleaseへのWindows / Linux asset集約を確認する。
