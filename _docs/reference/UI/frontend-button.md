---
title: Frontend Common Button
status: active
draft_status: n/a
created_at: 2026-04-17
updated_at: 2026-04-17
references:
  - "_docs/reference/UI/frontend-container.md"
related_issues: []
related_prs: []
---

## Overview

`frontend/src/components/Button.tsx` は、フロントエンド内の `button` 要素を共通化するための薄いラッパーです。

目的は以下の 2 点です。

- 既存画面ごとの `className` を維持したまま、ボタン実装を 1 箇所に揃える
- `disabled` 状態のボタンで hover 表現が出る不整合を抑止する

## Behavior

- `ButtonHTMLAttributes<HTMLButtonElement>` をそのまま受け取る
- `type` を省略した場合は `button` を既定値にする
- 呼び出し元の `className` は変更せず、そのまま適用する
- 共通で `cursor-pointer` を付与し、選択可能なボタンでポインタカーソルを表示する
- 共通で `disabled:pointer-events-none` を付与し、無効状態で hover が発火しないようにする

## Usage

- 既存デザインを維持したい場合は、呼び出し元で使っていた `className` をそのまま `Button` に移す
- 無効状態の見た目は、各画面側で `disabled:*` 系クラスを定義し続ける
- hover 色や境界線、shadow などの表現は各画面側の責務とし、`Button` 自体はデザインを持たせない
