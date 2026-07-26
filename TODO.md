# Project Task Management Rules

## 0. System Metadata

- **Current Max ID**: `Next ID No: 74` (タスク追加時にインクリメント必須)
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

### Core-Bug-73: [Bug] Multiple app instances share the results index without cross-process locking

- **Title**: [Bug] Multiple app instances share the results index without cross-process locking
- **ID**: Core-Bug-73
- **Priority**: P2
- **Size**: S
- **Risk**: High
- **Area**: Core
- **Dependencies**: [Core-Bug-71]
- **Goal**: 同一マシンでアプリを多重起動した場合でも、結果 index が破損・欠落しないようにする。または多重起動自体を防ぐ。
- **Acceptance Criteria**:
  - AC-001: 2 つのインスタンスが同時に結果を保存・削除しても index が壊れず、entry が失われない。
  - AC-002: 方針（プロセス間ロック / 単一インスタンス化）を Intent に記録する。
  - AC-003: 2 プロセスを模した regression test を追加し、再発を検出できる。
- **Steps**:
  1. [ ] プロセス間ロックと単一インスタンス化を比較検討する
  2. [ ] 方針を Intent へ記録し実装する
  3. [ ] 多重起動を模した regression test を追加する
- **Description**:
  - Context: Core-Bug-71 で導入した排他は `threading.RLock` によるプロセス内ロックであり、別プロセスからの更新は防げない（`_docs/intent/Core/result-index-integrity/decision.md` DEC-004）。`launcher.py` は空きポートを探してフォールバックするため多重起動が可能で、両インスタンスが `AppPaths.results_dir()` の同じ `index.json` を共有する。
  - Notes: DEC-004 の Revisit when に該当する。atomic write（DEC-002）により破損の窓は狭まっているが、lost update は依然起きうる。
- **Plan**: `_docs/plan/Core/cross-process-index-safety/plan.md`
- **Intent**: `_docs/intent/Core/result-index-integrity/decision.md`
- **QA**: `_docs/qa/Core/result-index-integrity/test-plan.md`
- **Verification**: None

### Core-Bug-72: [Bug] run_id collides at second resolution across concurrent jobs

- **Title**: [Bug] run_id collides at second resolution across concurrent jobs
- **ID**: Core-Bug-72
- **Priority**: P1
- **Size**: S
- **Risk**: High
- **Area**: Core
- **Dependencies**: []
- **Goal**: 同一モデルの評価を同じ秒に開始したときの `run_id` 衝突を解消し、同時実行の管理とキャンセルを run 単位で正しく分離する。
- **Acceptance Criteria**:
  - AC-001: 同一モデル・同一秒に開始した 2 本の run が異なる `run_id` を持つ。
  - AC-002: `ActiveRunRegistry.try_start` が重複 `run_id` を暗黙に成功扱いせず、同時上限の計上が正しい。
  - AC-003: 片方のキャンセルが他方へ波及しない。
  - AC-004: 同じ秒に完了した同一モデルの結果ファイルが互いを上書きしない。
  - AC-005: 同一秒・同一モデルの並行 run を対象とした regression test を追加し、再発を検出できる。
- **Steps**:
  1. [ ] `run_id` に衝突しない識別子を導入する
  2. [ ] `try_start` の重複時の扱いを見直す
  3. [ ] `_cancel_flags` と結果ファイル名の分離を確認する
  4. [ ] regression test を追加する
- **Description**:
  - Context: `server.py` の `run_id = f"{time.strftime('%Y%m%d_%H%M%S')}_{req.target_model}"` は秒精度。`ActiveRunRegistry.try_start` は `run_id in _active` のとき登録せず `True` を返すため、同時上限を素通りし、片方の `finish` が共有キーを消す。`_cancel_flags` も共有される。`ResultStorage.save` のファイル名も秒精度で衝突しうる。
  - Notes: Core-Bug-71 の調査中に発見。intent は `_docs/intent/Core/result-index-integrity/decision.md` の Rollback / Follow-ups に記載。専用 intent は着手時に作成する。
- **Plan**: `_docs/plan/Core/run-identity-collision/plan.md`
- **Intent**: `_docs/intent/Core/result-index-integrity/decision.md`
- **QA**: `_docs/qa/Core/result-index-integrity/test-plan.md`
- **Verification**: None

