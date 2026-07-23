---
title: "QA Test Plan: Official Strict Mode v3 + provider-flexible judges"
status: active
draft_status: n/a
qa_schema: 2
qa_status: in-progress
risk: Medium
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/intent/Core/strict-mode-v3/decision.md"
  - "_docs/archives/plan/Core/strict-mode-v3/plan.md"
  - "_docs/qa/Core/strict-mode-v3/verification.md"
related_issues: []
related_prs: []
---

# QA Test Plan: Official Strict Mode v3 + provider-flexible judges

## Source of Intent

- `_docs/intent/Core/strict-mode-v3/decision.md`

## Decision Review Scope

- DEC-001 … DEC-003
- INV-001 (from DEC-002)

## Quality Goal

v3 judge セットで Strict が成立し、同一 leaf なら provider ルートを変えても eligible になる。
UI は leaf 外モデルを選べない。

## Acceptance Criteria

- AC-001: official preset id は `official-v3`、judge preferred ID は Kimi K3 / Terra / Qwen3.7 Max。
- AC-002: leaf 一致の別 provider ID は validate で violations なし。leaf 不一致は violations。
- AC-003: frontend issues も leaf 一致で判定する。
- AC-004: Strict 時 judge picker は leaf 一致モデルにフィルタされ、同一 leaf は置換選択できる。

## Intent-derived Invariants

- INV-001 (from DEC-002): eligible 時 leaf 多重集合一致。

## Risk Assessment

- Medium: Strict eligibility 契約変更。旧 v2 完全一致クライアントは新 preset で再取得が必要。

## Test Strategy

- Unit: `core/strict_mode` leaf validate、preset endpoint、frontend `strictMode` helper。
- Diff review: Settings Strict judge UI。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | Intent | v3 preset | unit | `tests/test_server_frontend.py` / `test_strict_mode.py` | official-v3 + 3 judges | verified |
| AC-002 / INV-001 | Intent | leaf match | unit | `tests/test_strict_mode.py` | alt provider OK / mismatch NG | verified |
| AC-003 | Intent | FE issues | unit | `frontend/src/lib/strictMode.node.test.ts` | leaf match | verified |
| AC-004 | Intent | picker filter | unit + diff | settingsStore / SettingsPage | filter + replace | verified |

## Manual QA Checklist

- [ ] Strict ON で judge picker に v3 leaf 候補だけが出る
- [ ] OpenRouter 以外の同一 leaf を選んでも Strict 条件 OK になる（catalog にある場合）

## Regression Checklist

- [ ] task set / judge_runs / subject_temp 固定は維持
- [ ] Standard モードの judge 選択は制限されない

## Out of Scope

- live Strict run、v2 結果の再ラベル

## Open Questions

None
