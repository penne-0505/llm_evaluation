---
title: Frontend Common Container
status: active
draft_status: n/a
created_at: 2026-04-17
updated_at: 2026-04-17
references:
  - ./frontend-button.md
related_issues: []
related_prs: []
---

## Overview

`frontend/src/index.css` の `.card` は、フロントエンド全体で使う共通コンテナです。

主な用途は以下です。

- 設定画面の説明・入力ブロック
- Run / Results / Dashboard の情報カード
- エラー表示や空状態のコンテナ

## Behavior

- `.card` は背景、境界線、角丸のみを共通定義する
- 非クリックコンテナに hover 反応を持たせない
- hover を持たせたい場合は、呼び出し側で明示的に `hover:*` を追加する

## Notes

- 以前は `.card:hover` で境界線色を変えていたが、非インタラクティブな説明コンテナにも hover が出ていたため削除した
- クリック可能なカードやボタンの hover は、各コンポーネント側のクラスで個別に維持する
