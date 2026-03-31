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
- `.env` を使う場合は `.env.example` をコピーして設定してください。
- 旧来の `.streamlit/secrets.toml` がある場合は読み込みを継続しますが、新規保存先は app data 側です。

```bash
cp .env.example .env
```

### 保存先

- API キー: app data / config 配下の `secrets.toml`
- モデルキャッシュ: app data 配下の `models/models.json`
- 前回のモデル/タスク選択: app data 配下の `models/last_selection.json`
- 実行結果: app data 配下の `results/`
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

## 注意事項

- APIキーが設定されていないプロバイダはモデル一覧取得時にスキップされます。
- モデル一覧は起動時にTTL内ならキャッシュを使用し、TTL超過時に再取得します。
- 設定画面の「モデル一覧を再取得」はTTLを無視して強制更新します。
- モデル一覧が空の場合は手動入力欄が表示されます。
- 配布向け起動では `frontend/dist` が必要です。開発環境では `npm run build --prefix frontend` を実行してください。
- portable ZIP では `frontend/dist` や bundled resource が欠けていると launcher が起動前チェックで停止します。
- APIキーをUIから保存すると app data 配下に保存されます。共有環境ではユーザーごとの OS アカウントを利用してください。
- 前回のモデル/タスク選択は app data 配下に保存され、再起動後に復元されます。
- `http://127.0.0.1:<port>/api/resources` で judge system prompt の解決元と候補 layer を確認できます。
- judgeのJSONが不正な場合はリトライ後にスキップされます。

## License

MIT License
