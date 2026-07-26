---
title: "Plan: Exclude subject model identity from execution presets"
status: superseded
draft_status: n/a
created_at: 2026-07-26
updated_at: 2026-07-26
references:
  - "_docs/intent/UI/execution-presets/decision.md"
  - "_docs/qa/UI/execution-presets/test-plan.md"
  - "_docs/reference/UI/execution-presets.md"
related_issues: []
related_prs: []
---

# Plan: Exclude subject model identity from execution presets

## Overview

実行プリセットを評価対象モデルから独立した評価条件として扱う。新規プリセットから
被験モデルIDと被験モデル専用preferred hostを除外し、既存schema v1の読込時も
保存済み被験モデルを適用しない。

本planはv0.16.2向け実装とverificationの完了に伴いarchiveした。

## Scope

- execution preset schemaをv2へ更新する。
- schema v1を互換読込し、legacy `subjectModel`を無視する。
- capture / resolve / Settings storeから被験モデルの保存・復元経路を除く。
- judgeまたは包括judgeに使うpreferred hostだけをsnapshotへ保存する。
- unit tests、Settings説明、README、reference、intent、QAを同期する。
- Settingsの優先ホストピッカーが周辺要素に隠れるstacking / clipping問題を修正する。

## Non-Goals

- subject run count、subject temperatureをプリセットから外さない。
- Strict Modeのsubject model policyを変更しない。
- localStorageの既存プリセットを一括書換えしない。
- import / exportやbackend同期を追加しない。
- Settings全体のレイアウトやhost pickerの情報設計を刷新しない。

## Requirements

- **Functional**: プリセット読込前後で現在のcatalog選択・free-text被験モデルを保持する。
- **Functional**: schema v1のjudge、task、包括評価、評価回数、temperatureを引き続き適用する。
- **Non-Functional**: legacyデータの追加fieldを許容し、利用者の既存プリセットを失効させない。
- **Non-Functional**: API keyなど既存の非保存境界を維持する。
- **Non-Functional**: host pickerの候補を既存Settingsレイアウト内で視認・選択できる。

## Tasks

- preset型をschema v1 / v2の互換境界が表現できる形へ更新する。
- capture結果からsubject model identityと専用preferred hostを除く。
- resolve結果からsubject model復元値を除く。
- store適用時にcurrent subject fieldsを保持する。
- legacy、新規、judge兼用hostのregression testsを追加する。
- UI文言とcanonical docsを更新する。
- HostPicker周辺のstacking contextとoverflowを修正し、回帰確認を追加する。

## QA Plan

- QA document: `_docs/qa/UI/execution-presets/test-plan.md`
- Risk level: Medium
- Test strategy:
  - Unit: schema v2 capture、schema v1 resolve、被験モデル非適用、preferred host filtering。
  - Integration: Settings storeのsave / load経路とfrontend test suite。
  - Manual QA: プリセット読込前後の被験モデル表示を比較する。
  - Manual QA: host pickerを開き、後続カードの前面で候補を選択できることを確認する。
  - Validator / static check: frontend lint / build、docs validators。
- AC-001..006とINV-001..003をtest matrixへ割り当てる。
- DEC-002の保存境界とDEC-004の互換読込理由に沿うかdiff reviewする。

## Deployment / Rollout

- `v0.16.2`としてcommit、tag、pushする。
- rollback時はv2作成を停止できるが、作成済みv2プリセットは旧版で未対応となる。
- schema v1は読込時に移行保存せず、利用者が上書きした時点でv2へ更新する。
