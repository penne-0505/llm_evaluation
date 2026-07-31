---
title: "QA Verification: Provider-aware reasoning effort ceiling"
status: active
draft_status: n/a
qa_status: verified
risk: High
qa_schema: 2
created_at: 2026-08-01
updated_at: 2026-08-01
references:
  - "_docs/intent/Core/reasoning-effort-ceiling/decision.md"
  - "_docs/plan/Core/reasoning-effort-ceiling/plan.md"
  - "_docs/qa/Core/reasoning-effort-ceiling/test-plan.md"
related_issues: []
related_prs: []
---

# QA Verification: Provider-aware reasoning effort ceiling

## Summary

被験通常・native tool・judge の effort 解決を `LLMAdapter.reasoning_effort_params` に統一した。
OpenRouter は nested `xhigh`、OpenAI / Google は top-level `reasoning_effort`、Anthropic は
`output_config.effort`、LM Studio は catalog が graded `high` を許す場合だけ top-level
`reasoning_effort` を送る。local regression と repository baseline は全て通過した。

implementation commit `82ee42e4a12128fde10a9d246018fbdeaa29d6df` は main と annotated
`v0.17.0` tag へ push 済みである。Code CI / Docs CI / Linux / Windows release workflow は全て
success、GitHub Release は公開済みで4 assetが uploaded になった。

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
date '+%Y-%m-%d %H:%M:%S %Z'
uv run python  # OpenAI / Anthropic SDK version and create signatures
curl -fsS --max-time 3 http://127.0.0.1:1234/api/v1/models
uv run pytest tests/test_adapters.py tests/test_model_parameter_support.py \
  tests/test_anthropic_adapter.py tests/test_benchmark_engine.py \
  tests/test_openrouter_preferred_host.py -q
uv run pytest -q
npm run lint --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
./scripts/check-docs.sh
npx markdownlint-cli2 '_docs/**/*.md' '_evals/**/*.md' README.md AGENTS.md \
  TODO.md QUICKSTART.md '!_docs/archives/**/*' '!_docs/standards/templates/**/*' \
  --config .markdownlint.jsonc
git diff --check
rg -n -S '\{"reasoning": \{"effort": "high"\}\}|extra_params = \
  \{"reasoning"|"effort": "max"' adapters core tests
git push origin main
git tag -a v0.17.0 82ee42e4a12128fde10a9d246018fbdeaa29d6df -m "v0.17.0"
git push origin refs/tags/v0.17.0
git ls-remote --heads --tags origin
gh run view 30662780030 --json name,status,conclusion,headSha,jobs,url
gh run view 30662780368 --json name,status,conclusion,headSha,jobs,url
gh run view 30662789470 --json name,status,conclusion,headSha,jobs,url
gh run view 30662790075 --json name,status,conclusion,headSha,jobs,url
gh release view v0.17.0 --json tagName,isDraft,isPrerelease,publishedAt,url,assets
```

Result:

```text
date=2026-08-01 JST
anthropic=0.79.0 (messages.create supports output_config)
openai=2.21.0 (chat.completions.create supports reasoning_effort)
lmstudio-live=deferred (127.0.0.1:1234 connection refused)
targeted=90 passed, 15 subtests passed
backend=226 passed, 39 subtests passed
frontend-lint=PASS
frontend-test=68 passed
frontend-build=PASS
docs-validator=PASS
markdownlint=154 files, 0 issues
diff-check=PASS
legacy-high/max-send-scan=0 matches
implementation-push=82ee42e4a12128fde10a9d246018fbdeaa29d6df
remote-tag=v0.17.0 -> 82ee42e4a12128fde10a9d246018fbdeaa29d6df
code-ci=success (backend 3.12, backend 3.14, frontend)
docs-ci=success
windows-release=success
linux-release=success
release=v0.17.0 published, draft=false, prerelease=false, assets=4 uploaded
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| targeted provider / engine regression | PASS | 90 tests + 15 subtests |
| `uv run pytest -q` | PASS | 226 tests + 39 subtests |
| frontend lint / test / build | PASS | lint 0、68 tests、Vite build 0 |
| docs validators / Markdown lint | PASS | validator exit 0、154 files 0 issues |
| static payload scan / diff check | PASS | legacy nested high / emitted max 0、whitespace error 0 |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| OpenAI field / enum | PASS | official model guidance + SDK 2.21.0 signature |
| Anthropic field / enum | PASS | official effort table + SDK 0.79.0 signature |
| Google AI Studio field / enum | PASS | official OpenAI compatibility map: high が上限 |
| LM Studio field / capability | PASS | 0.4.8 changelog + `/api/v1/models` schema。live server は停止中 |
| Live LM Studio request | deferred | Core-Bug-48 に follow-up。unit で top-level / omit を固定 |
| Remote main / tag / release | PASS | main / tag SHA 一致、4 workflow success、4 asset uploaded |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | engine subject normal / native / judge tests |
| AC-002 | PASS | resolver + four adapter test groups、official docs / SDK signatures |
| AC-003 | PASS | unsupported/custom omit tests、static scan、`max` return なし |
| AC-004 | PASS | targeted と baseline suite が全て緑 |
| AC-005 | PASS | main / annotated tag は `82ee42e`。Code/Docs/Linux/Windows 全 workflow success、4 asset uploaded |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | resolver は xhigh を ceiling とし、xhigh 非対応 family だけ high へ下げる。max を返さない |
| DEC-002 | PASS | protocol shape は各 adapter の method / merge helper に閉じ、engine は内容を解釈しない |
| DEC-003 | PASS | official static family と OR / LM catalog を使用し、unknown は omit |
| DEC-004 | PASS | engine 3 call site が同じ adapter contract を呼ぶ |
| DEC-005 | PASS | custom OpenAI-compatible provider test は None を返す |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | engine regression + hard-coded payload scan 0 |
| INV-002 | PASS | provider kwargs tests + `max` scan / resolver tests |

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| LM Studio live | ローカルサーバ停止中。AC-002 は公式仕様 + unit で充足 | Core-Bug-48 |
| Paid provider live comparison | regression に課金 credential を要求しない | 必要時に別 Manual QA |

## Residual Risks

None

## Follow-up TODOs

- Core-Bug-48: LM Studio 0.4.8+ 実サーバで graded high の受理を確認する。
