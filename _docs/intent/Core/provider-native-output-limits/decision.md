---
title: "Intent: Provider-native output token limits"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-08-05
updated_at: 2026-08-05
references:
  - "_docs/archives/plan/Core/provider-native-output-limits/plan.md"
  - "_docs/qa/Core/provider-native-output-limits/test-plan.md"
  - "_docs/intent/Core/model-parameter-support/decision.md"
  - "_docs/intent/Core/holistic-context-overflow/decision.md"
related_issues: []
related_prs: []
---

# Intent: Provider-native output token limits

## Context

reasoning model は internal reasoning と visible response が同じ output budget を共有する。固定 `16,384`
は以前の `4,096` より打ち切りを減らしたが、現在は model/provider が許す最大出力より低いアプリ独自
cap になっている。被験とjudgeで同じ評価条件を守りつつ、protocol差を adapter に閉じ込める必要がある。

## Decisions

### DEC-001: 評価 engine は output cap を決めず `None` を渡す

- **What**: 被験 text/native/final と judge standard/holistic の全 call site は `max_tokens=None` を使う。
- **Why**: roleやtool modeごとに固定値が残ると、同じmodelでも評価経路により打ち切り条件が変わる。
- **Change freedom**: 引数名や sentinel type は変えられるが、engine が数値 cap を所有しない責務は維持する。

### DEC-002: optional protocol は max output field を省略する

- **What**: OpenRouter / OpenAI-compatible / LM Studio は `None` のとき `max_tokens` と
  `max_completion_tokens` のどちらも送らない。explicit integer caller は従来どおり送る。
- **Why**: `None` を別の大きい固定値へ置換すると cap の名前を変えただけになり、model native default/limit
  に追従できない。
- **Change freedom**: SDK の omit sentinel を使う実装へ変更できる。
- **Why not**: 極端に大きい integer を送らない。provider max 超過の400と将来model driftを招く。

### DEC-003: Anthropic required max は Models API から解決する

- **What**: Anthropic は catalog entry の `max_tokens` を優先し、無ければ `models.retrieve(model_id)` の
  `max_tokens` を取得する。同一 adapter/model 内でcacheする。値が正の整数でなければ request を送らず
  `LLMError` にする。
- **Why**: Messages API は `max_tokens` 必須である一方、Models API が provider native maximum を返す。
  静的表や旧固定値より、credential が実際にアクセスできる model metadata が正確である。
- **Change freedom**: cache scope（instance / process / catalog file）と事前fetch timing は変更できる。
- **Why not**: metadata failure時の `16,384` fallback — 利用者から見えないapp capを復活させる。

### DEC-004: holistic output reserve はinput overflow予防でありrequest capではない

- **What**: holistic bundled input budget の output reserve は専用名へ分離し、adapterへmax値として渡さない。
- **Why**: reserve はcontext rejectionを減らす入力側heuristicで、生成を打ち切るrequest parameterとは目的が違う。
- **Change freedom**: reserve値やmodel-aware化は holistic overflow intent の範囲で変更できる。

## Consequences / Impact

- optional protocol は provider default / native maximum まで生成できるため、latency と cost が増える場合がある。
- Anthropic は model limit metadata lookup が初回 call に加わる。catalog/cache hit 後は追加 network call を避ける。
- metadataを提供しないcustom Anthropic-compatible endpointは、明示integer caller以外の評価でエラーになる。

## Quality Implications

- engine の全call siteで `None` を記録するtestが必要。
- adapterごとにNone omitとexplicit integer維持の両方をtestする。
- Anthropicはcatalog hit、live lookup/cache、invalid/missing metadataの3分岐をtestする。
- `16,384` はholistic reserve以外の評価request契約に残さない。

## Intent-derived Invariants

- INV-001 (from DEC-001): 被験またはjudgeの評価 call site は数値の output token cap を adapter へ渡さない。
- INV-002 (from DEC-003): Anthropic model maximum を解決できない評価 request は、固定 token 値へfallbackして送信しない。

## Rollback / Follow-ups

- rollback: engine/adaptersをinteger required contractへ戻す。結果artifact schemaのrollbackは不要。
- follow-up: holistic reserve をcontext/output metadataでmodel-aware化する場合は既存 overflow intentを更新する。