### DevOps-Test-69: [Test] Verify first Code CI run on GitHub

- **Title**: [Test] Verify first Code CI run on GitHub
- **ID**: DevOps-Test-69
- **Priority**: P1
- **Size**: XS
- **Risk**: High
- **Area**: DevOps
- **Dependencies**: []
- **Goal**: 新設した `Code CI` workflow が GitHub 上で実際に発火し、backend matrix と frontend job が緑になることを確認する。
- **Acceptance Criteria**:
  - AC-001: push で `Code CI` が起動し、backend（3.12 / 3.14）と frontend の全 job が成功する。
  - AC-002: 意図的に失敗させたコミットで job が赤くなり、gate として機能することを確認する。
  - AC-003: backend の 2 leg のログが実際に異なる Python 版を報告する。緑であることだけを根拠にしない。
- **Steps**:
  1. [ ] push 後に Actions の run を確認する
  2. [ ] 失敗ケースで gate が赤くなることを確認する
  3. [ ] verification の AC-004 を PASS へ更新する
- **Description**:
  - Context: DevOps code-ci-gate verification PARTIAL の deferred 項目。ローカルでは全 gate コマンドが exit 0 だが、workflow 自体は未実行である。
  - Notes: `_docs/qa/DevOps/code-ci-gate/verification.md`
- **Plan**: `_docs/plan/DevOps/code-ci-gate/plan.md`
- **Intent**: `_docs/intent/DevOps/code-ci-gate/decision.md`
- **QA**: `_docs/qa/DevOps/code-ci-gate/test-plan.md`
- **Verification**: `_docs/qa/DevOps/code-ci-gate/verification.md`

### DevOps-Chore-70: [Chore] Audit frontend toolchain versions and dev dependency advisories

- **Title**: [Chore] Audit frontend toolchain versions and dev dependency advisories
- **ID**: DevOps-Chore-70
- **Priority**: P2
- **Size**: S
- **Risk**: High
- **Area**: DevOps
- **Dependencies**: []
- **Goal**: Node のローカル版と CI / release 版の差の扱いを決め、`npm audit` が報告する dev 依存の既知脆弱性を棚卸しする。
- **Acceptance Criteria**:
  - AC-001: Node のバージョン方針を決定する（matrix 化、または出荷版へ統一）。決定理由を残す。
  - AC-002: `npm audit` の 10 件について、対応するか受容するかを判断し、受容分は理由を残す。
  - AC-003: 対応後も `npm run lint / test / build --prefix frontend` が緑である。
- **Steps**:
  1. [ ] ローカル（24）と CI / release（22）の差分影響を確認する
  2. [ ] `npm audit` の各件を出荷影響の有無で分類する
  3. [ ] 方針を決めて workflow または依存を更新する
- **Description**:
  - Context: DevOps code-ci-gate verification の residual risks。脆弱性はいずれも vite・eslint 配下の既存 dev 依存で、ビルド成果物には載らない。
  - Notes: 依存を上げるとビルドが壊れうるため、gate が緑であることを確認しながら進める。
- **Plan**: `_docs/plan/DevOps/code-ci-gate/plan.md`
- **Intent**: `_docs/intent/DevOps/code-ci-gate/decision.md`
- **QA**: `_docs/qa/DevOps/code-ci-gate/test-plan.md`
- **Verification**: None

### Core-Test-68: [Test] OpenRouter preferred host Manual QA

- **Title**: [Test] OpenRouter preferred host Manual QA
- **ID**: Core-Test-68
- **Priority**: P3
- **Size**: S
- **Risk**: Medium
- **Area**: Core
- **Dependencies**: []
- **Goal**: Settings のホストピッカー（enabled/disabled・チップ切替・プリセット）と優先ホスト付き短 run を実 OpenRouter で確認する。
- **Acceptance Criteria**:
  - AC-001: endpoints ≥ 2 でホストピッカーが enabled、1 以下で disabled（枠は残る）。
  - AC-002: judge チップ切替で共有ピッカーの編集対象が変わり、プリセット保存・読込で preferredHosts が戻る。
  - AC-003: 優先ホスト指定の短 run が完走する（または失敗時に unrestricted フォールバックが観測できる）。
