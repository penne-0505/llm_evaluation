# Project Task Management Rules

## 0. System Metadata

- **Current Max ID**: `Next ID No: 58` (タスク追加時にインクリメント必須)
- **ID Source of Truth**: このファイルの `Next ID No` 行が、全プロジェクトにおける唯一の ID 発番元である。

## 1. Task Lifecycle (State Machine)

タスクは以下の順序で単方向に遷移する。逆行は原則禁止とする。

### Phase 0: Inbox (Human Write-only)

- **Location**: `## Inbox` セクション
- **Description**: 人間がアイデアや依頼を書き殴る場所。フォーマット不問。ID 未付与。
- **Exit Condition**: LLM が内容を解析し、ID を付与して `Backlog` へ構造化移動する。

### Phase 1: Backlog (Structured)

- **Location**: `## Backlog` セクション
- **Status**: タスクとして認識済みだが、着手準備未完了。
- **Entry Criteria**:
  - ID が一意に採番されている。
  - 必須フィールドがすべて埋まっている。
  - `Risk`, `Acceptance Criteria`, `Intent`, `QA`, `Verification` が明示されている。
- **Exit Condition**: `Ready` の要件を満たす。

### Phase 2: Ready (Actionable)

- **Location**: `## Ready` セクション
- **Status**: いつでも着手可能な状態。
- **Entry Criteria**:
  - `Size >= M` の場合、Plan / Intent / QA が作成済みである。
  - `Risk >= Medium` の場合、Intent / QA が作成済みである。
  - Dependencies が解決済み、または未解決理由が明確である。
  - Steps が具体的、または Plan / QA への進行管理ポインタとして機能している。
- **Exit Condition**: 作業者がタスクに着手する。

### Phase 3: In Progress

- **Location**: `## In Progress` セクション
- **Status**: 現在実行中。
- **Entry Criteria**: 作業者がアサインされている、または自律的に着手している。

### Phase 4: Completed

- **Location**: なし。完了タスクは `TODO.md` から削除する。
- **Exit Action**: Goal と Acceptance Criteria の達成、および必要な verification verdict を確認後に削除する。
- **History**: 完了履歴は PR / commit / CHANGELOG / intent / guide / reference / QA verification に残す。`TODO.md` に Done / Archived セクションは作らない。

## 2. Schema & Validation

各タスクは以下のフィールドを必須とする。

| Field | Type | Constraint / Value Set |
| --- | --- | --- |
| **Title** | `String` | `[Category] Title` 形式。Category は後述の Enum 参照。 |
| **ID** | `String` | `<Area>-<Category>-<Number>` 形式。不変の一意キー。 |
| **Priority** | `Enum` | `P0` / `P1` / `P2` / `P3` |
| **Size** | `Enum` | `XS` / `S` / `M` / `L` / `XL` |
| **Risk** | `Enum` | `Low` / `Medium` / `High` / `Critical` |
| **Area** | `String` | タスクの論理領域。各 canonical path の `<Area>` と一致させる。 |
| **Dependencies** | `List<ID>` | 依存タスク ID の配列。なしは `[]`。 |
| **Goal** | `String` | 完了後に成り立つ状態を一文で書く。 |
| **Acceptance Criteria** | `Markdown` | `AC-001` 形式で、検証可能な条件を書く。 |
| **Steps** | `Markdown` | 進行管理用チェックリスト。 |
| **Description** | `Markdown` | Context / Notes を含める。 |
| **Plan** | `Path` | `None` または `_docs/plan/<Area>/<slug>/plan.md`。 |
| **Intent** | `Path` | `None` または `_docs/intent/<Area>/<slug>/decision.md`。 |
| **QA** | `Path` | `None` または `_docs/qa/<Area>/<slug>/test-plan.md`。 |
| **Verification** | `Path` | `None` または `_docs/qa/<Area>/<slug>/verification.md`。 |

推奨形式:

