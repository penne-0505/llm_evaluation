---
title: "QA Test Plan: OpenRouter preferred host selection"
status: active
draft_status: n/a
qa_schema: 2
qa_status: in-progress
risk: Medium
created_at: 2026-07-24
updated_at: 2026-07-24
references:
  - "_docs/archives/plan/Core/openrouter-preferred-host/plan.md"
  - "_docs/intent/Core/openrouter-preferred-host/decision.md"
  - "_docs/qa/Core/openrouter-preferred-host/verification.md"
related_issues: []
related_prs: []
---

# QA Test Plan: OpenRouter preferred host selection

## Source of Intent

- `_docs/intent/Core/openrouter-preferred-host/decision.md`

## Decision Review Scope

- `DEC-001`: 優先ホスト最大 3 回 → unrestricted フォールバック
- `DEC-002`: モデル単位マップ + プリセット
- `DEC-003`: 常時表示 disabled/enabled + 共有ピッカー
- `DEC-004`: endpoints 指標表示

## Quality Goal

OpenRouter モデルでホストを優先指定でき、障害時は unrestricted に落ち、設定とプリセットで再現できる。
ホスト UI は予測可能（disabled/enabled）で、選択判断に足る指標が見える。

## Acceptance Criteria

- AC-001: OpenRouter モデルで endpoints ≥ 2 のときホストピッカーが enabled、1 以下は disabled（非表示にしない）。
- AC-002: ホスト選択がモデル単位で Settings と execution preset に保存・復元される。
- AC-003: Run 時、優先ホストへピン留め呼び出しが最大 3 回先行し、失敗後にホスト指定なしで再試行する。
- AC-004: ホストリストに tps(p50)、input/M、output/M、cache read/M（欠落は —）が表示される。
- AC-005: subject / judge / holistic の OpenRouter 呼び出しに preferredHosts が適用される。

## Intent-derived Invariants

- INV-001 (from DEC-001): 優先ホスト指定時、unrestricted の前にピン留め試行が先行する。
- INV-002 (from DEC-002): preferredHosts 欠落は空マップとして扱い、legacy preset を壊さない。

## Risk Assessment

- Medium: ピン留め後フォールバック順が逆だと意図と異なるホストへ寄る。
- Medium: judge 既存リトライと二重化し過大に叩く。
- Low: endpoints API 失敗でピッカーが壊れる。
- Low: legacy preset 互換破れ。

## Test Strategy

- preferred-host ヘルパの試行順を unit で固定する。
- endpoints proxy の正規化（$/M、欠落）を unit / API test する。
- preset capture/resolve に preferredHosts を node test する。
- UI の enabled/disabled は Manual QA + 必要なら helper test。
- OpenRouter 以外のモデルでは preferred host を無視する。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | enabled/disabled | manual + review | Settings UI | ≥2 enabled、<2 disabled | covered |
| AC-002 | TODO | preset/settings map | node | executionPresets / settingsStore | round-trip | verified |
| AC-003 | TODO | 3 pin then open | unit | preferred host helper test | call order | verified |
| AC-004 | TODO | metrics display | unit + manual | endpoints normalize + UI | fields / — | verified |
| AC-005 | TODO | subject/judge/holistic | unit + review | engine wiring | lookup by model id | covered |
| INV-001 | Intent | pin before open | unit | helper test | order fixed | verified |
| INV-002 | Intent | legacy empty map | node | executionPresets test | missing field ok | verified |

## Manual QA Checklist

- [ ] OpenRouter でホスト複数のモデルを選び、ホストピッカーが enabled になる。
- [ ] ホスト1件相当（または取得1件）で disabled のまま枠が見える。
- [ ] judge チップ切替で共有ピッカーの編集対象が変わる。
- [ ] プリセット保存→読込でホスト優先が戻る。
- [ ] 優先ホストを選び run が完走する（可能なら）。

## Regression Checklist

- [ ] ホスト未指定の既存 OpenRouter run が従来どおり動く。
- [ ] LM Studio / 非 OpenRouter モデル選択が壊れない。
- [ ] reasoning extra_body と provider 指定が共存する。

## Out of Scope

- 実 API 全ホストの品質比較
- 結果画面へのホスト表示

## Open Questions

None
