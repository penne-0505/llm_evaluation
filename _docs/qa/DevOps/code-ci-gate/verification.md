---
title: "QA Verification: Code CI gate"
status: active
draft_status: n/a
qa_status: partial
risk: High
qa_schema: 2
created_at: 2026-07-26
updated_at: 2026-07-26
references:
  - "_docs/intent/DevOps/code-ci-gate/decision.md"
  - "_docs/plan/DevOps/code-ci-gate/plan.md"
  - "_docs/qa/DevOps/code-ci-gate/test-plan.md"
related_issues: []
related_prs: []
---

# QA Verification: `Code CI gate`

## Summary

コード側の自動 gate 新設（`Code CI`）、テスト間のプロセス共有状態リセット、frontend node test の
単一 script 化、および `quality_assurance.md` の baseline suite 規範を検証した。

gate 対象コマンドはすべてローカルで実行し exit code を確認した。workflow 定義は diff review と
manual QA で確認したが、GitHub 上での実行は未実施である。この 1 点により verdict を `PARTIAL` とする。

## Verification Verdict

Verdict: PARTIAL

## Commands Run

```bash
uv run pytest -q
uv run --python 3.12 pytest -q
npm run lint --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
npm ci --prefix frontend
./scripts/check-docs.sh
npx markdownlint-cli2 --config .markdownlint.jsonc "_docs/**/*.md" "AGENTS.md" "TODO.md" "README.md" "QUICKSTART.md" "!_docs/archives/**/*" "!_docs/standards/templates/**/*"
```

Result:

```text
pytest-3.14=0 :: 213 passed, 23 subtests passed in 1.49s
pytest-3.12=0 :: 213 passed, 23 subtests passed in 1.32s
lint=0
fe-test=0 :: tests 66 / pass 66 / fail 0
build=0
check-docs=0
markdownlint=0 :: Summary: 0 issues in 0 files
```

変更前の基準値（`tests/conftest.py` 追加前）:

