---
title: "QA Test Plan: Code CI gate"
status: active
draft_status: n/a
qa_status: planned
risk: High
qa_schema: 2
created_at: 2026-07-26
updated_at: 2026-07-26
references:
  - "_docs/intent/DevOps/code-ci-gate/decision.md"
  - "_docs/plan/DevOps/code-ci-gate/plan.md"
  - "_docs/standards/quality_assurance.md"
related_issues: []
related_prs: []
---

# QA Test Plan: `Code CI gate`

## Source of Intent

- TODO: DevOps-Test-69 / DevOps-Chore-70（gate 新設そのものは完了時点で TODO へ残さず、
  残る follow-up のみをタスクとして保持する）
- Plan: `_docs/plan/DevOps/code-ci-gate/plan.md`
- Intent: `_docs/intent/DevOps/code-ci-gate/decision.md`

## Quality Goal

コードの退行を人間の記憶に依存せず検出できる状態にする。具体的には、push / PR の時点で
backend と frontend の失敗が gate として現れ、かつ full suite が実行順序に依存せず
再現的に緑になること。

## Acceptance Criteria

- AC-001: `uv run pytest` が full suite で緑になり、単独実行との結果差（順序依存）が無い。
- AC-002: backend テストが release build 版（3.12）と開発版（3.14）の双方で緑になる。
- AC-003: frontend の 13 個の node test が単一コマンド `npm run test --prefix frontend` で
  すべて実行される。
- AC-004: `Code CI` workflow が push（main / dev）と PR（main）で backend test と
  frontend lint / test / build を実行する。
- AC-005: `quality_assurance.md` に baseline suite 規範があり、赤い suite で `PASS` を
  出せないことと、既知の失敗を TODO 起票へ回すことが明記されている。
- AC-006: 既存の Docs CI が本変更後も緑のままである。

## Decision Review Scope

- DEC-001: gate 対象が release build と同じコマンド一式になっているか。
- DEC-002: 本番シングルトンの挙動を変えずにテスト分離を達成しているか。
- DEC-003: node test の実行手段が単一 script に集約されているか。
- DEC-004: 出荷版と開発版の双方が gate されているか。
- DEC-005: 規範が「未確認」と「失敗」を区別しているか。

## Intent-derived Invariants

- INV-001 (from DEC-005): full suite に失敗が残る状態の verification verdict を `PASS` にしない。

## Risk Assessment

- Risk level: High
- Risk rationale: CI/CD に関わる変更であり、`quality_assurance.md` は全タスクの完了判定を
  規定する文書であるため、誤ると以後すべてのタスクの品質判定に影響する。
- Regression risk: `tests/conftest.py` は全 backend テストへ無条件に適用される。
  リセット対象を誤ると、自前で状態を管理しているテストの前提を壊しうる。
- Data safety risk: なし。テスト実行と CI 定義のみで、利用者データへ触れる変更を含まない。
- Security / privacy risk: workflow は secret を参照せず、`permissions` を昇格しない。
  新規 dev 依存 `tsx` はビルド成果物へ載らない。
- UX risk: なし。アプリの挙動を変更しない。
- Agent misbehavior risk: 主に 3 点。
  1. agent が `npm run test` を知らず、旧来の個別 `npx tsx --test` 運用へ戻る。
  2. agent が赤い suite を `PARTIAL` で通す旧運用へ戻る。
  3. agent が conftest のリセット対象を安易に拡大し、テストの前提を壊す。

## Test Strategy

- Unit: 既存 backend / frontend テストを full suite として実行し、結果と実行時間を比較する。
- Integration: gate 対象コマンドを CI と同じ順序でローカル実行し、exit code を確認する。
- E2E: 対象外（CI 実行自体は push 後に GitHub 上で確認する）。
- Manual QA: workflow 定義の trigger / matrix / job 構成を読み合わせる。
- Validator / static check: `./scripts/check-docs.sh` と `markdownlint-cli2`。
- Diff review: conftest のリセット対象が、漏れを実証したものに限られているかを確認する。

## Test Matrix

| ID | Source | Requirement / Optional Invariant | Test Type | Command / File | Expected Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | TODO | full suite が順序依存なく緑 | unit | `uv run pytest -q` | 213 passed、単独実行と同結果 | planned |
| AC-002 | TODO | 3.12 / 3.14 双方で緑 | unit | `uv run --python 3.12 pytest -q` | 両版で 213 passed | planned |
| AC-003 | TODO | node test が単一コマンドで全実行 | unit | `npm run test --prefix frontend` | 13 ファイル / 66 tests pass | planned |
| AC-004 | TODO | CI が push / PR で gate する | diff review | `.github/workflows/code-ci.yml` | trigger と job 構成が release build と一致 | planned |
| AC-005 | TODO | baseline suite 規範の存在 | diff review | `_docs/standards/quality_assurance.md` | 未確認と失敗の区別、TODO 起票要求 | planned |
| AC-006 | TODO | Docs CI 維持 | validator | `./scripts/check-docs.sh` | exit 0 | planned |
| INV-001 | DEC-005 | 赤い suite で PASS を出さない | diff review | `_docs/standards/quality_assurance.md` | 規範として明文化 | planned |

## Manual QA Checklist

- [ ] `code-ci.yml` の trigger が `docs-ci.yml` と同じ branch 条件である。
- [ ] matrix の Python 版が release build（3.12）と `.python-version`（3.14）に一致する。
- [ ] workflow が secret を参照せず、`permissions` を昇格していない。
- [ ] `AGENTS.md` のコマンド一覧が gate 対象と一致する。

## Regression Checklist

- [ ] `tests/conftest.py` 追加後も既存テストの pass 数が減っていない。
- [ ] conftest のリセット対象が、漏れを実証した 3 つに限られている。
- [ ] `npm ci` が更新後の lock で成功する。
- [ ] frontend build 成果物が生成される。

## High-risk Checklist

Use this section only for Risk High / Critical.

- [ ] Rollback or recovery path is documented.（`code-ci.yml` 削除で gate のみ除去できる）
- [ ] Data safety has been checked.（利用者データへ触れない）
- [ ] Security / privacy implications have been checked.（secret 不参照、dev 依存は非出荷）
- [ ] Failure mode is understood.（gate 失敗時は merge を止めるだけで、実行時挙動へ波及しない）

## Out of Scope

- `core` の classmethod シングルトンそのものの再設計（DEC-002 の Why not を参照）。
- `npm audit` が報告する既存 dev 依存の脆弱性対応。
- Node のローカル版（24）と CI / release 版（22）の差の gate。
- `_docs/qa/Core/concurrent-evaluation-jobs/verification.md` の遡及修正。当時の記録として保持する。

## Open Questions

- Node のバージョン差を matrix 化するか、release 版へ揃えるか。