- **Steps**:
  1. [ ] Settings で複数ホストモデルを選び UI を確認する
  2. [ ] プリセット往復を確認する
  3. [ ] 短 run を実行する
- **Description**:
  - Context: Core-Feat-67 verification PARTIAL の deferred Manual QA。
  - Notes: `_docs/qa/Core/openrouter-preferred-host/verification.md`
- **Plan**: None
- **Intent**: `_docs/intent/Core/openrouter-preferred-host/decision.md`
- **QA**: `_docs/qa/Core/openrouter-preferred-host/test-plan.md`
- **Verification**: `_docs/qa/Core/openrouter-preferred-host/verification.md`

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

### UI-Feat-61: [Feat] Run presence observation on active evaluation cards

- **Title**: [Feat] Run presence observation on active evaluation cards
- **ID**: UI-Feat-61
- **Priority**: P2
- **Size**: M
- **Risk**: Medium
- **Area**: UI
- **Dependencies**: []
- **Goal**: 実行中の active 評価まわりに、緊張（滞留）と変化の向き（直近差分）の二チャンネル観察層を置き、異常時だけ数値で割込み、途中点や raw ログなしで待ちの観察体験を成立させる。
- **Acceptance Criteria**:
  - AC-001: active な評価カードに緊張ステージが滞留時間に応じて変わり、score-low 色相や opacity 点滅の高速化へ寄せて点の良し悪し／障害を暗示しない。
  - AC-002: 採点確定の拍で rising / falling / unsettled のいずれかが専用 motif 上に短く表現され、具体点・暫定平均・絶対帯ラベルは出ない。カード全体は平行移動しない。
  - AC-003: 実行失敗と、settled における 0 点過半（または Intent で許した同等閾値）のときだけ数値付きの率直表示が出る。
  - AC-004: subject フェーズでは変化の向きが発動せず緊張のみである。
  - AC-005: `prefers-reduced-motion` で連続アニメに依存せず、静的な密度／向き表示へ落ちる。
  - AC-006: 既存の進行ボード lane 集計、ETA、包括評価 dedicated 表示を壊さない。
- **Steps**:
  1. [ ] progress SSE に内部用採点シグナルと緊張用開始時刻を additive で載せる
  2. [ ] 緊張 / 向き / 異常の helper を実装し、生スコアを表示経路から隔離する
  3. [ ] ActiveTaskCard に inset/segment 緊張・専用 motif 拍・異常割込みを接続し、CSS 変数 transition / motion / reduced-motion を追加する
  4. [ ] helper / store / snapshot テストと Manual QA を実施し verification を残す
- **Description**:
  - Context: 進行ボードは状態一覧として機能するが API 待ちが静止する。観察目的の presence を局所に置く。楽しさは質であり暇つぶし目的化しない。
  - Notes: Plan の Expression Technique（自己レビュー反映）と Intent DEC-001..005。緊張はばね圧縮、向きは専用 motif、点滅高速化とカード translate は禁止。
- **Plan**: `_docs/plan/UI/run-presence-observation/plan.md`
- **Intent**: `_docs/intent/UI/run-presence-observation/decision.md`
- **QA**: `_docs/qa/UI/run-presence-observation/test-plan.md`
- **Verification**: None

## In Progress

### Core-Bug-71: [Bug] Result index lost update and non-atomic write

- **Title**: [Bug] Result index lost update and non-atomic write
- **ID**: Core-Bug-71
- **Priority**: P0
- **Size**: M
- **Risk**: High
- **Area**: Core
- **Dependencies**: []
- **Goal**: `index.json` の read-modify-write 競合と非アトミック書き込みを解消し、index を書く経路を `ResultStorage` へ集約する。
- **Acceptance Criteria**:
  - AC-001: `save` と `delete` の並行実行で保存済み結果が index から失われない。
  - AC-002: 並行実行下でも `index.json` が常に完全な JSON として解析できる。
  - AC-003: 削除した結果の entry が index に残らない。
  - AC-004: バックフィル移送前後で既存 index に対する一覧出力が同値である。
  - AC-005: `server.py` から `ResultStorage` の private 参照が無くなる。
  - AC-006: 既存 backend テストが緑のままである。
  - AC-007: 並行 save / delete を対象とした regression test を追加し、修正前コードで落ちることを確認して再発を検出できる。
