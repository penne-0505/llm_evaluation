---
title: "Plan: Code CI gate"
status: active
draft_status: n/a
created_at: 2026-07-26
updated_at: 2026-07-26
references:
  - "_docs/intent/DevOps/code-ci-gate/decision.md"
  - "_docs/qa/DevOps/code-ci-gate/test-plan.md"
  - "_docs/qa/DevOps/code-ci-gate/verification.md"
related_issues: []
related_prs: []
---

# Plan: Code CI gate

## Overview

コード側の自動 gate を新設し、退行検出を人間の記憶から仕組みへ移す。
第一段（gate 新設）は実装・検証済みであり、本 plan は残る 2 つの follow-up を含めた全体像を記述する。

進捗は `_docs/qa/DevOps/code-ci-gate/verification.md` の verdict（現在 `PARTIAL`）が示す。

## Scope

- `Code CI` workflow の新設（backend test matrix、frontend lint / test / build）。**完了**
- テスト間のプロセス共有状態リセット（`tests/conftest.py`）。**完了**
- frontend node test の単一 script 化（`npm run test --prefix frontend`）。**完了**
- `quality_assurance.md` の baseline suite 規範と `AGENTS.md` の整合。**完了**
- GitHub 上での初回 run 確認（DevOps-Test-69）。**未着手**
- Node 版差の方針決定と dev 依存脆弱性の棚卸し（DevOps-Chore-70）。**未着手**

## Non-Goals

- `core` の classmethod シングルトンの再設計。`_docs/intent/DevOps/code-ci-gate/decision.md`
  の DEC-002 `Why not` を参照する。
- server.py / ResultStorage のリファクタ本体。gate はその前提条件であり、作業自体は別タスクとする。
- `_docs/qa/Core/concurrent-evaluation-jobs/verification.md` の遡及修正。当時の記録として保持する。

## Requirements

- **Functional**: push（main / dev）と PR（main）で backend と frontend の失敗が gate として現れる。
  full suite が実行順序に依存せず再現的に緑になる。
- **Non-Functional**: gate の実行時間が開発の反復を阻害しない。
  gate 対象コマンドと `quality_assurance.md` / `AGENTS.md` の記述が乖離しない。

## Tasks

1. ~~`tests/conftest.py` で共有状態を分離し、full suite を緑にする~~ 完了
2. ~~`Code CI` workflow を追加する（最小権限・matrix）~~ 完了
3. ~~`tsx` 固定と `npm run test` 追加~~ 完了
4. ~~baseline suite 規範と `AGENTS.md` の更新~~ 完了
5. [ ] 初回 run を GitHub で確認し、失敗ケースで赤くなることを検証する（DevOps-Test-69）
6. [ ] Node 版差の方針を決め、`npm audit` の各件を分類する（DevOps-Chore-70）

## QA Plan

- QA document: `_docs/qa/DevOps/code-ci-gate/test-plan.md`
- Risk level: High
- Test strategy:
  - Unit: backend full suite（3.12 / 3.14）、frontend node test
  - Integration: gate 対象コマンドを CI と同順でローカル実行し exit code を確認
  - E2E: GitHub Actions 上での実 run（DevOps-Test-69 で実施）
  - Manual QA: workflow の trigger / matrix / 権限の読み合わせ
  - Validator / static check: `./scripts/check-docs.sh`、`markdownlint-cli2`
- AC は test-plan の Test Matrix で確認手段へ割り当て済み。INV-001 は diff review と、
  本 verification 自身の verdict 判断で確認する。
- 影響する DEC は DEC-001 から DEC-005。verification の Decision Conformance で review する。
- Risk High のため、rollback / recovery / data safety / security の観点を test-plan の
  High-risk Checklist に含める。

## Deployment / Rollout

- Rollout: workflow ファイルの追加のみで有効になる。段階導入は行わない。
- 監視: Actions の run 結果。初回 run は DevOps-Test-69 で明示的に確認する。
- Rollback: `.github/workflows/code-ci.yml` を削除すれば gate だけが消える。
  `tests/conftest.py` は順序依存の再発を招くため、単独では戻さない。
