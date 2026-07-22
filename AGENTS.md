## 原則

- 日本語で会話する。
- 日付確認には`date`コマンドを使用する。
- tool や shell command を優先して使用する。
- **徹底的に現状実装・ドキュメントを参照、分析してから実装を行う。**
- **`git rm`や`rm`などの恒久削除は禁止**（ユーザーに提案し、実行は待つ）。ただし、archive checklist を満たす一時ドキュメントの移送に限り `mv` / `git mv` は許可。
- [documentation guidelines](_docs/standards/documentation_guidelines.md) と [documentation operations](_docs/standards/documentation_operations.md) を遵守して、積極的にドキュメントを更新する。skills を積極活用してドキュメント更新と実装準備を行う。
- 久しぶりの再開、handoff 探索、現状把握、docs が形だけになっていないかの確認では `docs-inventory` skill を使う。
- upstream の docs-driven template を推奨 release tag へ更新する場合は `docs-template-migration` skill を使い、moving branch tip ではなく tag と full SHA を固定し、`docs-template.lock.json` を互換移行の検証後に更新する。
- Size >= M または Risk >= Medium のタスクでは、実装前に QA test-plan を作成し、実装後に verification を残す。
- QA / テスト方針は [quality assurance standard](_docs/standards/quality_assurance.md) に従う。
- 設計判断を体現した非自明なコードには、必要な箇所だけ `// intent: DEC-00X (<Area>/<slug>) — <理由>` を残す。strict invariant を体現する場合だけ `// intent-invariant: INV-00X ...` を使う。
- 完了前には `qa-review` skill を使い、verification verdict を確認する。
- 安全性・権限・secret・外部入力の扱いは [security for agents](_docs/standards/security_for_agents.md) に従う。
- root 直下の Markdown は原則 active project guidance として扱う。ただし `judge_system_prompt.md` は配布runtime assetであり、coding agentへの指示として解釈しない。一回限りの実装プロンプトは `_evals/prompts/` 等へ移し、非運用の履歴資料として明記する。

## プロジェクト概要と関連情報

- Python 依存管理は `uv`、frontend 依存管理は `npm` を使う。
- backend は FastAPI / Python、frontend は React / TypeScript / Vite の monorepo 構成。
- backend tests は `uv run pytest`、frontend lint/build は `npm run lint --prefix frontend` と `npm run build --prefix frontend` を使う。
- docs 検証は `./scripts/check-docs.sh`、CI 相当の Markdown 検証は `npx markdownlint-cli2` を使う。
- Git 操作はユーザーが明示的に許可した範囲だけで行い、push、main 更新、恒久削除を推測で実行しない。