```markdown
### <ID>: [<Category>] <Title>

- **Title**: [<Category>] <Title>
- **ID**: <Area>-<Category>-<Number>
- **Priority**: P0 | P1 | P2 | P3
- **Size**: XS | S | M | L | XL
- **Risk**: Low | Medium | High | Critical
- **Area**: <Area>
- **Dependencies**: []
- **Goal**: <one sentence>
- **Acceptance Criteria**:
  - AC-001:
  - AC-002:
- **Steps**:
  1. [ ] Step 1
  2. [ ] Step 2
- **Description**:
  - Context:
  - Notes:
- **Plan**: None | _docs/plan/<Area>/<slug>/plan.md
- **Intent**: None | _docs/intent/<Area>/<slug>/decision.md
- **QA**: None | _docs/qa/<Area>/<slug>/test-plan.md
- **Verification**: None | _docs/qa/<Area>/<slug>/verification.md
```

## 3. Required Documents

| Condition | Requirement |
| --- | --- |
| `Size XS/S` and `Risk Low` | Plan / Intent / QA / Verification は `None` 可。 |
| `Size >= M` | Plan / Intent / QA が必須。 |
| `Risk >= Medium` | Intent / QA が必須。 |
| `Risk High / Critical` | Plan / Intent / QA が必須。完了前に Verification が必須。 |
| `Category Bug` | Acceptance Criteria に再発防止条件を含め、QA test-plan に regression test または no-test rationale を含める。 |
| `Category Refactor` | QA test-plan に behavior-preservation checks を含める。 |
| Agent workflow / validator / CI / Skill / documentation rule 変更 | QA test-plan に agent misbehavior checks を含める。 |

`Size XS/S` かつ `Risk Low` でも、将来の作業者が未実装と誤認しそうな非対応・制限・省略は intentional omission risk として扱う。その場合は、必須フィールドを増やさず、TODO Description / PR / commit、または必要に応じて Plan Non-Goals / Intent の DEC（Why / Why not）に理由を残す。

## 4. Completion Rules

タスクを `TODO.md` から削除できるのは、以下を満たす場合のみ。

1. Steps が完了している。
2. Acceptance Criteria が満たされている。
3. `Size >= M` または `Risk >= Medium` の場合、`verification.md` が存在する。
4. verification verdict が `PASS` である。
5. `PARTIAL` の場合は、残リスクと follow-up TODO が明記されている。
6. `FAIL` / `BLOCKED` の場合は完了扱いにしない。
7. 必要な intent / guide / reference / QA docs が更新されている。

完了履歴は `verification.md`、intent、guide、reference、PR / commit に残す。`TODO.md` は未完了作業の source of truth として保つ。

## 5. Canonical Document Paths

```text
_docs/draft/<Area>/<slug>/notes.md
_docs/survey/<Area>/<slug>/survey.md
_docs/plan/<Area>/<slug>/plan.md
_docs/intent/<Area>/<slug>/decision.md
_docs/qa/<Area>/<slug>/test-plan.md
_docs/qa/<Area>/<slug>/verification.md
_docs/guide/<Area>/<slug>/usage.md
_docs/reference/<Area>/<slug>/reference.md
_docs/archives/{draft,plan,survey}/<Area>/<slug>/...
```

`<Area>` はタスクの `Area` と一致させる。`<slug>` は機能・変更単位の kebab-case 名にする。`intent` / `qa` / `guide` / `reference` は archive 対象にしない。

## 6. Defined Enums

### Categories (Title & ID)

- `Feat` (New Feature)
- `Enhance` (Improvement)
- `Bug` (Fix)
- `Refactor` (Code Structuring)
- `Perf` (Performance)
- `Doc` (Documentation)
- `Test` (Testing)
- `Chore` (Maintenance/Misc)

### Priorities

- `P0`: Critical / immediate
- `P1`: High
- `P2`: Medium
- `P3`: Low

### Sizes

- `XS`: 0.5 day 未満
- `S`: 1 day 程度
- `M`: 2-3 days 程度
- `L`: 1 week 程度
- `XL`: 2 weeks 以上

### Risk

Risk の詳細は `_docs/standards/quality_assurance.md` を参照する。

