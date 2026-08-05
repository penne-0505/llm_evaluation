---
title: "Intent: Ollama Cloud and OpenCode Go official providers"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-08-05
updated_at: 2026-08-05
references:
  - "_docs/intent/Core/openai-compat-anthropic-providers/decision.md"
  - "_docs/archives/plan/Core/official-cloud-providers/plan.md"
  - "_docs/qa/Core/official-cloud-providers/test-plan.md"
related_issues: []
related_prs: []
---

# Intent: Ollama Cloud and OpenCode Go official providers

## Context

両サービスは既存の custom OpenAI-compatible provider として登録できるが、利用者が base URL と
secret 名を正しく転記する必要がある。「公式対応先」は、動作する URL を README に書くだけでなく、
組み込み registry、environment alias、model catalog、adapter routing が一つの契約として一致する状態とする。

## Decisions

### DEC-001: 公式 URL と公式 API key 名を一組で組み込む

- **What**: Ollama Cloud は `ollama-cloud` / `https://ollama.com/v1` / `OLLAMA_API_KEY`、
  OpenCode Go は `opencode-go` / `https://opencode.ai/zen/go/v1` / `OPENCODE_API_KEY` を使う。
- **Why**: URL だけ preset にして secret を generic alias のままにすると、公式 client と同じ `.env` を
  再利用できず、UI 保存先と環境変数読込が食い違う。
- **Change freedom**: 公式 service が仕様を変更した場合は、同じ検証手順で URL と key alias を更新できる。

### DEC-002: 両 provider は既存 OpenAI-compatible adapter を使う

- **What**: provider kind は `openai_compatible` とし、モデル一覧は `/models`、生成は
  `/chat/completions` を使う。新しい adapter kind は追加しない。
- **Why**: Ollama は OpenAI compatibility を公式提供する。OpenCode Go gateway は Chat Completions
  request をモデルごとの Anthropic Messages / OpenAI Responses / upstream Chat Completions へ変換するため、
  client 側で同じ credential を複数 provider id に分割する必要がない。
- **Change freedom**: gateway の変換保証が廃止された場合は、`profile=opencode-go` の model-level routing
  へ変更できる。
- **Why not**: OpenCode Go を protocol ごとに3 providerへ分割 — model picker、secret、usage.provider が
  同一サービス内で分裂する。
- **Revisit when**: 公式 Chat Completions endpoint が一部モデルを受理しないことを live contract で確認したとき。

### DEC-003: 価格は推測せず `pricing_profile=none` とする

- **What**: 両 provider の builtin pricing profile は `none` とする。
- **Why**: subscription limit、モデルごとの価格、提供モデルは変動し、既存の OpenAI / Anthropic / Google
  静的表や OpenRouter catalog を流用すると実際の請求経路と異なる。
- **Change freedom**: provider 固有の検証済み価格 source を追加できた場合は専用 profile を導入できる。

### DEC-004: 同名の旧 custom entry は official contract へ昇格する

- **What**: 既存 registry に `ollama-cloud` / `opencode-go` があれば custom entry を複製せず、builtin、
  kind、base URL、pricing profile を公式値へ正規化する。display name と他の custom entries は保持する。
- **Why**: 以前に手動登録した利用者を二重表示にせず、誤 URL も修復しつつ、registry 全体の再生成による
  custom provider 消失を避ける。
- **Change freedom**: migration の実装位置は `ensure_builtins` 以外へ移せる。

## Consequences / Impact

- Settings の組み込み provider は4件から6件になる。
- 公式 environment alias を使うため、UI で保存した key の secrets.toml 名も公式 client と揃う。
- catalog は両 provider の全モデルを prefix 付きで表示するが、料金推定は unavailable / partial になり得る。

## Quality Implications

- exact URL / alias / model prefix を unit test に固定し、upstream 仕様変更を意図しない drift と区別する。
- 実 credential は test fixture に入れず、公開 endpoint と mock request で通常回帰を閉じる。
- 既存 provider registry と secret 非露出の invariant は関連 intent の INV-001 / INV-002 を継承する。

## Intent-derived Invariants

None

## Rollback / Follow-ups

- rollback: 2 provider の builtin seed、official alias、UI help を戻す。registry ファイル全体は削除しない。
- follow-up: live credential を明示提供された場合だけ、代表モデルで completion と tool calling を確認する。
