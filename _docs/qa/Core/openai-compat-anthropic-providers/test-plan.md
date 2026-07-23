---
title: "QA Test Plan: User-registered OpenAI-compatible providers + Anthropic"
status: active
draft_status: n/a
qa_schema: 2
qa_status: in-progress
risk: High
created_at: 2026-07-23
updated_at: 2026-07-24
references:
  - "_docs/archives/survey/Core/openai-compat-anthropic-providers/survey.md"
  - "_docs/archives/plan/Core/openai-compat-anthropic-providers/plan.md"
  - "_docs/intent/Core/openai-compat-anthropic-providers/decision.md"
related_issues: []
related_prs: []
---

# QA Test Plan: User-registered OpenAI-compatible providers + Anthropic

## Source of Intent

- `_docs/intent/Core/openai-compat-anthropic-providers/decision.md`

## Decision Review Scope

- DEC-001 … DEC-010（registry、LM Studio 分離、ID、slug、OpenRouter profile、Anthropic 範囲、
  pricing_profile、secrets 写像、欠損耐性、builtin 集合 A）
- INV-001（公式 profile の OR 価格禁止）、INV-002（key 非漏洩）

## Quality Goal

公式 credit 経路を安全に追加しつつ、既存 OpenRouter / LM Studio を壊さず、推定コストの誤表示と
API key 漏洩を防ぐ。

## Acceptance Criteria

- AC-001: 名前付き openai_compatible を追加し、そのモデルを subject または judge に指定して run できる。
- AC-002: OpenRouter が registry プリセットとして key 設定でき、既存 `openrouter/` モデル ID の run が壊えない。
- AC-003: Anthropic プロバイダで非 tool complete、tool-use、thinking（`api_reasoning`）が
  subject または judge で通る（stub 可）。
- AC-004: Google AI Studio を openai_compatible で登録する手順が Settings 文言または guide にある。
- AC-005: プロバイダ削除・key 欠落時、保存済み preset / 過去 run の表示がクラッシュしない。
- AC-006: API key が結果 JSON / SSE / ログ経路のテストで漏洩しない。
- AC-007: `pricing_profile=openai|anthropic|google` の推定は静的表のみ。表外は N/A。
  同 profile で `pricing_source=openrouter_catalog` にならない（INV-001）。

## Intent-derived Invariants

- INV-001 (from DEC-007): 公式 pricing_profile の推定に OpenRouter カタログ価格を使わない。
- INV-002 (from DEC-008): API key を永続結果・SSE ペイロードに含めない。

## Risk Assessment

- **High — secrets / migration**: 動的 key、既存 OPENROUTER 写像失敗で実行不能。
- **High — cost 誤表示**: OR フォールバック残存、静的表の古い価格を available と過信。
- **High — 課金経路増加**: 公式 API への実呼び出し（live は Manual、CI は stub）。
- **Medium — Anthropic パリティ**: tools/thinking 形状差で engine 分岐漏れ。
- **Medium — ID 衝突**: reserved slug、削除後の dangling model ID。
- **Regression**: openrouter strict、lmstudio 別枠、既存 preset。

## Test Strategy

- **Unit**: registry CRUD / slug、adapter ルーティング、OpenRouter 互換、Anthropic Messages stub
  （complete / tool_use / thinking）、cost profile 分岐と INV-001。
- **Unit**: secrets migration（OPENROUTER → preset）、key が to_dict / SSE fixture に出ない。
- **Integration**: server registry API、models list、run の key 解決失敗メッセージ。
- **Frontend**: Settings 追加フロー smoke、欠損プロバイダ表示、connectedCount。
- **Manual**: 実 OpenAI / Anthropic / AI Studio の短 run（任意、verification に記録）。
- **Diff review**: LM Studio 吸収が混入していないこと、OR フォールバック除去。

## Test Matrix

