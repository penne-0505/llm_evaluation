# Project Task Management Rules

## 0. System Metadata
- **Current Max ID**: `Next ID No: 21` (※タスク追加時にインクリメント必須)
- **ID Source of Truth**: このファイルの `Next ID No` 行が、全プロジェクトにおける唯一のID発番元である。

## 1. Task Lifecycle (State Machine)
タスクは以下の順序で単方向に遷移する。逆行は原則禁止とする。

### Phase 0: Inbox (Human Write-only)
- **Location**: `# Inbox (Unsorted)` セクション
- **Description**: 人間がアイデアや依頼を書き殴る場所。フォーマット不問。ID未付与。
- **Exit Condition**: LLMが内容を解析し、IDを付与して `Backlog` へ構造化移動する。

### Phase 1: Backlog (Structured)
- **Location**: `# Backlog` セクション
- **Status**: タスクとして認識済みだが、着手準備未完了。
- **Entry Criteria**: 
  - IDが一意に採番されている。
  - 必須フィールド（Title, ID, Priority, Size, Area, Description）が埋まっている。
- **Exit Condition**: `Ready` の要件を満たす。

### Phase 2: Ready (Actionable)
- **Location**: `# Ready` セクション
- **Status**: いつでも着手可能な状態。
- **Entry Criteria**:
  - **Plan Requirement**:
    - `Size: M` 以上 (M, L, XL): `Plan` フィールドに有効な `_docs/plan/...` へのリンクが**必須**。
    - `Size: S` 以下 (XS, S): `Plan` は **None** でよい。
  - **Dependencies**: 解決済み（または明確化済み）である。
  - **Steps**: 具体的な実行手順（またはPlanへのポインタ）が記述されている。
- **Exit Condition**: 作業者がタスクに着手する。

### Phase 3: In Progress
- **Location**: `# In Progress` セクション
- **Status**: 現在実行中。
- **Entry Criteria**: 作業者がアサインされている（または自律的に着手）。

### Phase 4: Done
- **Location**: なし（行削除）
- **Exit Action**: `Goal` 達成を確認後、リストから物理削除する。

## 2. Schema & Validation
各タスクは以下の厳格なスキーマに従うこと。

| Field | Type | Constraint / Value Set |
| :--- | :--- | :--- |
| **Title** | `String` | `[Category] Title` 形式。Categoryは後述のEnum参照。 |
| **ID** | `String` | `{Area}-{Category}-{Number}` 形式。不変の一意キー。 |
| **Priority** | `Enum` | `P0` (Critical), `P1` (High), `P2` (Medium), `P3` (Low) |
| **Size** | `Enum` | `XS` (<0.5d), `S` (1d), `M` (2-3d), `L` (1w), `XL` (>2w) |
| **Area** | `Enum` | `_docs/plan/` 直下のディレクトリ名と一致する値。 |
| **Dependencies**| `List<ID>`| 依存タスクIDの配列 `[Core-Feat-1, UI-Bug-2]`。なしは `[]`。 |
| **Goal** | `String` | 完了条件（Definition of Done）。 |
| **Steps** | `Markdown` | 進行管理用のチェックリスト（詳細は後述）。 |
| **Description** | `String` | タスクの詳細。 |
| **Plan** | `Path` | `Size >= M` の場合必須。`_docs/plan/` へのパス。`Size < M` は `None` 可。 |

## 3. Field Usage Guidelines

### Area & Directory Mapping
- **Rule**: `Area` フィールドの値は、`_docs/plan/` 直下に実在するディレクトリ名（ドメイン）と一致させること。
- **New Area**: 新しい領域のタスクを作成する場合、まず `_docs/plan/` にディレクトリを作成してから、その名前を `Area` に指定する。
- **Example**: `Area: Core` -> implies existence of `_docs/plan/Core/`

### Steps vs Plan
タスクの規模に応じて `Steps` の記述方針を切り替えること。情報の二重管理を避ける。

- **Case A: Planあり (Size >= M)**
  - `Steps` は **「Planを実行するための進行管理チェックリスト」** として機能する。
  - 詳細な仕様やコードは Plan に記述し、Steps には複製しない。
  - 例: `1. [ ] Planの "DB Schema" セクションに従いマイグレーション作成`

- **Case B: Planなし (Size < M)**
  - `Steps` に **「具体的な作業手順」** を直接記述する。
  - 例: `1. [ ] src/utils/format.ts の dateFormat 関数を修正`

## 4. Defined Enums

### Categories (Title & ID)
ID生成およびタイトルのプレフィックスには以下のみを使用する。
- `Feat` (New Feature)
- `Enhance` (Improvement)
- `Bug` (Fix)
- `Refactor` (Code Structuring)
- `Perf` (Performance)
- `Doc` (Documentation)
- `Test` (Testing)
- `Chore` (Maintenance/Misc)

