# LLM Benchmark App

タスク固有ルーブリックに基づき、被験LLMを複数judge（OpenAI/Anthropic/Gemini/OpenRouter）で評価するStreamlitアプリです。

## 特徴

- 被験LLMの回答を1回生成し、judge系統ごとに複数回評価
- judge結果は集約せず、系統ごとに並置表示
- JSON結果の保存・読み込み
- 起動時にモデル一覧を取得し、UIから被験/ judgeモデルを選択（取得できない場合は手動入力）
- 11タスクのルーブリック/プロンプトを同梱

## 依存関係

- Python 3.10+
- Streamlit
- openai / anthropic / google-genai
- python-dotenv / pandas / plotly

## セットアップ

1. 依存関係のインストール

```bash
uv sync
```

2. (環境変数の設定)

`.env.example` をコピーして `.env` を作成し、APIキーを設定してください。（ただしUIから保存する場合はこのステップは不要です）

```bash
cp .env.example .env
```

3. アプリ起動

```bash
uv run streamlit run app.py
```

### 追加のリソースパス指定（任意）

- `LLM_BENCHMARK_RUBRICS_DIR`: ルーブリック用ディレクトリ
- `LLM_BENCHMARK_PROMPTS_DIR`: プロンプト用ディレクトリ
- `LLM_BENCHMARK_JUDGE_SYSTEM_PROMPT_PATH`: judgeシステムプロンプトのファイルパス
- `LLM_BENCHMARK_MODEL_CATALOG_TTL_SECONDS`: モデル一覧キャッシュTTL秒（既定: 21600）

## ディレクトリ構成

```
.
├── app.py
├── adapters/
├── core/
├── ui/
├── rubrics/                # 11タスクのルーブリック
├── prompts/                # 11タスクの入力プロンプト
├── judge_system_prompt.md
├── results/                # 実行結果JSON
└── tests/
```

## 結果ファイル

`results/YYYYMMDD_HHMMSS_<model_name>.json` として保存されます。

## 注意事項

- APIキーが設定されていないプロバイダはモデル一覧取得時にスキップされます。
- モデル一覧は起動時にTTL内ならキャッシュを使用し、TTL超過時に再取得します。
- サイドバーの「モデル一覧を再取得」はTTLを無視して強制更新します。
- モデル一覧が空の場合は手動入力欄が表示されます。
- APIキーをUIから保存する場合は `.streamlit/secrets.toml` が作成されます。gitに含めないでください。
- 前回のモデル/タスク選択は `models/last_selection.json` に保存され、再起動後に復元されます。
- judgeのJSONが不正な場合はリトライ後にスキップされます。

## License

MIT License
