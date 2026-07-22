---
title: LM Studio Local Provider Support
status: superseded
draft_status: n/a
created_at: 2026-04-17
updated_at: 2026-07-22
references:
  - "_docs/intent/Core/legacy-documentation-retirement/decision.md"
  - "_docs/archives/plan/Core/legacy-documentation-retirement/model-selection-from-api.md"
  - "_docs/archives/plan/Core/legacy-documentation-retirement/local-search-tool-use-runtime.md"
related_issues: []
related_prs: []
---

## Overview
- LM Studio を、このアプリの local LLM provider として追加する。
- 初期対応の対象は LM Studio の OpenAI-compatible API に限定し、`/v1/models` と `POST /v1/chat/completions` を使って既存の OpenAI SDK ベース実装へ最小差分で統合する。
- 現状の課題は API 呼び出しそのものより、モデル識別子・設定保存・UI 契約・adapter 解決が cloud provider 前提で固定されていることにある。今回の計画ではここを first-class provider として解消する。
- 2026-04-17 時点で確認した LM Studio 公式仕様では、既定ポートは `1234`、OpenAI-compatible endpoint は `/v1/models`, `/v1/responses`, `/v1/chat/completions`, `/v1/embeddings`, `/v1/completions` であり、既定では認証不要だが LM Studio 0.4.0 以降は API Token 必須設定も可能である。

## Scope
- backend に `lmstudio` provider を追加し、subject / judge の両方で実行できるようにする。
- LM Studio 接続設定として `base_url` と optional な API Token の保存・取得手段を追加する。
- `ModelCatalog` で LM Studio の `/v1/models` を取得し、既存 UI のモデル選択に統合する。
- LM Studio の任意モデル名を既存の実行経路で扱えるよう、アプリ内部の model id を provider-qualified 形式で正規化する。
- Settings / Run UI に LM Studio 設定欄、状態表示、エラー表示を追加する。
- 単体テスト、server API テスト、最小限の手動検証手順を定義する。

## Non-Goals
- LM Studio 以外の local provider 追加。
- LM Studio native REST API (`/api/v1/*`) を使った download / load / unload 管理。
- Strict Mode preset への LM Studio 組み込み。
- LM Studio 向け推定コスト算出。
- `/v1/responses`, embeddings, completions, Anthropic-compatible endpoint の利用。
- provider 推定なしで raw な local model 名を free-text 入力し、自動的に LM Studio 扱いにすること。

## External API Notes
- `https://lmstudio.ai/docs/developer/openai-compat`
  - OpenAI client の `base_url` を `http://localhost:1234/v1` に切り替えることで既存クライアントを再利用できる。
  - LM Studio は OpenAI-compatible な `/v1/models` と `/v1/chat/completions` を提供する。
- `https://lmstudio.ai/docs/developer/openai-compat/models`
  - `GET /v1/models` は server から見えるモデル一覧を返す。
  - Just-In-Time loading が有効な場合、レスポンスには「現在ロード済み」だけでなく「ダウンロード済み」のモデルが含まれることがある。
- `https://lmstudio.ai/docs/developer/openai-compat/chat-completions`
  - `POST /v1/chat/completions` は `model`, `messages`, `temperature`, `max_tokens`, `stream`, `stop` など OpenAI 互換の基本 payload を受け取る。
- `https://lmstudio.ai/docs/developer/core/authentication`
  - 既定では認証不要。
  - 認証を有効にした場合は `Authorization: Bearer <token>` が必要。
- `https://lmstudio.ai/docs/developer/core/tools`
  - `/v1/chat/completions` と `/v1/responses` で tool use を扱える。
  - モデルごとの品質差はあるが、LM Studio 側は native / default の両レベルで tool use を扱う設計になっている。
- `https://lmstudio.ai/docs/developer/rest/quickstart`
  - native REST API 側では `/api/v1/chat` の auto-load や model management が可能だが、初期実装では依存しない。

## Design Decisions
- `lmstudio` を `openai` の単なる `base_url` 差し替えではなく、独立 provider として扱う。
  - 理由: OpenAI と LM Studio では認証前提、モデル命名、UI 表示、将来の機能差分が異なる。
  - 理由: run payload と結果保存が文字列 id ベースのため、provider を分離した方が resolver を壊さず拡張できる。
