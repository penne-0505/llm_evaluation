---
title: "QA Verification: Provider-native output token limits"
status: active
draft_status: n/a
qa_status: partial
risk: High
qa_schema: 2
created_at: 2026-08-05
updated_at: 2026-08-05
references:
  - "_docs/intent/Core/provider-native-output-limits/decision.md"
  - "_docs/plan/Core/provider-native-output-limits/plan.md"
  - "_docs/qa/Core/provider-native-output-limits/test-plan.md"
  - "_docs/intent/Core/model-parameter-support/decision.md"
  - "_docs/intent/Core/holistic-context-overflow/decision.md"
related_issues: []
related_prs: []
---

# QA Verification: Provider-native output token limits

## Summary

被験・judge の全評価経路からアプリ固定の output token cap を除いた。optional protocol は max field を
省略し、Anthropic Messages API は catalog または Models API が返すモデル別 `max_tokens` を使用する。
local baseline、公式仕様 / installed SDK 照合、static scan、独立 diff review は完了した。remote push、tag、
CI / release artifact の確認前であるため、現時点の verdict は `PARTIAL` とする。

## Verification Verdict

Verdict: PARTIAL

## Commands Run

```bash
date '+%Y-%m-%d %H:%M:%S %Z'
uv run pytest tests/test_benchmark_engine.py tests/test_adapters.py \
  tests/test_anthropic_adapter.py tests/test_model_catalog.py \
  tests/test_model_parameter_support.py
uv run pytest
npm run lint --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
./scripts/check-docs.sh
npx markdownlint-cli2 '_docs/**/*.md' '_evals/**/*.md' README.md AGENTS.md \
  TODO.md QUICKSTART.md '!_docs/archives/**/*' '!_docs/standards/templates/**/*' \
  --config .markdownlint.jsonc
rg -n '_SUBJECT_MAX_OUTPUT_TOKENS|_JUDGE_MAX_OUTPUT_TOKENS|_JUDGE_OUTPUT_RESERVE_TOKENS|max_tokens: int ='
cheap-opinion review --repo /home/penne/dev/active/llm_evaluation \
  --model qwen-coder --format json --max-input-chars 220000
git diff --check
```

Result:

```text
date=2026-08-05 17:29:36 JST
targeted=98 passed
backend=238 passed
frontend-lint=PASS
frontend-test=68 passed
frontend-build=PASS
docs-validator=PASS
markdownlint=162 files, 0 issues
static-cap-scan=PASS (evaluation request cap match 0)
explicit-probe-limit=server.py max_tokens=8 retained
independent-review=patch is correct; 2 findings rejected after direct code review
diff-check=PASS
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| targeted output-limit regression | PASS | 98 tests |
| `uv run pytest` | PASS | 238 tests |
| frontend lint / test / build | PASS | lint 0、68 tests、Vite build 0 |
| `./scripts/check-docs.sh` | PASS | exit 0、warningなし |
| Markdown lint | PASS | 162 files、0 issues |
| adapter request-shape tests | PASS | None omit、explicit integer、Anthropic lookup/cache/error |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| Anthropic Messages / Models API schema | PASS | `max_tokens` required とモデル別maximum metadataを公式docsで照合 |
| installed Anthropic SDK | PASS | `models.retrieve(model_id=...)` と required `messages.create(max_tokens=...)` を照合 |
| evaluation cap static scan | PASS | engineの全subject/judge callがNone。16,384はholistic input reserveのみ |
| non-evaluation probe | PASS | provider接続確認の明示`max_tokens=8`を維持 |
| paid live completion | not-applicable | credential探索と課金requestはscope外 |
| independent diff review | PASS | cache collision指摘はadapter instanceがprovider単位のため不成立。0 omission指摘は`is not None`条件と逆で不成立 |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | subject text/native/final call record tests |
| AC-002 | PASS | standard / holistic judge call record tests |
| AC-003 | PASS | OpenRouter / OpenAI-compatible / LM Studio omit・explicit request tests |
| AC-004 | PASS | Anthropic catalog/live/cache/native/error tests、catalog metadata test |
| AC-005 | PASS | `_HOLISTIC_OUTPUT_RESERVE_TOKENS` 分離とcall-site static review |
| AC-006 | PASS | backend / frontend / docs baseline 全成功 |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | engineのsubject text/native/finalとjudge standard/holisticはすべてNoneを渡す |
| DEC-002 | PASS | optional adapterはNoneで両max fieldを省略し、明示integerを維持する |
| DEC-003 | PASS | catalog優先、Models API fallback、instance cacheを実装し、解決不能時はrequest前にLLMErrorとする |
| DEC-004 | PASS | holistic reserveは入力budget計算だけに残り、adapter argumentへ流れない |
| model-parameter DEC-001/004 | PASS | model別parameter shapingをadapter境界に維持した |
| holistic overflow DEC-001 | PASS | reserve heuristicとoverflow metadata formatを変更していない |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | engine call record testsと数値cap static scan |
| INV-002 | PASS | missing/invalid model maximumでMessages requestが0回のtest |

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| Remote CI / release | pushとtag作成前 | 同一タスクのclosureで確認する |
| paid provider completion | credential探索・課金requestは許可範囲外 | None |

## Residual Risks

- remote CI / release artifact が未確認である。実装・local baselineの未達ではなく、publish前の状態差である。

## Follow-up TODOs

None
