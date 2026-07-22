# LLM Benchmark App Quickstart

## 1. 開発環境

```bash
uv sync
npm ci --prefix frontend
```

backend と frontend は別 terminal で起動します。

```bash
uv run uvicorn server:app --reload --host 127.0.0.1 --port 8000
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5173
```

## 2. Docs-driven workflow

作業前に [AGENTS.md](AGENTS.md)、[TODO.md](TODO.md)、
[_docs/documentation_guide.md](_docs/documentation_guide.md) を読みます。
Size M 以上または Risk Medium 以上のタスクでは Plan / Intent / QA test-plan
を作成し、完了前に verification を残します。

```bash
./scripts/check-docs.sh
npx markdownlint-cli2 "_docs/**/*.md" "_evals/**/*.md" "README.md" \
  "AGENTS.md" "TODO.md" "QUICKSTART.md" "!_docs/archives/**/*" \
  "!_docs/standards/templates/**/*" --config .markdownlint.jsonc
```

CI は legacy compatibility のため、P
`d309974a77c736b6d333819a38460edaeb21e57e` 以降に追加・copy・変更・rename
された docs を `DD_SCOPE_DIFF_FILTER=ACMR` で検証します。この scope は
owner-approved の repository-wide strict schema、frontmatter/link/intent
migration が PASS を記録して置換するまで有効です。

## 3. Project checks

```bash
uv run pytest
npm run lint --prefix frontend
npm run build --prefix frontend
timeout 8s uv run prism-llm-eval --no-browser --port 8765
```

外部 provider の API key が必要な live judge 評価は、通常のローカル回帰確認に
含めません。