### Areas (Examples)
**※実際には `_docs/plan/` のディレクトリ構成に従う。**
- `Core`: 基盤ロジック
- `UI`: プレゼンテーション層
- `Docs`: ドキュメント整備自体
- `General`: 特定ドメインに属さない雑多なタスク
- `DevOps`: CI/CD, 環境構築

## 5. Operational Workflows (for LLM)

### [Action] Create Task from Inbox
1. `Next ID No` を読み取り、割り当て予定のIDを決定する。
2. `Next ID No` をインクリメントしてファイルを更新する。
3. Inboxの内容を解析し、最適な `Area` と `Category` を決定する。
4. IDを生成する（例: `Core-Feat-24`）。
5. タスクをフォーマットし、`Backlog` の末尾に追加する。
6. 元のInbox行を削除する。

### [Action] Promote to Ready
1. **Size check**:
   - `Size >= M` ならば、`Plan` フィールドが有効なリンクであることを検証する。リンク切れや未作成の場合は移動を拒否する。
   - `Size < M` ならば、`Plan` が `None` でも許容する。
2. **Steps check**: `Steps` が具体的か（あるいはPlanへのポインタとして機能しているか）確認する。
3. **Dependency check**: 依存タスクが完了済みか確認する。
4. 全てクリアした場合のみ `Ready` セクションへ移動する。

## 6. Task Definition Examples (Few-Shot)

以下の例を参考に、サイズ（Size）に応じた記述ルール（Planの有無、Stepsの粒度）を厳守すること。

### Case A: Feature Implementation (Size >= M)
**Rule**: `Plan` へのリンクが必須。`Steps` はPlanの参照ポインタとして記述する。

```markdown
- **Title**: [Feat] User Authentication Flow
- **ID**: Core-Feat-25
- **Priority**: P0
- **Size**: M
- **Area**: Core
- **Dependencies**: []
- **Goal**: ユーザーがEmail/Passwordでサインアップおよびログインできる状態にする。
- **Steps**:
  1. [ ] Planの "Schema Design" セクションに基づき、Userテーブルのマイグレーションを作成・適用
  2. [ ] Planの "API Specification" に従い、`/auth/login` エンドポイントを実装
  3. [ ] Planの "Security" に記載されたJWT発行ロジックを実装
  4. [ ] E2Eテストを実施し、ログインフローの疎通を確認
- **Description**: 新規サービスの基盤となる認証機能を実装する。
- **Plan**: `_docs/plan/Core/auth-feature.md`
````

### Case B: Small Fix / Maintenance (Size \< M)

**Rule**: `Plan` は `None` でよい。`Steps` に具体的なコード修正手順を記述する。

```markdown
- **Title**: [Bug] Fix typo in Submit button
- **ID**: UI-Bug-26
- **Priority**: P2
- **Size**: XS
- **Area**: UI
- **Dependencies**: []
- **Goal**: ログイン画面のボタンのラベルが "Subimt" から "Submit" に修正されている。
- **Steps**:
  1. [ ] `src/components/LoginForm.tsx` を開く
  2. [ ] Submitボタンのラベル文字列を修正する
  3. [ ] ブラウザで表示を確認し、レイアウト崩れがないか確認
- **Description**: ユーザーから報告された誤字の修正。
- **Plan**: None
```

### Case C: New Area / Doc Task (Size S)

**Rule**: 新しいAreaが必要な場合、ディレクトリ作成を含む。

```markdown
- **Title**: [Doc] Add Deployment Guide
- **ID**: DevOps-Doc-27
- **Priority**: P1
- **Size**: S
- **Area**: DevOps
- **Dependencies**: [Core-Feat-25]
- **Goal**: 新メンバー向けのデプロイ手順書が `_docs/guide/deployment.md` に作成されている。
- **Steps**:
  1. [ ] `_docs/plan/DevOps/` ディレクトリが存在しないため作成する (Area定義用)
  2. [ ] `_docs/guide/deployment.md` を作成し、ステージング環境へのデプロイ手順を記述