```text
1 failed, 212 passed, 23 subtests passed in 121.91s
FAILED tests/test_benchmark_engine.py::TestBenchmarkEngine::test_no_fixed_sleep_between_successful_runs
AssertionError: 35 != 0
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `uv run pytest -q`（3.14） | PASS | 213 passed / 1.49s。変更前は 1 failed / 121.91s |
| `uv run --python 3.12 pytest -q` | PASS | 213 passed / 1.32s。release build 版で同結果 |
| `tests/test_benchmark_engine.py` 単独 | PASS | 変更前は単独でも 1 failed。順序依存ではなくファイル内蓄積と確定 |
| `npm run lint --prefix frontend` | PASS | 指摘なし |
| `npm run test --prefix frontend` | PASS | 13 ファイル / 66 tests / 0 fail |
| `npm run build --prefix frontend` | PASS | dist 生成を確認 |
| `npm ci --prefix frontend` | PASS | `tsx` 追加後の lock で成功 |
| `./scripts/check-docs.sh` | PASS | 初回実行で intent の dangling link を検出し、修正後 exit 0 |
| `markdownlint-cli2` | PASS | 95 files / 0 issues |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| trigger が `docs-ci.yml` と同条件 | PASS | 双方 `push: [main, dev]` / `pull_request: [main]` |
| matrix が release build と `.python-version` に一致 | PASS | 3.12（release build）/ 3.14（`.python-version`） |
| secret 不参照・権限昇格なし | PASS | `secrets.` 参照 0 件。`permissions: contents: read` を明示 |
| `AGENTS.md` のコマンド一覧が gate と一致 | PASS | `npm run test` を追記し、gate 参照を明記 |
| conftest のリセット対象が実証済みの範囲 | PASS | `ProviderRateLimiter` / `ActiveRunRegistry` / `RateLimitStore.FILE_PATH` の 3 つのみ |
| 既存テストの pass 数が減っていない | PASS | 212 → 213（失敗していた 1 件が pass へ転じた） |
| matrix が実際に別バージョンで走る | PASS | 下記「matrix 実効性の確認」を参照。初版の欠陥を修正済み |

### matrix 実効性の確認

初版の workflow は `setup-python` でバージョンを与えるのみだった。`uv` は `.python-version`
（3.14）を優先するため、matrix の両 leg が 3.14 で走り、3.12 を検証しないまま緑になる欠陥があった。
gate 自身はどちらでも緑になるため、この欠陥は gate では検出できない。

```text
uv run python --version              -> Python 3.14.6   （.python-version 由来）
UV_PYTHON=3.12 uv run python --version -> Python 3.12.13 （上書き可能）
```

job レベルで `UV_PYTHON: ${{ matrix.python-version }}` を設定して修正し、CI と同じ形で再確認した。

```text
UV_PYTHON=3.12 -> Python 3.12.13 :: exit=0 :: 213 passed, 23 subtests passed in 1.50s
UV_PYTHON=3.14 -> Python 3.14.6  :: exit=0 :: 213 passed, 23 subtests passed in 1.62s
```

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | full suite 213 passed。単独実行との結果差なし |
| AC-002 | PASS | 3.12 / 3.14 の双方で 213 passed |
| AC-003 | PASS | `npm run test` で 13 ファイル / 66 tests 実行 |
| AC-004 | PARTIAL | 定義は diff review と manual QA で確認。GitHub 上での実行は未実施 |
| AC-005 | PASS | `quality_assurance.md` の baseline suite 節 |
| AC-006 | PASS | `check-docs.sh` exit 0 / markdownlint 0 issues |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | gate 対象が release build と同じコマンド一式であり、push / PR で発火する定義になっている |
| DEC-002 | PASS | `core` のシングルトン設計は未変更。リセットは `tests/` 配下に閉じ、本番挙動へ影響しない |
| DEC-003 | PASS | `tsx` を devDependency に固定し、単一 script へ集約。拡張子なし import 規約は変更していない |
| DEC-004 | PASS | matrix が出荷版と開発版の双方を含む |
| DEC-005 | PASS | 規範が「未確認」と「失敗」を区別し、既知の失敗に TODO 起票を要求している |

DEC-005 は本 verification 自身にも適用した。gate が一度も発火していない状態を `PASS` と呼ばず
`PARTIAL` としたのは、この decision の `Why` に沿った判断である。

## Invariant Coverage

- INV-001 (from DEC-005): PASS — full suite が緑であることを確認したうえで、未確認項目が残るため
  verdict を `PASS` にせず `PARTIAL` とした。規範と実際の判定が一致している。

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| AC-004 | workflow は push 前であり、GitHub 上で実行されたことがない | DevOps-Test-69 |
| Node 版差 | ローカル 24 と CI / release 22 の差を gate していない | DevOps-Chore-70 |
| dev 依存脆弱性 | `npm audit` の 10 件は既存 dev 依存由来で本変更の対象外 | DevOps-Chore-70 |

## Residual Risks

- `Code CI` は未実行である。YAML 構文、action バージョン、CI 環境での `uv sync` など、
  ローカル実行では検証できない失敗要因が残る。初回 push 後の run 確認が必要。
- Node のローカル版（24.14.1）と CI / release 版（22）の差は gate されない。
  24 固有の破綻は検出できない。
- `npm audit` が dev 依存に 10 件（high 8）を報告する。`@babel/core` / `brace-expansion` /
  `esbuild` / `flatted` / `js-yaml` などで、いずれも vite・eslint 配下の既存依存であり、
  `tsx` が持ち込んだものではなく、ビルド成果物にも載らない。
- `tests/conftest.py` のリセット対象は実証済みの 3 つに限った。他の classmethod シングルトン
  （`AppPaths` / `ModelCatalog` / `SecretsStore` / `ProviderRegistry`）で新たな順序依存が
  現れた場合、最初の捜索先はここになる。

## Follow-up TODOs

- DevOps-Test-69: [Test] 初回 Code CI run を GitHub 上で確認する（AC-004）
- DevOps-Chore-70: [Chore] frontend toolchain の版差と dev 依存脆弱性を棚卸しする