- `Low`: 局所的で失敗影響が小さい変更。
- `Medium`: 機能挙動、ワークフロー、validator、ドキュメント規約、agent skill に影響する変更。
- `High`: 互換性、データ損失、認証、権限、セキュリティ、課金、外部 API、CI/CD、migration に関わる変更。
- `Critical`: 本番障害、secret 漏洩、重大なデータ破壊、ユーザー影響の大きい破壊的変更につながり得る変更。

## 7. Operational Workflows (for LLM)

### Create Task from Inbox

1. `Next ID No` を読み取り、割り当て予定の ID を決定する。
2. `Next ID No` をインクリメントしてファイルを更新する。
3. Inbox の内容を解析し、最適な `Area` / `Category` / `Risk` を決定する。
4. intentional omission risk があるか確認する。将来「未実装なので直す」と誤認されそうな非対応・制限・省略がある場合は、Description に理由を残すか、設計判断として Intent を作成する。
5. ID を生成する。
6. Acceptance Criteria を `AC-001` 形式で書く。
7. 必須文書条件に従い、Plan / Intent / QA / Verification を `None` または canonical path で埋める。
8. タスクを `Backlog` の末尾に追加する。
9. 元の Inbox 行を削除する。

### Promote to Ready

1. `Size >= M` なら Plan / Intent / QA が存在することを確認する。
2. `Risk >= Medium` なら Intent / QA が存在することを確認する。
3. QA test-plan の Test Matrix が主要 AC と、存在する場合の INV を最低 1 つの確認手段へ割り当て、影響する DEC の review scope を示していることを確認する。
4. Dependencies が解決済みか確認する。
5. 全てクリアした場合のみ `Ready` セクションへ移動する。

### Complete Task

1. Steps と Acceptance Criteria を確認する。
2. `Size >= M` または `Risk >= Medium` なら `qa-review` skill を使う。
3. verification verdict が `PASS`、または許容済み `PARTIAL` であることを確認する。
4. `FAIL` / `BLOCKED` の場合は、タスクを残すか follow-up を追加する。
5. 完了可能な場合のみ `TODO.md` から削除する。

## 8. Task Definition Examples

### Case A: XS/S + Low Risk Task

```markdown
### Docs-Chore-10: [Chore] Update project display name

- **Title**: [Chore] Update project display name
- **ID**: Docs-Chore-10
- **Priority**: P2
- **Size**: XS
- **Risk**: Low
- **Area**: Docs
- **Dependencies**: []
- **Goal**: README と Quickstart の表示名がプロジェクト名に置き換わっている。
- **Acceptance Criteria**:
  - AC-001: README の旧テンプレート名が新しいプロジェクト名に置き換わっている。
  - AC-002: Quickstart の初回案内が新しいプロジェクト名を参照している。
- **Steps**:
  1. [ ] README.md を更新する
  2. [ ] QUICKSTART.md を更新する
- **Description**:
  - Context: 新規プロジェクト作成直後の軽量カスタマイズ。
  - Notes: Plan / Intent / QA は不要。
- **Plan**: None
- **Intent**: None
- **QA**: None
- **Verification**: _docs/qa/Workflow/docs-template-v1-migration/verification.md
```

### Case B: Size M + Medium Risk Task

```markdown
### Core-Enhance-11: [Enhance] Add onboarding command

- **Title**: [Enhance] Add onboarding command
- **ID**: Core-Enhance-11
- **Priority**: P1
- **Size**: M
- **Risk**: Medium
- **Area**: Core
- **Dependencies**: []
- **Goal**: 新規メンバーが onboarding command で初期診断を実行できる。
- **Acceptance Criteria**:
  - AC-001: command が環境診断を実行し、結果を標準出力に表示する。
  - AC-002: decision の Why / Change freedom が記録され、必要な場合だけ intent-derived invariant に基づくテストまたは validator が存在する。
- **Steps**:
  1. [ ] Plan の Scope / Non-Goals を確認する
  2. [ ] QA test-plan の Test Matrix に従って実装と検証を進める
- **Description**:
  - Context: ユーザー向け workflow が増えるため Medium risk とする。
  - Notes: Plan / Intent / QA が必須。
- **Plan**: _docs/plan/Core/onboarding-command/plan.md
- **Intent**: _docs/intent/Core/onboarding-command/decision.md
- **QA**: _docs/qa/Core/onboarding-command/test-plan.md
- **Verification**: None
```