| ID | Source | Requirement / Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO / DEC-001 | openai_compatible run | unit / integration | `tests/test_adapters.py`、server tests | 登録エントリ経由で complete 成功（stub） | planned |
| AC-002 | TODO / DEC-003/005 | openrouter/ 互換 | unit / regression | `tests/test_adapters.py`、strict tests | `openrouter/` と `or/` が解決 | planned |
| AC-003 | TODO / DEC-006 | Anthropic complete | unit | `tests/test_adapters.py` | text + usage | planned |
| AC-003 | TODO / DEC-006 | Anthropic tool-use | unit | `tests/test_adapters.py` | NativeToolCall | planned |
| AC-003 | TODO / DEC-006 | Anthropic thinking | unit | `tests/test_adapters.py` | `api_reasoning` 非空 | planned |
| AC-004 | TODO / DEC-001 | Google 手順 | diff review / docs | guide or Settings copy | base_url 記載あり | planned |
| AC-005 | TODO / DEC-009 | 欠損耐性 | unit / frontend | preset / results load tests | 例外で落ちない | planned |
| AC-006 / INV-002 | Intent | key 非漏洩 | unit | cost/result/SSE fixtures | key 文字列非含有 | planned |
| AC-007 / INV-001 | Intent | 公式 profile 静的表 | unit | `tests/test_cost_estimator.py` | source ≠ openrouter_catalog、不明は None | planned |
| AC-007 | Intent | OR フォールバック禁止 | unit | `tests/test_cost_estimator.py` | openai profile + 未知モデル → None（OR に同名があっても） | planned |
| DEC-002 | Intent | LM Studio 別枠 | diff review | Settings / routing | lmstudio が registry CRUD 対象外 | planned |
| DEC-010 | Intent | builtin 集合 A | unit | `tests/test_provider_registry.py` | openrouter/openai/google-ai-studio/anthropic が seed、削除不可 | planned |
| DEC-008 | Intent | secrets 写像 | unit | secrets / registry tests | OPENROUTER → openrouter preset | planned |
| Regression | Plan | 既存 backend | regression | `uv run pytest`（関連 subset 可） | 既存 openrouter/lmstudio パス pass | planned |

## Manual QA Checklist

- [ ] OpenAI 公式（または互換）エントリを追加し短 run
- [ ] Anthropic エントリで thinking 付きモデル短 run（可能なら）
- [ ] AI Studio 互換 base_url 登録手順どおりに models 一覧または手動 ID
- [ ] OpenRouter 既存 key のみの環境で起動しプリセット写像を確認
- [ ] プロバイダ削除後に旧 preset を開いても UI が落ちない
- [ ] 結果画面の推定コストが公式経路で OR と混同されないこと

## High-risk Checklist

- **rollback**: registry / 新 adapter を無効化し、`openrouter/` + `lmstudio/` 固定ルーティングへ戻せる（プリセット seed のみ残す選択可）。
- **recovery**: `OPENROUTER_API_KEY` 写像失敗時も手動で openrouter プリセットに key を再保存できる。削除した registry エントリの model ID は実行時エラーだが過去 run JSON は読める。
- **data safety**: 既存 run / preset の model ID 文字列を書き換えない。プロバイダ削除は履歴 JSON を改変しない。
- **security**: API key は SecretsStore のみ。結果 JSON / SSE / ログ / catalog に key を出さない（INV-002）。connection test レスポンスにも key をエコーしない。

## Regression Checklist

- [ ] Strict mode（openrouter judges）
- [ ] LM Studio config / catalog
- [ ] OpenRouter management key / credits（壊れていない）
- [ ] 既存 `estimated_cost_usd` / `cost_estimate_status` セマンティクス

## Out of Scope

- 価格表の鮮度を CI で公式ページと自動突合
- LM Studio registry 吸収
- live 課金を伴う全モデル網羅

## Open Questions

None（draft OQ は Intent で閉鎖）。価格表の具体モデル集合は実装時に主要モデルから開始し、
表外は N/A。
