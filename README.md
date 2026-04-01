# LLM Benchmark App

タスク固有ルーブリックに基づき、被験LLMを複数judge（OpenAI/Anthropic/Gemini/OpenRouter）で評価する Web アプリです。

## 特徴

- 被験LLMの回答を1回生成し、judge系統ごとに複数回評価
- judge結果は集約せず、系統ごとに並置表示
- JSON結果の保存・読み込み
- 起動時にモデル一覧を取得し、UIから被験/ judgeモデルを選択（取得できない場合は手動入力）
- 11タスクのルーブリック/プロンプトを同梱

## 依存関係

- Python 3.10+
- Node.js / npm
- FastAPI / uvicorn
- React / Vite
- openai / anthropic / google-genai / python-dotenv

## UIフォント

- フロントエンド UI には `UDEV Gothic 35NFLG` をローカル同梱で使用しています。
- フォントファイルは `frontend/public/fonts/` に配置され、Google Fonts などの外部配信には依存しません。
- 同梱フォントのライセンスは [UDEVGothic-LICENSE.txt](/home/penne/dev/active/llm_evaluation/frontend/public/fonts/UDEVGothic-LICENSE.txt) を参照してください。

## セットアップ

1. 依存関係のインストール

```bash
uv sync
```

2. フロントエンド依存関係のインストール

```bash
npm ci --prefix frontend
```

## 開発起動

1. バックエンド起動