### Case C: Agent Workflow / Validator / Skill Task

```markdown
### Workflow-Chore-12: [Chore] Tighten TODO validator

- **Title**: [Chore] Tighten TODO validator
- **ID**: Workflow-Chore-12
- **Priority**: P1
- **Size**: M
- **Risk**: Medium
- **Area**: Workflow
- **Dependencies**: []
- **Goal**: TODO validator が新 schema と QA 必須条件を検出できる。
- **Acceptance Criteria**:
  - AC-001: validator が Risk / Intent / QA 欠落を error として検出する。
  - AC-002: QA test-plan に agent misbehavior checks が含まれている。
- **Steps**:
  1. [ ] Plan / Intent / QA を読む
  2. [ ] validator を更新する
  3. [ ] agent misbehavior checks を verification に残す
- **Description**:
  - Context: Agent workflow / validator / Skill 変更では、agent が古い運用へ戻るリスクを検証する。
  - Notes: `validate-todo` と `validate-qa` の両方を実行する。
- **Plan**: _docs/plan/Workflow/todo-validator/plan.md
- **Intent**: _docs/intent/Workflow/todo-validator/decision.md
- **QA**: _docs/qa/Workflow/todo-validator/test-plan.md
- **Verification**: None
```

---

## Inbox

- (empty)

---

## Backlog

### Core-Bug-50: [Bug] Persist standard results when holistic adapters fail

- **Title**: [Bug] Persist standard results when holistic adapters fail
- **ID**: Core-Bug-50
- **Priority**: P1
- **Size**: S
- **Risk**: High
- **Area**: Core
- **Dependencies**: []
- **Goal**: 包括評価用 judge adapter 解決に失敗しても、完了済み標準タスク結果が `ResultStorage` に保存される。
- **Acceptance Criteria**:
  - AC-001: `run_holistic=true` かつ holistic judge の API キー不足などで adapter が空のとき、SSE error のあとも標準タスク結果 JSON が保存される（または既存 cancel/partial 方針と同等の recoverable 保存になる）。
  - AC-002: Intent Consequences の「API key 不足時は holistic 開始前にエラーまたは partial failure 方針を既存 holistic failure 処理に合わせる」と実装が一致する。
  - AC-003: 回帰テストが「standard 完了 → holistic adapter 失敗 → 保存あり」を固定する。
- **Steps**:
  1. [ ] `server.py` の holistic adapter 空時 `return` を、保存経路を飛ばさない形へ直す
  2. [ ] partial failure / error SSE と保存済み `holistic_judge_models` 表現を決める
  3. [ ] `tests/test_server_frontend.py` 等に回帰を追加する
- **Description**:
  - Context: 未コミット差分レビュー。`server.py` は holistic adapter 解決失敗で SSE error 後に即 `return` し、後続の `ResultStorage.save` に到達しない。`holistic_judge_models` 分離後は「標準は成功・包括だけキー不足」が起きやすく、有料実行結果が消える。
  - Notes: Bugbot / code audit 共通指摘。参照 Intent `_docs/intent/Core/holistic-judge-model/decision.md` Consequences。
- **Plan**: None
- **Intent**: _docs/intent/Core/holistic-judge-model/decision.md
- **QA**: None
- **Verification**: None

### Core-Bug-51: [Bug] Dashboard leaderboard must not coerce null hero to 0

