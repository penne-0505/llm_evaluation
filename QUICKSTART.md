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

CIとローカルwrapperは同じunscoped validatorを実行し、live docsとarchive
invariantをrepository-wideに検証します。`DD_SCOPE_BASE`等の段階的導入scopeは
template機能として残りますが、このrepositoryのCIでは使用しません。

## 3. Project checks

```bash
uv run pytest
npm run lint --prefix frontend
npm run build --prefix frontend
timeout 8s uv run prism-llm-eval --no-browser --port 8765
```

外部 provider の API key が必要な live judge 評価は、通常のローカル回帰確認に
含めません。