```bash
uv run uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

2. フロントエンド起動

```bash
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5173
```

3. ブラウザで開く

```text
http://127.0.0.1:5173/
```

## ローカルアプリ起動

配布向け構成では frontend を build し、FastAPI から静的配信します。

1. frontend を build

```bash
npm run build --prefix frontend
```

2. launcher から起動

```bash
uv run prism-llm-eval
```

起動後、ローカルサーバーが立ち上がり、既定ブラウザでアプリが開きます。

起動確認だけを行う smoke test:

```bash
timeout 8s uv run prism-llm-eval --no-browser --port 8765
```

`frontend/dist` や bundled resource が不足している場合、launcher は起動前にエラーを表示して終了します。

## Windows Portable ZIP の使い方

GitHub Releases で配布する成果物名は `prism-llm-eval-{tag}-windows-x86_64.zip` です。`*.zip.sha256` も同時に配布し、SHA256 を確認できるようにします。

1. ZIP と `*.sha256` を取得
2. 任意のフォルダへ展開
3. `prism-llm-eval.exe` を実行
4. ブラウザで開いた UI から API キーを保存

詳細な利用ガイドとトラブルシュートは `_docs/guide/DevOps/windows-portable-zip.md` を参照してください。

## Windows 向けバンドル生成

PowerShell から以下を実行すると、frontend build と PyInstaller bundling をまとめて行います。

```powershell
./scripts/build_windows_bundle.ps1
```

`-Version` を指定すると ZIP 名へ反映されます。

```powershell
./scripts/build_windows_bundle.ps1 -Version v0.1.0
```

生成物:

- 展開前の onedir bundle: `dist/prism-llm-eval/`
- portable ZIP: `dist/prism-llm-eval-<version>-windows-x86_64.zip`
- SHA256: `dist/prism-llm-eval-<version>-windows-x86_64.zip.sha256`

### APIキー設定

- `.env` は任意です。UI から保存した API キーだけでも動作します。
- UI から保存した API キーはユーザーごとの app data 配下に永続化されます。
- OpenRouter の残高確認用 `OPENROUTER_MANAGEMENT_KEY` は、推論用 `OPENROUTER_API_KEY` と分離して設定できます。
- `.env` を使う場合は `.env.example` をコピーして設定してください。
- 旧来の `.streamlit/secrets.toml` がある場合は読み込みを継続しますが、新規保存先は app data 側です。

```bash
cp .env.example .env
```

### 保存先

- API キー: app data / config 配下の `secrets.toml`
- OpenRouter Management Key: app data / config 配下の `secrets.toml` 内 `OPENROUTER_MANAGEMENT_KEY`
- モデルキャッシュ: app data 配下の `models/models.json`
- 前回のモデル/タスク選択: app data 配下の `models/last_selection.json`
- 実行結果: app data 配下の `results/`
- grounding corpus: app data 配下の `grounding_corpus/`
- アプリログ: app data 配下の `logs/app.log`
- user override: app data 配下の `overrides/`

Windows では通常 `%LOCALAPPDATA%\Prism\prism-llm-eval\` 以下に保存されます。

### Resource override

prompt / rubric / judge system prompt は次の優先順位で解決されます。

1. 環境変数 override
2. user override
3. bundled resource

user override の配置先:

- `overrides/prompts/<task_id>.md`
- `overrides/rubrics/<task_id>.md`
- `overrides/judge_system_prompt.md`

必要なファイルだけ置けばよく、未配置の task は bundled resource にフォールバックします。

環境変数 override:

- `LLM_BENCHMARK_RUBRICS_DIR`: ルーブリック用ディレクトリ
- `LLM_BENCHMARK_PROMPTS_DIR`: プロンプト用ディレクトリ
- `LLM_BENCHMARK_JUDGE_SYSTEM_PROMPT_PATH`: judgeシステムプロンプトのファイルパス
- `LLM_BENCHMARK_MODEL_CATALOG_TTL_SECONDS`: モデル一覧キャッシュTTL秒（既定: 21600）

## ディレクトリ構成

```
.
├── server.py
├── adapters/
├── core/
├── frontend/
├── rubrics/                # 11タスクのルーブリック
├── prompts/                # 11タスクの入力プロンプト
├── judge_system_prompt.md
├── launcher.py
├── models/
├── packaging/
├── scripts/
├── results/                # 旧保存先（後方互換読み込み用）
└── tests/
```

## 結果ファイル

実行結果は app data 配下の `results/YYYYMMDD_HHMMSS_<model_name>.json` として保存されます。
結果JSONには `execution_duration_ms` が含まれ、評価パイプライン全体の実行時間をミリ秒で記録します。
各 task には `subject_usage`、各 judge run には `usage` が保存されます。さらに結果全体には `usage_summary`、`estimated_cost_usd`、`cost_estimate_status` が追加され、usage が取れた呼び出しと価格が分かるモデルについて推定コストを保存します。
推定コストは現状 OpenRouter モデルで優先的に対応しており、価格不明なモデルは `cost_estimate_status: partial` または `unavailable` になります。
結果JSONには `strict_mode` も保存されます。正式な Strict Mode は Settings で `Strict` を選んだうえで official preset を満たした run だけが `requested: true` / `enforced: true` になり、Dashboard の Strict Mode leaderboard 集計対象になります。
official preset は `task_ids=01..11`、`judge_models=[openrouter/anthropic/claude-sonnet-4.6, openrouter/openai/gpt-5.4, openrouter/google/gemini-3.1-pro-preview]`、`judge_runs=3`、`subject_temperature=0.6`、bundled prompt / rubric / judge_system_prompt 固定です。
実行時のアプリログは app data 配下の `logs/app.log` にローテーション付きで保存されます。
保存済み結果は UI から削除でき、削除時は対応する JSON と `index.json` のサマリーが同時に更新されます。

## Grounding Corpus

grounding corpus は検索結果 JSON と採用 document 本文を紐付けて app data 配下の `grounding_corpus/*.json` に保存されます。

- `GET /api/grounding-corpus`: 保存済みレコード一覧
- `GET /api/grounding-corpus/{record_id}`: 個別レコード取得
- `POST /api/grounding-corpus`: 検索結果と documents を保存

1 レコードには `query`, `search_results`, `documents`, `captured_at`, `notes` が含まれます。`documents` は `url`, `title`, `text`, `source_type` などの provenance を保持します。

## Local Search Tool-Use

一部 task では、モデルプロバイダ固有の web 検索機能に依存せずに tool-use を評価するため、bundled のローカル検索 runtime を使います。

- task ごとの設定は `task_configs/<task_id>.json` に置きます。
- 検索用 fixture は `task_fixtures/<task_id>.json` に置き、`query_snapshots` と `documents` を保持します。
- `query_snapshots` は `temp/search_result*.json` のような検索レスポンス単位の保存領域です。各 snapshot は `query`, `source_file`, `results[]` を持ちます。
- `documents` は URL 単位の本文ストアです。各 document は `url`, `title`, `source_type`, `fetch_status`, `text` を持ち、`open-document(url)` がこの本文を返します。
- 現在は `task08` が `web-search` / `open-document` を使う対象です。
- `/api/tasks` の各 task には `has_subject_tools` が含まれ、subject 側の tool runtime が有効かどうかを確認できます。
- 実行結果 JSON の各 task には `tool_trace` が保存され、被験モデルがどのツールを呼んだかを後から確認できます。

## 注意事項

- APIキーが設定されていないプロバイダはモデル一覧取得時にスキップされます。
- モデル一覧は起動時にTTL内ならキャッシュを使用し、TTL超過時に再取得します。
- 設定画面の「モデル一覧を再取得」はTTLを無視して強制更新します。
- モデル一覧の再取得時は、APIキーが設定された provider を並列に問い合わせます。
- モデル一覧が空の場合は手動入力欄が表示されます。
- 設定画面のタスク一覧は prompt 全文ではなくプレビューを表示します。
- 設定画面の `OpenRouter Admin` セクションから `OPENROUTER_MANAGEMENT_KEY` を保存すると、`GET /api/openrouter/credits` で残高を確認できます。
- 実行画面の右上には、OpenRouter Management Key が設定されている場合のみ、残り credits の簡易表示が出ます。
- 履歴データは Results / Dashboard 画面表示時に遅延ロードされます。
- 配布向け起動では `frontend/dist` が必要です。開発環境では `npm run build --prefix frontend` を実行してください。
- portable ZIP では `frontend/dist` や bundled resource が欠けていると launcher が起動前チェックで停止します。
- APIキーをUIから保存すると app data 配下に保存されます。共有環境ではユーザーごとの OS アカウントを利用してください。
- 前回のモデル/タスク選択は app data 配下に保存され、再起動後に復元されます。
- `http://127.0.0.1:<port>/api/resources` で judge system prompt の解決元と候補 layer を確認できます。
- judgeのJSONが不正な場合はリトライ後にスキップされます。

## License

MIT License