- **Title**: [Bug] Dashboard leaderboard must not coerce null hero to 0
- **ID**: Core-Bug-51
- **Priority**: P1
- **Size**: S
- **Risk**: Medium
- **Area**: Core
- **Dependencies**: []
- **Goal**: 有効 hero スコアが無いモデルのダッシュボード集計が `0` ではなく N/A（欠損）として扱われる。
- **Acceptance Criteria**:
  - AC-001: `averageScore` / `bestScore` が全て null のモデル行で平均・最良が `0` 表示にならない。
  - AC-002: DEC-004 / INV-001（全除外時のサイレント 0 禁止）が Dashboard 集計経路でも成り立つ。
  - AC-003: 集計 helper の node test が null-only ケースを固定する。
- **Steps**:
  1. [ ] `DashboardPage.tsx` の `buildModelAggregates` で scores 空時の `avgScore: 0` / `best: 0` フォールバックをやめる
  2. [ ] 表・チャート表示を N/A 扱いに揃える
  3. [ ] node test を追加し、exclude verification の Residual Risks を更新する
- **Description**:
  - Context: ResultDetail は null→`—` だが、Dashboard は null hero を scores に入れず空配列時 `avgScore: 0`。exclude-ON 全除外 run があるとリーダーボード上で真の 0 点と区別できない。
  - Notes: Intent DEC-004。参照 `_docs/intent/Core/exclude-unreliable-judges/decision.md`。
- **Plan**: None
- **Intent**: _docs/intent/Core/exclude-unreliable-judges/decision.md
- **QA**: _docs/qa/Core/exclude-unreliable-judges/test-plan.md
- **Verification**: None

### Core-Bug-52: [Bug] Surface cross_judge_divergence in review flags

- **Title**: [Bug] Surface cross_judge_divergence in review flags
- **ID**: Core-Bug-52
- **Priority**: P1
- **Size**: S
- **Risk**: Medium
- **Area**: Core
- **Dependencies**: []
- **Goal**: 集計除外理由 `cross_judge_divergence` が ResultDetail の要確認 flags でも追跡できる。
- **Acceptance Criteria**:
  - AC-001: 同一 task で judge 間 mean range > 15 のとき、除外候補/除外一覧と整合する review flag が出る。
  - AC-002: DEC-001 の「`computeReviewFlags` の警告対象と集計除外を一致」が `cross_judge_divergence` でも成り立つ。
  - AC-003: ResultDetail / judgeReliability の node test が当該理由コードを固定する。
- **Steps**:
  1. [ ] `computeReviewFlags` または scoreAggregation 由来表示で divergence を出す方針を決める
  2. [ ] UI とラベル（`RELIABILITY_REASON_LABELS`）を接続する
  3. [ ] テストと exclude test-plan / verification を更新する
- **Description**:
  - Context: backend `collect_unreliable_judges` は `cross_judge_divergence` を付与するが、`ResultDetail.tsx` の `computeReviewFlags` は SD / low confidence / critical fail のみ。除外はされるが要確認リストに出ない。
  - Notes: Intent DEC-001 Why。参照 `_docs/intent/Core/exclude-unreliable-judges/decision.md`。
- **Plan**: None
- **Intent**: _docs/intent/Core/exclude-unreliable-judges/decision.md
- **QA**: _docs/qa/Core/exclude-unreliable-judges/test-plan.md
- **Verification**: None

### Core-Bug-53: [Bug] Gate Gemini non-reasoning api_reasoning extraction

- **Title**: [Bug] Gate Gemini non-reasoning api_reasoning extraction
- **ID**: Core-Bug-53
- **Priority**: P1
- **Size**: S
- **Risk**: Medium
- **Area**: Core
- **Dependencies**: []
- **Goal**: catalog 上 reasoning 非サポートの Gemini judge では `api_reasoning` 抽出（タグ fallback 含む）を行わないか、Intent DEC-002 を実装に合わせて改訂する。
- **Acceptance Criteria**:
  - AC-001: reasoning 非サポート Gemini で content 内 `<thinking>` 相当があっても `api_reasoning` が保存されない、または Intent が「共通 helper + 空フィールド時タグ fallback」へ改訂され Why not が残る。
  - AC-002: thinking サポート Gemini / Claude の抽出は現行どおり維持される。
  - AC-003: adapter / prompt contract テストが no-support 境界を固定する。
