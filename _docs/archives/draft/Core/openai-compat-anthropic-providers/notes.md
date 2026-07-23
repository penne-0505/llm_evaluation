---
title: "Draft: User-registered OpenAI-compatible providers + Anthropic"
status: completed
draft_status: n/a
created_at: 2026-07-23
updated_at: 2026-07-24
references:
  - "_docs/archives/survey/Core/openai-compat-anthropic-providers/survey.md"
  - "_docs/archives/plan/Core/openai-compat-anthropic-providers/plan.md"
  - "_docs/intent/Core/openai-compat-anthropic-providers/decision.md"
  - "_docs/qa/Core/openai-compat-anthropic-providers/test-plan.md"
related_issues: []
related_prs: []
---

# Draft: User-registered OpenAI-compatible providers + Anthropic

## Status

Open Questions は 2026-07-23 の会話で閉鎖。正式ドキュメントへ昇格済み。

- Survey / Plan / Intent / QA: 上記 references
- TODO: `Core-Feat-58`

実装完了・intent 紐付け後、archive checklist を満たせば
`_docs/archives/draft/Core/openai-compat-anthropic-providers/` へ移送可。

## Closed Open Questions

| Q | 決定 |
| --- | --- |
| Q1 LM Studio | 別枠維持（DEC-002） |
| Q2 provider id | slug 自動生成 + display_name（DEC-004） |
| Q3 Anthropic | subject+judge + tool-use + thinking（DEC-006） |
| Q4 OpenRouter | `kind=openai_compatible` + `profile=openrouter`（DEC-005） |
| Q5 cost | 明示 `pricing_profile`、OpenAI/Anthropic/Google 静的表（DEC-007 / INV-001） |
| Q6 secrets | 動的 id + OPENROUTER 写像（DEC-008） |

## Historical notes

以下は探索時の原文動機・要件候補。正典は Intent / Plan。

### Motivation

- OpenRouter 経由の strict 評価は被験込みで平均およそ 5〜6 USD。
- 公式 credit / 無料枠を subject / judge に直結したい。
- Google は OpenAI 互換で足りる。Anthropic は専用 adapter。
- OpenRouter も registry の一インスタンスに寄せる。