- LM Studio のモデル id はアプリ内部で `lmstudio/<raw_model_id>` に正規化する。
  - 例: `openai/gpt-oss-20b` を UI 表示上はそのまま見せつつ、内部 id は `lmstudio/openai/gpt-oss-20b` にする。
  - 理由: 現在の `get_adapter_for_model()` は model 名の prefix だけで adapter を決めており、raw な local model 名では provider 判定できない。
- 初期実装は OpenAI-compatible `/v1/*` に寄せ、LM Studio native REST API は将来拡張へ回す。
  - 理由: 既存実装が `openai.OpenAI(...).chat.completions.create(...)` を前提にしており、再利用コストが最も低い。
  - 理由: native model management を同時に入れると、設定保存・事前ロード・状態同期の設計が一段重くなる。

## Technical Design
### Model Identity
- `ModelCatalog` の LM Studio entry は `provider="lmstudio"`、`id="lmstudio/<raw_id>"`、表示名は `<raw_id>` を使う。
- `SelectionStore`、Run request、Result JSON、Dashboard 集計は prefixed id をそのまま保持する。
- `LMStudioAdapter` 内では API 呼び出し直前に `lmstudio/` prefix を剥がして raw model id へ戻す。
- free-text 手入力で LM Studio モデルを指定する場合は `lmstudio/<raw_id>` 形式のみを受け付ける。

### Configuration Persistence
- secret ではない接続設定の保存先として、新規に `core/provider_config_store.py` を追加する。
- 保存対象は少なくとも `lmstudio.base_url` とし、保存先は `AppPaths.config_dir()` 配下の JSON を想定する。
- API Token は secret 扱いとし、`SecretsStore` に `LMSTUDIO_API_TOKEN` を追加する。
- LM Studio 設定 API は既存の `/api/keys` に無理に畳み込まず、`/api/lmstudio/config` 系の dedicated endpoint を追加する。
  - 理由: 既存の `/api/keys` は cloud provider の API key 有無だけを扱う契約で、`base_url` を表現できない。
  - 理由: LM Studio だけ optional token + required URL という非対称性がある。

### Adapter Layer
- 新規に `adapters/lmstudio_adapter.py` を追加する。
- 内部実装は `openai.OpenAI(base_url=<normalized_url>, api_key=<token_or_placeholder>)` を使う。
- OpenAI SDK の都合で non-empty `api_key` が必要な場合は、token 未設定時に placeholder として `"lm-studio"` を使う。
- `supports_native_tools()` は `True` を返し、`complete_with_model_native_tools()` は既存 OpenAI-compatible tool calling 実装を再利用する。
- `tool_mode="auto"` では既存の `NativeToolsNotSupportedError` fallback をそのまま生かし、LM Studio 側の tool support 差は runtime の自動退避で吸収する。

### Catalog / Resolver / Execution Path
- `core/model_catalog.py`
  - `PROVIDERS` に `lmstudio` を追加する。
  - 設定済み base URL がある場合のみ `/v1/models` を取得する。
  - token 未設定は `missing_keys` に入れず、認証が必要な server で失敗した場合のみ `errors.lmstudio` へ格納する。
- `adapters/__init__.py`
  - `get_adapter_for_model()` と `_resolve_api_key()` に `lmstudio/` 分岐を追加する。
- `server.py`
  - `_resolve_subject_key()` を `lmstudio` 対応に拡張するか、provider-aware resolver へ置き換える。
  - run 開始時のエラーを「adapter 未対応」ではなく「LM Studio 未設定 / 到達不能 / 認証失敗 / モデル未解決」に寄せる。
- `frontend/src/api/client.ts`
  - provider map に `lmstudio` を追加する。
  - LM Studio 設定用 API クライアントを追加する。

### UI / UX
- Settings に LM Studio 専用セクションを追加する。
- 入力項目は `Server URL` と `API Token (optional)` の 2 つを基本とする。
- URL の初期提案値は `http://127.0.0.1:1234/v1` とする。
- モデル一覧再取得時、LM Studio のみ URL 未設定なら問い合わせをスキップし、設定欄に説明を出す。
- モデル picker では provider label を `LM Studio` と表示する。
- manual input の補助文言として、LM Studio の場合は `lmstudio/<model-id>` 形式を明示する。