- **Steps**:
  1. [ ] catalog / capability ゲート実装か Intent 改訂かを決める
  2. [ ] `extract_api_reasoning_from_message` 呼び出し側または helper を修正する
  3. [ ] claude-gemini verification の DEC-002 証拠を実挙動に合わせて更新する
- **Description**:
  - Context: Intent DEC-002 は catalog 非サポート Gemini で thinking 抽出を試みないと書く。実装は全モデル共通で CC fields → `<thinking>` fallback。verification の PASS は空 stub のみで、タグ fallback 抑止は未検証。
  - Notes: 参照 `_docs/intent/Core/claude-gemini-judge-thinking/decision.md` DEC-002。
- **Plan**: None
- **Intent**: _docs/intent/Core/claude-gemini-judge-thinking/decision.md
- **QA**: _docs/qa/Core/claude-gemini-judge-thinking/test-plan.md
- **Verification**: None

### Core-Bug-54: [Bug] Keep ETA meaningful during holistic phase

- **Title**: [Bug] Keep ETA meaningful during holistic phase
- **ID**: Core-Bug-54
- **Priority**: P2
- **Size**: S
- **Risk**: Medium
- **Area**: Core
- **Dependencies**: []
- **Goal**: 標準タスク完了後〜包括評価実行中に ETA が「実測 0（完了）」と誤表示されない。
- **Acceptance Criteria**:
  - AC-001: standard lane 完了かつ holistic 未完了のとき `eta_ms: 0` + `eta_status: measured` にならない。
  - AC-002: remaining カウントまたは status が holistic 残作業を反映する。
  - AC-003: server / frontend の進捗テストが当該遷移を固定する。
- **Steps**:
  1. [ ] `_compute_progress_eta` と remaining 入力（standard-only フィルタ）を見直す
  2. [ ] holistic 残件がある間の status / eta 表示を決める
  3. [ ] 回帰テストを追加する
- **Description**:
  - Context: remaining が standard 完了で 0 になると measured ETA 0 を返す。包括フェーズ中も UI が完了扱いの推定を出しうる。
  - Notes: 参照 `_docs/intent/Core/task-duration-eta/decision.md` DEC-002/003。`total_steps` と holistic 実 judge 数のずれは関連調査として本タスク Notes に残してよい。
- **Plan**: None
- **Intent**: _docs/intent/Core/task-duration-eta/decision.md
- **QA**: _docs/qa/Core/task-duration-eta/test-plan.md
- **Verification**: None

### Core-Enhance-55: [Enhance] Define holistic input when subject_runs > 1

- **Title**: [Enhance] Define holistic input when subject_runs > 1
- **ID**: Core-Enhance-55
- **Priority**: P2
- **Size**: S
- **Risk**: Low
- **Area**: Core
- **Dependencies**: []
- **Goal**: `subject_runs > 1` 時に包括評価へ渡す被験出力が「全試行」か「代表応答のみ」かが Intent 上明示され、実装と一致する。
- **Acceptance Criteria**:
  - AC-001: Intent / Plan Non-Goals に holistic 入力方針（全試行 bundle / 代表のみ）が DEC として残る。
  - AC-002: 方針が「全試行」なら `server.py` の `non_creative_responses` が `subject_runs` を渡し、list-eval と入力粒度が一致する。
  - AC-003: 方針が「代表のみ」なら intentional omission として Why / Why not を Intent に残し、UI または reference で利用者に分かる。
- **Steps**:
  1. [ ] subject-multi-run Intent と holistic reference を突き合わせ方針を決める
  2. [ ] 実装またはドキュメントを方針に合わせる
  3. [ ] 必要なら engine / server テストを追加する
- **Description**:
  - Context: 標準タスクは `_build_bundled_subject_runs` で全試行を渡すが、包括は代表 `response` のみ。Plan Non-Goals は holistic bundler schema 非変更を宣言しており、現状は intentional omission の疑いが強い。未決定のままだと multi-run ON の包括評価の意味が標準と食い違う。
  - Notes: Bugbot high。コード修正前に方針確定が先。参照 `_docs/intent/Core/subject-multi-run-judge-batch/decision.md`。
