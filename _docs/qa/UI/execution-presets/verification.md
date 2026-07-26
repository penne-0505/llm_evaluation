---
title: "QA Verification: Execution Presets"
status: active
draft_status: n/a
qa_status: verified
risk: Medium
qa_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-26
references:
  - "_docs/archives/plan/UI/execution-presets/plan.md"
  - "_docs/intent/UI/execution-presets/decision.md"
  - "_docs/reference/UI/execution-presets.md"
  - "_docs/qa/UI/execution-presets/test-plan.md"
related_issues: []
related_prs: []
---

# QA Verification: Execution Presets

## Summary

実行プリセットをschema v2へ更新し、被験モデルのidentityと被験モデル専用hostを
保存・適用対象から外した。schema v1はlegacy `subjectModel`だけを無視して互換読込し、
judge条件を維持する。HostPickerはbody直下のportalへ移し、後続sectionのstacking
contextに隠れず選択できることを実画面で確認した。

## Verification Verdict

Verdict: PASS

## Commands Run

```bash
uv run pytest
npm run lint --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend
./scripts/check-docs.sh
npx markdownlint-cli2 "_docs/**/*.md" "_evals/**/*.md" \
  "README.md" "QUICKSTART.md" "TODO.md" "AGENTS.md" "CLAUDE.md"
git diff --check
```

Result:

```text
backend pytest: 220 PASS
frontend lint: PASS
frontend node tests: 68 PASS
frontend production build: PASS
docs validators: PASS (既存Core-Bug-48 warningのみ)
markdownlint: PASS (212 files, 0 issues)
git diff --check: PASS
```

## Automated Test Results

| Command / Test | Result | Notes |
| --- | --- | --- |
| `uv run pytest` | PASS | 220 tests |
| `npm run lint --prefix frontend` | PASS | ESLint error 0 |
| `npm run test --prefix frontend` | PASS | 68 tests。schema v2、v1互換、subject維持、host filteringを含む |
| `npm run build --prefix frontend` | PASS | TypeScriptとVite production bundle |
| `./scripts/check-docs.sh` | PASS | 既存TODO warning 1件、validator failureなし |
| `npx markdownlint-cli2 ...` | PASS | 212 files、0 issues |
| `git diff --check` | PASS | whitespace errorなし |

## Manual QA Results

| Checklist Item | Result | Notes |
| --- | --- | --- |
| Page identity / non-blank | PASS | `http://127.0.0.1:8765/settings`, title `LLM評価スイート` |
| Preset説明 | PASS | 被験モデルを維持する文言をrendered DOMで確認 |
| HostPicker layer | PASS | body直下、`position: fixed`、`z-index: 10000`、候補点でmenuが最前面 |
| HostPicker selection | PASS | OpenAI hostを選択するとmenuが閉じ、表示が切り替わることを確認後、自動へ復元 |

## Acceptance Criteria Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| AC-001 | PASS | captureとoverwrite unit test。schema v2にsubject identityなし |
| AC-002 | PASS | Settings store unit testでcatalog / free-text subjectの不変を確認 |
| AC-003 | PASS | schema v1 fixtureでlegacy subjectを無視しjudge条件を適用 |
| AC-004 | PASS | judge / holistic judge / preferred hostのcapture / resolve unit test |
| AC-005 | PASS | missing judge / task filter unit test |
| AC-006 | PASS | config型とcapture diff reviewでsecret / tool / parallel fieldなし |
| AC-007 | PASS | 既存task catalog順unit testを維持 |
| AC-008 | PASS | Settings rendered DOM、README、reference review |
| AC-009 | PASS | in-app Browserでportal layerと候補選択を確認 |

## Decision Conformance

| ID | Result | Why the implementation remains aligned |
| --- | --- | --- |
| DEC-001 | PASS | backendを変更せず既存localStorage persistを継続 |
| DEC-002 | PASS | subject identityを除き、judgeを中心とする再利用可能な評価条件だけを保存 |
| DEC-003 | PASS | 欠損をfilterしconsole warningのみ記録 |
| DEC-004 | PASS | v1全体を失効させず、legacy subjectだけを無視して読込 |

## Invariant Coverage

| ID | Result | Evidence |
| --- | --- | --- |
| INV-001 | PASS | `ExecutionPresetConfig`にAPI key fieldなし |
| INV-002 | PASS | resolve unit testとUI中断なし |
| INV-003 | PASS | store unit testでpreset load前後のsubject fields不変 |

## Deferred / Not Covered

None

## Residual Risks

None

## Follow-up TODOs

None
