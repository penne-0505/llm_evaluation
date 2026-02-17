# Documentation Driven Development Template

> This README is available in English and Japanese. English speakers, please scroll down.

## 概要

このリポジトリは私が常用しているドキュメント駆動開発 *(Documentation Driven Development)* のテンプレートです。

開発サイクルはドキュメントと [TODO.md](TODO.md) によって構成されています。

人がサイクルを回すことも出来ますが、基本的にはClaude Codeなどのコーディングエージェントが、この規則に従って自律的な開発を行うために設計されました。

**詳細については [ガイドライン](_docs/documentation_guide.md) を参照してください。**

## 使用方法

1. このリポジトリをフォークまたはクローンします。
2. プロジェクトに合わせてドキュメントと設定ファイルを編集します。
4. 開発を開始します。

### カスタマイズ

使用に当たっては、以下のファイルをプロジェクトに合わせてカスタマイズしてください。

#### Issue Templates

これらの **"Area"** セクションを、プロジェクトに適した内容に変更してください。

- `.github/ISSUE_TEMPLATE/bag_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`

#### AGENTS.md

変更の推奨事項はありませんが、特定コマンドの使用指示が含まれているので、必要に応じて編集してください。

#### CONTRIBUTING.md

- `CONTRIBUTING.md`

このファイルの、`2. 開発環境のセットアップ` セクションを、プロジェクトに合わせて編集してください。ただし、プロジェクトによって大きく対応が変化すると思いますので、全面的に、必要に応じて編集してください。

#### README.md

このREADME自体も、プロジェクトに合わせて編集してください。

#### LICENSE.txt

[LICENSE](LICENSE.txt)についても、特に著作者の表示を編集してください。

## ライセンス

このリポジトリは [MITライセンス](LICENSE.txt) の下でライセンスされています。

---

## Summary

This repository is a template for Documentation Driven Development that I commonly use.

The development cycle is structured around documentation and [TODO.md](TODO.md).

While humans can run the cycle, it is primarily designed for coding agents like Claude Code to autonomously develop according to these rules.

**For more details, please refer to the [Guidelines](_docs/documentation_guide.md).**

## Usage

1. Fork or clone this repository.
2. Edit the documentation and configuration files to suit your project.
3. Start development.

### Customization

When using this template, please customize the following files to fit your project.

#### Issue Templates

Please modify the **"Area"** sections to reflect content appropriate for your project.
- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`

#### AGENTS.md

No specific changes are recommended here, but feel free to edit it as needed, especially if you want to suggest the use of certain commands.

#### CONTRIBUTING.md

- `CONTRIBUTING.md`

Please edit the `2. Setting Up Development Environment` section to suit your project. Since this may vary significantly between projects, feel free to overhaul it as necessary.

#### README.md

Feel free to edit this README itself to suit your project.

#### LICENSE.txt

Please edit the [LICENSE](LICENSE.txt) file, particularly the author attribution.

## License
This repository is licensed under the [MIT License](LICENSE.txt).
