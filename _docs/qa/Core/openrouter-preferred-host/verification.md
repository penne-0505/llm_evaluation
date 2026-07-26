---
title: "QA Verification: OpenRouter preferred host selection"
status: active
draft_status: n/a
qa_schema: 2
qa_status: partial
risk: Medium
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/archives/plan/Core/openrouter-preferred-host/plan.md"
  - "_docs/intent/Core/openrouter-preferred-host/decision.md"
  - "_docs/qa/Core/openrouter-preferred-host/test-plan.md"
related_issues: []
related_prs: []
---

# QA Verification: OpenRouter preferred host selection

## Summary

OpenRouter モデルの優先ホスト選択（ピン留め最大 3 回 → unrestricted）、endpoints proxy、
Settings / プリセット / HostPicker UI を実装した。自動テストは PASS。実 OpenRouter を使う
Manual QA は deferred（Core-Test-68）。

## Verification Verdict

Verdict: PARTIAL

## Commands Run

```bash
uv run pytest tests/test_openrouter_preferred_host.py tests/test_adapters.py -q
uv run pytest tests/test_server_frontend.py -k openrouter_endpoints -q
npm run lint --prefix frontend
npm run build --prefix frontend
node --experimental-strip-types --test frontend/src/api/client.node.test.ts frontend/src/lib/executionPresets.node.test.ts
./scripts/check-docs.sh
```

Result:

```text
test_openrouter_preferred_host.py: 6 PASS
test_adapters.py: 31 PASS
openrouter_endpoints API: 2 PASS
frontend lint / build: PASS
client + executionPresets node tests: PASS
docs validators: PASS
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `iter_extra_params_attempts` | PASS | AC-003 / INV-001 |
| `normalize_endpoint` | PASS | AC-004 |
| `executionPresets preferredHosts` | PASS | AC-002 / INV-002 |
| `buildRunRequestBody preferred_hosts` | PASS | AC-002 |
| `/api/openrouter/endpoints` | PASS | AC-001 enable flag |
| frontend lint / build | PASS | |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| endpoints ≥ 2 で enabled / 1 以下で disabled | DEFERRED | Core-Test-68 |
| judge チップ切替で共有ピッカー対象変更 | DEFERRED | Core-Test-68 |
| プリセット保存・読込 | DEFERRED | 自動は PASS、UI 操作は deferred |
| 優先ホスト付き短 run | DEFERRED | 実 API 依存 |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS (code) / DEFERRED (live) | HostPicker enabled = endpoints ≥ 2 |
| AC-002 | PASS | presets + settingsStore + RunRequest |
| AC-003 | PASS | helper unit + engine invoke loop |
| AC-004 | PASS | normalize + HostPicker metrics |
| AC-005 | PASS (review) | subject / judge / holistic wiring |

## Decision Conformance

| DEC | Result | Notes |
| --- | --- | --- |
| DEC-001 | PASS | pin ×3 then unrestricted |
| DEC-002 | PASS | preferredHosts map |
| DEC-003 | PASS | disabled/enabled + shared picker |
| DEC-004 | PASS | tps / $/M metrics |

## Invariant Coverage

| INV | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | pin attempts precede unrestricted |
| INV-002 | PASS | legacy missing → `{}` |

## Deferred / Not Covered

- Live OpenRouter endpoints 形と UI Manual QA（Core-Test-68）
- ホスト別実測コストの結果画面表示

## Residual Risks

- Manual QA 未実施のため、実 UI 操作感と upstream endpoints 応答差は未確認。
- endpoints API 失敗時は選択不可（エラー表示）。

## Follow-up TODOs

- Core-Test-68: OpenRouter preferred host Manual QA