- **Plan**: _docs/plan/Core/subject-multi-run-judge-batch/plan.md
- **Intent**: _docs/intent/Core/subject-multi-run-judge-batch/decision.md
- **QA**: None
- **Verification**: None

### Core-Bug-56: [Bug] Align list summary min_score with exclude hero scores

- **Title**: [Bug] Align list summary min_score with exclude hero scores
- **ID**: Core-Bug-56
- **Priority**: P2
- **Size**: XS
- **Risk**: Low
- **Area**: Core
- **Dependencies**: [Core-Bug-51]
- **Goal**: exclude-ON 結果の一覧 summary で `min_score` が除外前全 judge 再集計にならない。
- **Acceptance Criteria**:
  - AC-001: 保存 JSON に hero があるとき `min_score` も exclude 適用後のスコア集合と整合する、または null/省略方針が Intent に残る。
  - AC-002: `avg_score` / `max_score`（hero 優先）と `min_score` の意味が reference またはコードコメントで一致する。
  - AC-003: `tests/test_result_storage.py` が exclude-ON ケースを固定する。
- **Steps**:
  1. [ ] `ResultStorage._build_summary` の min 算出を hero / score_aggregation と揃える
  2. [ ] 回帰テストを追加する
- **Description**:
  - Context: `average_score` / `best_score` は保存 hero（null 可）優先だが、`min_score` は全 judge `total_score_mean` 再集計のまま。exclude-ON 一覧で min だけ除外前になる。
  - Notes: code audit medium。Dashboard N/A（Core-Bug-51）と併せて触るとよい。
- **Plan**: None
- **Intent**: _docs/intent/Core/exclude-unreliable-judges/decision.md
- **QA**: None
- **Verification**: None

### Core-Docs-57: [Docs] Tighten post-impl QA evidence for multi-feature landing

- **Title**: [Docs] Tighten post-impl QA evidence for multi-feature landing
- **ID**: Core-Docs-57
- **Priority**: P2
- **Size**: S
- **Risk**: Low
- **Area**: Core
- **Dependencies**: []
- **Goal**: 未コミットで PASS/PARTIAL とした verification / test-plan の証拠過大申告が是正され、Residual Risks と Follow-up が実測に合う。
- **Acceptance Criteria**:
  - AC-001: `subject-multi-run-judge-batch` の Risk High に対し High-risk Checklist（rollback / data safety / failure mode）が verification に記録される。
  - AC-002: `exclude-unreliable-judges` verification の Manual「PASS（unit）」過大申告を DEFERRED/unit に分け、Residual Risks / Follow-up を空にしない（または意図的に空なら理由を書く）。
  - AC-003: test-plan で `verified` と書いたが実ファイルが無い項目（例: RunPage exclude toggle node test、無関係 `test_engine.py`）を Status 修正またはテスト追加のどちらで閉じるか明記する。
  - AC-004: Intent 未記載の `unreliable_candidates` 保存意味を exclude Intent Consequences に追記する。
- **Steps**:
  1. [ ] 対象 verification / test-plan / Intent を棚卸しする
  2. [ ] 証拠のない verified 行を直し、High-risk Checklist を埋める
  3. [ ] `./scripts/check-docs.sh` 相当で破綻がないことを確認する
- **Description**:
  - Context: 実装核はおおむね Intent 整合だが、完了記録が過大（High-risk 未記録で PASS、Manual を unit 代替、存在しないテストを verified）。コード修正より証跡の健全化が主目的。
  - Notes: intent/QA alignment audit F-004〜F-009。live Manual QA 本体は既存 `Core-Test-49` を維持。
- **Plan**: None
- **Intent**: None
- **QA**: None
- **Verification**: None

### Core-Test-49: [Test] Live Manual QA for OpenAI judge api_reasoning UI

