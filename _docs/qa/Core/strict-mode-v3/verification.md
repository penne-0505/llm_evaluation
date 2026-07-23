---
title: "QA Verification: Official Strict Mode v3 + provider-flexible judges"
status: active
draft_status: n/a
qa_schema: 2
qa_status: verified
risk: Medium
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/Core/strict-mode-v3/decision.md"
  - "_docs/archives/plan/Core/strict-mode-v3/plan.md"
  - "_docs/qa/Core/strict-mode-v3/test-plan.md"
related_issues: []
related_prs: []
---

# QA Verification: Official Strict Mode v3 + provider-flexible judges

## Summary

official preset を `official-v3`（Kimi K3 / GPT-5.6 Terra / Qwen3.7 Max）へ更新し、
Strict judge 適合を leaf（末尾セグメント）一致に変更。Settings は leaf フィルタ付き
picker で provider ルートを選択可能にした。

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
uv run pytest tests/test_strict_mode.py tests/test_server_frontend.py::TestStrictModeApi -q
npx --prefix frontend tsx --test frontend/src/lib/strictMode.node.test.ts
npm run lint --prefix frontend
npm run build --prefix frontend
```

Result: PASS

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `tests/test_strict_mode.py` | PASS | v3 preset、leaf match / mismatch、profile 共有 |
| `TestStrictModeApi` | PASS | `/api/strict-mode/preset` → official-v3 |
| `strictMode.node.test.ts` | PASS | issues / filter / resolve |
| frontend lint / build | PASS | |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| Strict ON で leaf フィルタ picker | deferred | unit + Settings diff で AC-004 充足 |
| 非 OpenRouter 同一 leaf で条件 OK | deferred | backend/FE unit で代替 |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | preset endpoint + `test_official_preset_is_v3` |
| AC-002 / INV-001 | PASS | leaf match/mismatch unit |
| AC-003 | PASS | `strictMode.node.test.ts` |
| AC-004 | PASS | filter helper + SettingsPage picker wiring |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | official-v3 + 3 preferred OpenRouter IDs |
| DEC-002 | PASS | `judge_model_leaf_id` / validate leaf multiset |
| DEC-003 | PASS | filtered picker + leaf replace toggle |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | validate + FE issues |

## Deferred / Not Covered

| ID | Reason | Follow-up |
| --- | --- | --- |
| Live Strict run | catalog / keys 依存 | ユーザー環境で再実行 |
| Provider 差の可視化 | Intent Consequences | Dashboard 内訳は別タスク |
| catalog に leaf 無し | issues 表示で検知 | キー設定・再取得 |

## Residual Risks

None

## Follow-up TODOs

None