### Compatibility and Risk Handling
- LM Studio docs 上、`/v1/models` に見えていても必ずしも実行可能とは限らない可能性があるため、初期実装では load 状態の厳密保証をしない。
- 実行失敗時は「LM Studio 側で model が ready か」「JIT loading が有効か」「認証 token が必要か」を案内する。
- 既存 provider の保存形式や run schema は壊さず、LM Studio 追加のみの後方互換にとどめる。

## Requirements
- **Functional**
  - Settings から LM Studio の `base_url` と optional token を保存・読み出しできる。
  - モデル一覧再取得で LM Studio の `/v1/models` を取り込み、subject / judge の両 picker に出せる。
  - LM Studio モデルを standard mode で subject / judge として実行できる。
  - subject tool runtime の `native` / `text` / `auto` が LM Studio でも既存方針のまま動作する。
  - app 再起動後も LM Studio 設定、モデル選択、結果表示が破綻しない。
- **Non-Functional**
  - LM Studio が未設定の環境では既存挙動を変えない。
  - OpenAI / Anthropic / Gemini / OpenRouter の既存動作と API 契約を壊さない。
  - 到達不能・401/403・空モデル一覧・未知 model id の各失敗が区別できるエラーメッセージを出す。
  - LM Studio を使うためにインターネット接続を要求しない。

## Tasks
1. `lmstudio` provider の内部仕様を確定し、`lmstudio/<raw_id>` 正規化ルールを backend / frontend で統一する。
2. `ProviderConfigStore` と `SecretsStore` 拡張を追加し、LM Studio 設定 API (`GET/POST/DELETE /api/lmstudio/config`) を実装する。
3. `LMStudioAdapter` を追加し、adapter resolver と subject key resolver を `lmstudio` 対応に更新する。
4. `ModelCatalog` に LM Studio fetcher を追加し、エラー・キャッシュ・正規化ルールを固める。
5. frontend の `Provider` 型、API client、Settings UI、Model picker 表示を LM Studio 対応に更新する。
6. Run 導線と free-text 入力の補助文言を更新し、LM Studio model id の扱いを明確にする。
7. unit test / server test を追加し、README と利用ガイド更新の差分を準備する。

## Test Plan
- unit test
  - `get_adapter_for_model("lmstudio/<raw_id>")` が `LMStudioAdapter` を返す。
  - LM Studio adapter が token なしでも placeholder key で client 初期化できる。
  - prefix の付与 / 剥離、base URL の正規化が期待通り動く。
- catalog test
  - `/v1/models` の response を `lmstudio/<raw_id>` へ正規化できる。
  - URL 未設定時は fetch をスキップする。
  - 認証失敗と接続失敗が `errors.lmstudio` に載る。
- server API test
  - LM Studio 設定の保存 / 取得 / 削除ができる。
  - `/api/models` が `lmstudio` provider を返せる。
  - `/api/run` が LM Studio subject / judge を解決できる。
- manual smoke
  - LM Studio server を起動し、Settings で URL を保存する。
  - モデル一覧を再取得し、LM Studio モデルが picker に出ることを確認する。
  - LM Studio を subject にして 1 task 実行する。
  - LM Studio を judge にして 1 task 実行する。
  - tool-use task で `auto` と `text` fallback の両方を確認する。

## Deployment / Rollout
- 既定では未設定 provider として扱い、LM Studio 設定を保存したユーザーだけが利用できる opt-in rollout にする。
- 実装後は README に最低限のセットアップ手順を追記する。
  - LM Studio 側で server を起動すること。
  - 既定 URL が `http://127.0.0.1:1234/v1` であること。
  - 認証を有効にした場合のみ token が必要なこと。
- 初回リリースでは model load / download 失敗を app 側で自動復旧しない。必要なら次フェーズで `/api/v1/models/load` 連携を検討する。
- rollback は `lmstudio` provider を UI と resolver から外すだけでよく、既存 provider データへの migration は不要。