- **Title**: [Test] Live Manual QA for OpenAI judge api_reasoning UI
- **ID**: Core-Test-49
- **Priority**: P3
- **Size**: S
- **Risk**: Low
- **Area**: Core
- **Dependencies**: []
- **Goal**: Core-Feat-37 / Core-Feat-38 の ResultDetail「API thinking（モデル内部推論）」表示が、実 OpenRouter reasoning judge run（OpenAI / Claude / Gemini）で採点根拠と分離して確認できる。
- **Acceptance Criteria**:
  - AC-001: reasoning 対応 judge の実 run で `api_reasoning` が保存され、ResultDetail に API thinking 折りたたみが表示される。
  - AC-002: 同一カード内で採点根拠（`reasoningSamples`）と API thinking のラベルが混同されない。
  - AC-003: reasoning 非対応 judge では API thinking セクションが出ず、採点表示は従来どおりである。
  - AC-004: Claude（`:thinking` または opt-in）と Gemini thinking のうち少なくとも各 1 件で AC-001 相当を確認する（Core-Feat-38 follow-up）。
- **Steps**:
  1. [ ] OpenRouter reasoning judge で短い評価 run を実行する（OpenAI 系 + Claude / Gemini 各 1）
  2. [ ] ResultDetail で API thinking / 採点根拠の分離を目視確認し、verification 追記または本タスク Notes に残す
  3. [ ] 非 reasoning judge の対照 run を確認する
- **Description**:
  - Context: Core-Feat-37 verification は Verdict PARTIAL。自動テストは PASS、live Manual QA のみ deferred。
  - Notes: 参照 `_docs/qa/Core/openai-judge-thinking/verification.md`。実装変更は原則不要。
- **Plan**: None
- **Intent**: None
- **QA**: None
- **Verification**: None

---


### Core-Bug-48: [Bug] Verify LM Studio reasoning.effort payload shape

- **Title**: [Bug] Verify LM Studio reasoning.effort payload shape
- **ID**: Core-Bug-48
- **Priority**: P2
- **Size**: S
- **Risk**: Low
- **Area**: Core
- **Dependencies**: []
- **Goal**: LM Studio chat completions 被験呼び出しで、現行の nested `extra_body.reasoning.effort` がサーバに受理・反映されるか、flat `reasoning_effort` 等への正規化が必要かをライブ検証し、必要なら adapter を修正する。
- **Acceptance Criteria**:
  - AC-001: default off の代表ローカルモデルで、現行 payload（`{"reasoning": {"effort": "high"}}`）と代替（例: `{"reasoning_effort": "high"}`）の受理差が記録される。
  - AC-002: 受理される形に合わせて `LMStudioAdapter` が `extra_body` を正規化する、または現行形で十分なら調査結果を survey / Intent に残して閉じる。
  - AC-003: `tests/test_adapters.py` の LM Studio extra_body / opt-in 関連テストが更新または維持され通る。
- **Steps**:
  1. [ ] LM Studio 実機（または互換サーバ）で default off モデルに両 payload を送り、ログ / 応答差を記録する
  2. [ ] 必要なら `LMStudioAdapter.complete_with_model_result` / native tools で payload 正規化を実装する
  3. [ ] テストと `_docs/survey/Core/local-subject-effort-passthrough/survey.md` を更新する
- **Description**:
  - Context: Core-Chore-45 調査で、engine は OpenRouter 同型の nested `reasoning.effort` を LM Studio にも送ることが確定。一方 LM Studio 0.4.8 は `reasoning_effort` 追加を changelog 記載し、`/v1/responses` は nested effort を明示サポート、chat completions の公式パラメータ一覧には未列挙。live 検証なしでは nested 形の有効性が未確定。
  - Notes: Source survey `_docs/survey/Core/local-subject-effort-passthrough/survey.md` §E。opt-in 条件（default off のみ送信）自体の変更は本 Bug のスコープ外。
- **Plan**: None
- **Intent**: None
- **QA**: None
- **Verification**: None

---

## Ready

## In Progress

- (empty)

