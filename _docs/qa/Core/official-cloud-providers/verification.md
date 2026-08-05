---
title: "QA Verification: Ollama Cloud and OpenCode Go official providers"
status: active
draft_status: n/a
qa_status: partial
risk: High
qa_schema: 2
created_at: 2026-08-05
updated_at: 2026-08-05
references:
  - "_docs/intent/Core/official-cloud-providers/decision.md"
  - "_docs/intent/Core/openai-compat-anthropic-providers/decision.md"
  - "_docs/plan/Core/official-cloud-providers/plan.md"
  - "_docs/qa/Core/official-cloud-providers/test-plan.md"
related_issues: []
related_prs: []
---

# QA Verification: Ollama Cloud and OpenCode Go official providers

## Summary

Ollama Cloud / OpenCode Go を official builtin provider とし、base URL、environment alias、UI 保存、
model catalog、Chat Completions routing を同じ registry contract に統合した。local baseline、公開 endpoint、
無認証 error contract、独立 diff review は完了した。remote main / tag / release workflow は未実行のため、
deployment closure だけを deferred とする。

## Verification Verdict

Verdict: PARTIAL

## Commands Run

```bash
date '+%Y-%m-%d %H:%M:%S %Z'
uv run pytest tests/test_provider_registry.py tests/test_secrets_store.py \
  tests/test_model_catalog.py tests/test_model_parameter_support.py \
  tests/test_cost_estimator.py tests/test_server_frontend.py -q
uv run pytest
npm run lint --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
./scripts/check-docs.sh
npx markdownlint-cli2 '_docs/**/*.md' '_evals/**/*.md' README.md AGENTS.md \
  TODO.md QUICKSTART.md '!_docs/archives/**/*' '!_docs/standards/templates/**/*' \
  --config .markdownlint.jsonc
curl -fsSL https://ollama.com/v1/models
curl -fsSL https://opencode.ai/zen/go/v1/models
curl -X POST https://ollama.com/v1/chat/completions  # credentialなし
curl -X POST https://opencode.ai/zen/go/v1/chat/completions  # credentialなし
curl -fsSL https://models.dev/api.json
cheap-opinion review --model qwen-coder --format json
git diff --check
git ls-remote --tags origin refs/tags/v0.18.0 refs/tags/v0.18.0^{}
```

Result:

```text
date=2026-08-05 JST
targeted=86 passed, 21 subtests passed
backend=233 passed
frontend-lint=PASS
frontend-test=68 passed
frontend-build=PASS
docs-validator=PASS
markdownlint=158 files, 0 issues
ollama-models=HTTP 200, object=list, 18 models
opencode-go-models=HTTP 200, object=list, 25 models
ollama-chat-no-auth=HTTP 401 Unauthorized
opencode-go-chat-no-auth=HTTP 401 Missing API key
models.dev=ollama-cloud https://ollama.com/v1 OLLAMA_API_KEY
models.dev=opencode-go https://opencode.ai/zen/go/v1 OPENCODE_API_KEY
independent-review=patch is correct; 2 documentation findings rejected after direct line review
diff-check=PASS
remote-v0.18.0=absent
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| targeted provider regression | PASS | 86 tests + 21 subtests |
| `uv run pytest` | PASS | 233 tests |
| frontend lint / test / build | PASS | lint 0、68 tests、Vite build 0 |
| docs validators / Markdown lint | PASS | wrapper exit 0、158 files 0 issues |
| registry / secret / pricing / request-shape tests | PASS | AC-001..004、INV-001..002を固定 |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| Ollama official URL / key alias | PASS | official docs + models.dev + live `/models` |
| OpenCode Go URL / key alias | PASS | official docs/source + models.dev + live `/models` |
| Chat Completions endpoint existence | PASS | representative model は認証判定まで到達し HTTP 401 |
| Paid credential completion | not-applicable | secret 探索・課金 request は scope 外 |
| Independent diff review | PASS | correctness 0.98。2 doc 指摘は事実不一致 / 既記載のため棄却 |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | builtin seed / URL / deletion constraint tests |
| AC-002 | PASS | official env alias save/load tests、API response key非露出 test |
| AC-003 | PASS | `/models` prefix tests、OpenCode Go request-shape test、live endpoint |
| AC-004 | PASS | legacy custom promotion + unrelated custom preservation test |
| AC-005 | PASS | README、`.env.example`、Settings help の diff review |
| AC-006 | PASS | backend / frontend / docs baseline 全成功 |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| official DEC-001 | PASS | URL と official env alias を同じ builtin id に結合した |
| official DEC-002 | PASS | adapter kind を増やさず Chat Completions gateway を再利用した |
| official DEC-003 | PASS | 両 provider は `none` で、価格表 fallback を行わない |
| official DEC-004 | PASS | 同名だけを正規化し他 custom entry を保持する test が通った |
| provider DEC-001 / 008 / 010 | PASS | 既存 protocol registry / secret boundary / builtin ordering を拡張した |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | official cloud 2 provider の price は unavailable、source None |
| INV-002 | PASS | secret alias tests、provider API test、diff scanで非露出 |

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| Remote release | implementation commit / tag がまだ未 push | Core-Enhance-76 のまま継続し、CI / asset確認後に PASSへ更新 |

## Residual Risks

- GitHub Code CI / Docs CI / Linux / Windows release workflow と配布 asset は tag push 後まで未確認。

## Follow-up TODOs

- Core-Enhance-76: `v0.18.0` push 後の remote workflow / release asset を確認して本 verification を閉じる。
