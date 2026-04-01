---
title: Model Selection UI
status: proposed
draft_status: n/a
created_at: 2026-02-18
updated_at: 2026-04-03
references:
  - _docs/plan/Core/model-selection-from-api.md
related_issues: []
related_prs: []
---

## Overview
- UIでモデル選択を行うための方針と仕様を定義する。

## Scope
- モデル一覧が取得できる場合はドロップダウンで選択する。
- モデル一覧が取得できない場合は手動入力欄を提供する。
- 既存の保存済み選択（対象/ judge/温度/試行回数）の復元を維持する。

## Non-Goals
- モデル一覧取得ロジックの変更（Core側の実装は対象外）。
- 新しいプロバイダ追加。

## Requirements
- **Functional**:
  - モデル一覧が存在する場合、評価対象は単一選択、judgeは同一UI基盤の複数選択とする。
  - モデル選択UIは検索可能な combobox とし、モデル名・ID・プロバイダ名で絞り込めること。
  - モデル一覧が空の場合は手動入力に切り替える。
  - 手動入力はカンマ区切りでjudgeを指定できる。
- **Non-Functional**:
  - UIでの選択肢は短時間で判別可能なラベルを維持する。

## Tasks
- UIコンポーネントの条件分岐を実装し、一覧あり/なしのUXを整理する。
- 評価対象モデルと judge モデルで一覧表示・行レイアウトを揃え、judge 側のみ複数選択トグルを許可する。
- 入力欄と候補一覧を統合し、入力中に候補を絞り込めるようにする。
- 既存の選択保存/復元が継続されることを確認する。

## Test Plan
- APIキーが未設定でモデル一覧が空の状態で、手動入力が表示されることを確認。
- モデル一覧がある状態で、評価対象/ judge が同系統のドロップダウンとして表示され、judge のみ複数選択できることを確認。
- モデル一覧がある状態で、入力値に応じて候補が絞り込まれることを確認。

## Deployment / Rollout
- 通常のアプリ更新に含める。