- **Steps**:
  1. [x] index 更新経路をロックで直列化する
  2. [x] `_save_index` を一時ファイル + `os.replace` にする
  3. [x] バックフィルを `list_summaries()` へ移送する
  4. [x] 並行テストを追加し verification を残す
- **Description**:
  - Context: `POST /api/run` は async で event loop thread、`GET`/`DELETE /api/results` は同期のため threadpool thread。両者が排他なしで index を read-modify-write する。barrier で競合を強制した 20 試行で 20 件すべて不整合（破損 11 / stale entry 8 / 消失 1）。
  - Notes: index が非空のまま entry を失うと再構築が走らず、その run は履歴から恒久的に消える。結果 JSON 本体は残るためデータ損失ではなく可視性の損失。
- **Plan**: `_docs/plan/Core/result-index-integrity/plan.md`
- **Intent**: `_docs/intent/Core/result-index-integrity/decision.md`
- **QA**: `_docs/qa/Core/result-index-integrity/test-plan.md`
- **Verification**: `_docs/qa/Core/result-index-integrity/verification.md`

### Core-Feat-66: [Feat] Concurrent evaluation jobs with provider rate limits

- **Title**: [Feat] Concurrent evaluation jobs with provider rate limits
- **ID**: Core-Feat-66
- **Priority**: P1
- **Size**: L
- **Risk**: High
- **Area**: Core
- **Dependencies**: []
- **Goal**: 設定違いの評価ジョブを最大 3 本まで同時実行でき、Run 画面では進行ボード一式をジョブとして縦積みし、プロバイダ別レート制限（Settings 編集可・推奨デフォルト内蔵）で発行を抑える。
- **Acceptance Criteria**:
  - AC-001: 最大 3 本まで設定違いの評価を同時起動でき、4 本目はサーバが拒否する。
  - AC-002: Run 画面で各ジョブが進行ボード一式として縦積み表示され、個別キャンセルできる。
  - AC-003: 全ジョブの LLM 呼び出しがプロバイダ別レート制限を共有し、窓内上限を超えて発行しない。
  - AC-004: Settings でプロバイダごとに制限を編集・保存でき、未設定時は推奨デフォルトが効く。
  - AC-005: ジョブ 1 本のみのとき、進行ボード体験は現行と同等である。
  - AC-006: active run 中に Settings 等の内部 route へ移動しても run / SSE が中断されず、Run 画面へ戻ると継続した進捗を確認できる。
- **Steps**:
  1. [x] Plan / Intent / QA を確認する
  2. [x] 共有 ProviderRateLimiter と設定ストア / API を実装する
  3. [x] active run registry（上限 3）を `/run` に接続する
  4. [x] multi-job store とジョブ縦積み UI、Settings 編集 UI を実装する
  5. [x] Test Matrix に従い検証し verification を残す（Verdict PARTIAL: Manual QA deferred）
  6. [x] run / SSE の所有を route-local component から app shell lifecycle へ移す
  7. [ ] route 往復の回帰テストと Manual QA を実行し verification を更新する
- **Description**:
  - Context: 単一 runStore 前提をやめ、同時比較用に 2〜3 ジョブ並列が欲しい。同時起動時の stampede を避けるため初版からプロバイダ単位の共有レート制限を入れる。設定違いの二本目を構成する通常導線で RunPage が unmount され、route-local cleanup が先行 SSE を abort する回帰が 2026-07-26 に確認された。
  - Notes: UI-Feat-61（presence）と進行ボード表面を共有する。presence はジョブ内カード局所のまま共存。2026-07-26 に app-shell coordinator へ SSE 所有を移し、node 回帰は PASS。verification PARTIAL — Browser の route 往復確認と、実 API 複数ジョブ Manual QA が未完了。
- **Plan**: `_docs/plan/Core/concurrent-evaluation-jobs/plan.md`
- **Intent**: `_docs/intent/Core/concurrent-evaluation-jobs/decision.md`
- **QA**: `_docs/qa/Core/concurrent-evaluation-jobs/test-plan.md`
- **Verification**: `_docs/qa/Core/concurrent-evaluation-jobs/verification.md`