- **Description**: オンボーディングコスト削減のため、暗黙知になっているデプロイ手順をドキュメント化する。
- **Plan**: None
```

--- 

## Inbox

- `_docs/draft/ui_rebuild/feature_inventory.md` の機能インベントリをベースに、UIの再構築案（レイアウト・ナビゲーション・コンポーネント構成）を設計・検討する。
- モデル一覧取得のTTL/並列化
- ROI可視化グラフ：横軸をスコア、縦軸を1MトークンあたりのAPI価格とした散布図。コストパフォーマンスの良いモデルを視覚的に比較できる。将来的にはダッシュボードに追加したい。
- Strict Modeリーダーボード：認証マーク付きのモデルランキングを公開。全ユーザーが同じ条件で評価したスコアを集計し、コストパフォーマンスも考慮したランキング表示を実装したい。
- 検索結果JSON＋記事本文テキストを複数集めて、Deep Research向けの grounding / 因果飛躍チェック用コーパスを作る。

---

## Backlog

- **Title**: [Feat] Finalize Windows portable ZIP distribution
- **ID**: DevOps-Feat-17
- **Priority**: P1
- **Size**: M
- **Area**: DevOps
- **Dependencies**: [Core-Enhance-18, Core-Enhance-19, DevOps-Test-20, DevOps-Doc-21]
- **Goal**: Windows portable ZIP を展開して `prism-llm-eval.exe` を実行するだけでアプリがフル起動し、user override と release 成果物の運用まで含めて配布可能な状態にする。
- **Steps**:
  1. [ ] `Core-Enhance-18` に従い、portable 運用向けの差し替えリソース優先順位を完成させる
  2. [ ] `Core-Enhance-19` に従い、launcher と配布向けエラーメッセージを調整する
  3. [ ] `DevOps-Test-20` に従い、Windows クリーン環境での起動・評価・履歴確認を通す
  4. [ ] `DevOps-Doc-21` に従い、portable ZIP の生成・命名・利用ガイドを確定する
- **Description**: installer を最終ターゲットにせず、Windows 向け portable ZIP を正式配布形態として完成させる。既存の launcher / bundled frontend / app data 保存をベースに、差し替えリソース運用、実機検証、release 成果物整備をまとめて完了させる。
- **Plan**: `_docs/plan/DevOps/windows-portable-zip-finalization.md`

## In Progress

- **Title**: [Feature] ダッシュボード拡張：評価履歴と詳細比較
- **ID**: UI-Feature-16
- **Priority**: P2
- **Size**: M
- **Area**: UI
- **Dependencies**: []
- **Goal**: ダッシュボードに「評価履歴」と「詳細比較」機能を追加し、サイドバーの「過去の結果」を統合する
- **Steps**:
  1. [x] Planの "Phase 1" に従い、基盤整備（データ読み込み、セッション状態）
  2. [ ] Planの "Phase 2" に従い、評価履歴タブを実装
  3. [ ] Planの "Phase 3" に従い、詳細比較タブを実装
  4. [ ] Planの "Phase 4" に従い、サイドバー修正
  5. [ ] Planの "Phase 5" に従い、テスト
- **Description**: ダッシュボードに評価履歴（カード形式+ページネーション）と詳細比較（2モデル比較）機能を追加する
- **Plan**: `_docs/plan/UI-Feature-15-Ext-dashboard-enhancement.md`

---

## Ready


- **Title**: [Test] Validate Windows portable ZIP on clean environment
- **ID**: DevOps-Test-20
- **Priority**: P1
- **Size**: S
- **Area**: DevOps
- **Dependencies**: [Core-Enhance-18, Core-Enhance-19]
- **Goal**: Windows クリーン環境で ZIP 展開後に exe 実行だけで起動し、API キー保存・評価実行・履歴参照まで通ることが確認され、packaging の不足が反映されている。
- **Steps**:
  1. [ ] `_docs/plan/DevOps/windows-portable-zip-execution-breakdown.md` の `WP3` を読み、実機検証観点と対象ファイルを確認する
  2. [ ] `scripts/build_windows_bundle.ps1` で Windows 向け bundle を生成し、ZIP 展開後の実行確認を行う
  3. [ ] 実機で見つかった hidden import / DLL / resource 不足を `packaging/windows/prism-llm-eval.spec`、workflow、コードへ反映する
  4. [ ] 実機検証結果を README または関連 docs に反映する
- **Description**: portable ZIP の成立性を Windows 実機で確認し、packaging 上の不足を潰す。
- **Plan**: None

- **Title**: [Doc] Finalize portable ZIP release artifact and guide
- **ID**: DevOps-Doc-21
- **Priority**: P1
- **Size**: S
- **Area**: DevOps
- **Dependencies**: [DevOps-Test-20]
- **Goal**: GitHub Releases 向け成果物名が portable ZIP 前提で確定し、ZIP 展開・起動・保存先・override 方法を説明するドキュメントが整備されている。
- **Steps**:
  1. [ ] `_docs/plan/DevOps/windows-portable-zip-execution-breakdown.md` の `WP4` を読み、成果物名とドキュメント要件を確認する
  2. [ ] `.github/workflows/windows-bundle.yml` の成果物命名と必要なら SHA256 出力を確定する
  3. [ ] README と必要なら `_docs/guide/` 配下に portable ZIP 利用ガイドを追加する
  4. [ ] user override の保存先、差し替え方法、トラブルシュートを利用者向けに記述する
- **Description**: portable ZIP を release できる状態にし、配布物だけ受け取ったユーザーがドキュメントを読めば利用開始できるようにする。
- **Plan**: None

## In Progress

---
