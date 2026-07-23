#!/usr/bin/env bash
set -euo pipefail

deno fmt --check scripts/*.ts
deno check scripts/*.ts
deno run --allow-read --allow-env --allow-run=git scripts/validate-frontmatter.ts
deno run --allow-read scripts/validate-todo.ts
deno run --allow-read --allow-env --allow-run=git scripts/validate-doc-links.ts
deno run --allow-read --allow-env --allow-run=git scripts/validate-intent.ts
deno run --allow-read --allow-env --allow-run=git scripts/validate-qa.ts
deno run --allow-read --allow-write --allow-env --allow-run scripts/test-validators.ts
deno run --allow-read --allow-write --allow-env --allow-run scripts/test-agent-workflow-hook.ts
deno run --allow-read scripts/test-agent-workflow-smoke.ts
