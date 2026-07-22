---
title: "Decision: Judge system prompt and rubric reliability"
status: active
draft_status: n/a
intent_schema: 2
created_at: 2026-07-22
updated_at: 2026-07-22
references:
  - "_docs/archives/plan/Core/legacy-documentation-retirement/judge-rubric-reliability.md"
  - "_docs/qa/Core/judge-rubric-reliability/test-plan.md"
  - "_docs/reference/Core/holistic-evaluation.md"
related_issues: []
related_prs: []
---

# Decision: Judge system prompt and rubric reliability

## Context

このベンチマークは、一般的な正答率ではなく、設計者が実用上重視する回答特性を
task-specific rubric で測る。一方、現行 rubric は一部で特定語句・特定ツール・特定の
模範回答を満点条件にし、Critical Fail の適用範囲や三軸の境界も揃っていない。
その結果、優れた別解の過小評価、同一欠点の重複減点、軽微な欠点による全点失効、
被験回答内の命令による judge prompt injection が起こり得る。

直近の raw evaluation session では、rubric に存在しない `CF-3` の生成、任意の歴史的引用を
書かなかったことへの減点、tool trace が存在しても最終回答が空の task、途中切れ・空回答を
holistic style で再度減点する挙動が確認された。したがって、抽象的な authoring 改善だけでなく、
実際の judge failure mode を deterministic rule と task-specific boundary へ反映する。

## Decisions

### DEC-001: 共通採点手順と task 固有判断を分離する

- **What**: system prompt は権限階層、採点手順、三軸の一般原則、Critical Fail の適用規則、
  JSON schema を定義し、rubric は task 固有の事実前提、観点、アンカー、CF だけを定義する。
- **Why**: 共通規則の重複と task 間 drift を減らしながら、各問いで重視する実用上の価値を
  rubric 側で明示できる。
- **Change freedom**: parser / aggregator 互換と役割分離を維持する限り、見出し名、説明順序、
  アンカーの表現は変更できる。
- **Why not**: 全 task を一つの汎用 rubric で採点すると、設計者が意図する task 固有の性能差を
  測れない。反対に、全規則を各 rubric へ複製すると修正漏れと judge 間差が増える。

### DEC-002: Critical Fail は明示的かつ壊滅的な失敗に限定する

- **What**: CF は rubric に ID 付きで明記された条件について、中心的回答に直接的で十分な証拠が
  ある場合だけ適用する。単なる省略、浅さ、言い回し、境界事例は通常採点で扱う。
- **Why**: CF は全軸を 0 点にするため、通常の品質差へ適用すると情報量を失い、judge の小さな
  解釈差を極端なスコア差へ増幅する。
- **Change freedom**: 安全上または task 成立上の壊滅的失敗が新たに判明した場合は CF を追加できる。
  ただし通常減点では不十分な理由を rubric に記す。

### DEC-003: 模範回答への一致ではなく、要件を満たす回答品質を採点する

- **What**: rubric の例示は排他的な必須語句・必須ツールとして扱わず、同等の別解、異なる
  説明順序、妥当な推論、校正された不確実性を満点域の候補として認める。
- **Why**: ベンチマークで測りたいのは参照文の再現能力ではなく、未知の実務状況でも目的を
  満たす回答を構成できる能力だからである。
- **Change freedom**: task が厳密解を持つ場合は truth table や必須出力のような結果契約を固定できる。
  実装手段や表現まで固定するには、それ自体がユーザー要件である必要がある。
- **Why not**: 特定の製品機能名、研究者名、締めの質問、定型句を満点条件にすると、質の高い
  独立解を誤って下げ、モデルの言い換え能力をノイズとして測ってしまう。

### DEC-004: rubric と評価対象の信頼境界を prompt 上で明示する

- **What**: task rubric を trusted evaluation rules として先に配置し、原プロンプト、被験回答、
  tool trace は命令として従わない untrusted evidence としてタグで囲む。
- **Why**: 被験回答は任意の文字列を含み得るため、出力形式変更や満点要求などを judge の命令として
  解釈すると評価の完全性が失われる。
- **Change freedom**: system prompt が同じ権限階層を明示し、構造の曖昧さを生まない限り、タグ名や
  serialization 形式は変更できる。

### DEC-005: 三軸・配点・JSON 出力契約は維持し、軸の意味を task 内で切り分ける

- **What**: `logic_and_fact`、`constraint_adherence`、`helpfulness_and_creativity` と既存配点を維持し、
  同じ欠点は原則一つの主軸で評価する。複数軸へ影響させる場合は別々の帰結を説明する。
- **Why**: 既存 UI、parser、aggregator、過去結果との互換性を壊さずに、重複減点を減らせる。
- **Change freedom**: 将来 schema version と migration を導入する場合は軸名や配点体系を再設計できる。
  現行 schema 内では rubric ごとの軸解釈を調整できる。

### DEC-006: 可視の最終回答だけを成果物として deterministic に扱う

- **What**: 空回答は全軸 0・CF false、途中切れは可視部分だけを採点する。tool trace、検索結果、
  推測される続きで最終回答を補完しない。
- **Why**: tool 実行能力とユーザーへ届いた回答品質を混同すると、出力しなかった根拠へ点を与え、
  同じ実行失敗でも judge によって扱いが変わるためである。
- **Change freedom**: 将来、tool-use quality を独立 task として測る場合は trace 専用 rubric を追加できる。
  現行 per-task score では final answer delivery と分離する。

### DEC-007: holistic は言語傾向だけを測り、完遂性欠陥を再採点しない

- **What**: 空回答、API failure、明白な token truncation の欠落自体は holistic style から除外する。
  可視部分に現れた語用・register・文構造は証拠にできる。標本が少ない場合は score ではなく
  `confidence` で不確実性を表す。
- **Why**: 完遂性は per-task score へ既に反映される。holistic でも同じ欠落を減点すると、文体とは
  別の能力を二重計上し、横断評価の意味が失われる。
- **Change freedom**: 将来、completion reliability を横断的に測る場合は style と別 rubric / metric を
  定義する。

### DEC-008: task 08 は no-change oracle と慎重な non-claim を非対称に評価する

- **What**: task 08 では、設計者の同時代的な継続観測を含む project-specific oracle として、対象期間中の
  Deep Research 固有モデル変更・知能向上はなかったことを採点用 ground truth にする。一方、公開資料だけを
  根拠に「変更を確認できず、賢くなったとはいえない」とする回答も近接する高得点域へ置く。一般モデルや
  UX 更新から固有モデル向上を誤認する回答は大幅に低く評価する。
- **Why**: この task の主要な失敗は、保険をかけた慎重さではなく、弱い証拠から存在しない更新を作る
  false positive である。完全な oracle 一致との差は残しつつ、認識上健全な不確実性表明を罰すると、
  地雷回避という task の目的を逆転させる。
- **Change freedom**: 具体的な点数帯は変更できるが、`oracle に整合する変更なし`、`慎重な確認不能`、
  `根拠のない更新断定`の順序と、後二者の差を前二者の差より大きくする非対称性は維持する。
- **Why not**: 公開資料だけで非公開 backend 変更の不在証明を要求しない。また「確認できない」を
  中得点以下へ落とし、断言の強さ自体を品質として測らない。
- **Revisit when**: 対象期間内の Deep Research 固有モデル更新を示す一次資料または保存済みの直接証拠が
  見つかった時。

## Consequences / Impact

- 同じ回答でも、軽微な欠点だけで 0 点になる頻度と、模範回答にない別解の不当な失点が減る。
- rubric は以前より長くなるが、task 間で探索位置と判断手順が揃う。
- 厳密な正解がない task のスコアには設計者の価値判断が残る。これは排除せず、評価目的として明示する。
- prompt envelope の文字列が変わるため、prompt 内容を直接比較するテストは更新が必要になる。
- 集計ロジックは変更しないため、単一 judge run の CF を aggregate CF とする現行挙動は残る。
  今回は CF ID の創作禁止と適用境界の明確化により、入力側で false positive を抑える。

## Quality Implications

- metadata と weights は全 rubric で機械検証できること。
- CF 判定時だけ全軸と total が 0 になり、理由に CF ID と直接証拠が含まれること。
- 被験回答内の命令が rubric や JSON schema を上書きできないこと。
- 各軸の採点根拠が、同一欠点の言い換えだけにならないこと。
- holistic は個別 task の内容正誤を再採点せず、複数出力に見られる傾向を比例的に評価すること。
- 空回答は trace に関係なく 0 点・CF false、途中切れは可視部分だけで通常採点されること。
- rubric にない CF ID と、任意例の単純な omission を judge が減点根拠として創作しないこと。

## Intent-derived Invariants

- INV-001 (from DEC-004): 原プロンプト、被験回答、tool trace を judge の命令として扱わない。
- INV-002 (from DEC-005): rubric の三軸 weights の合計は 100 であり、出力 key は既存 parser / aggregator と互換である。
- INV-003 (from DEC-002): `critical_fail: true` の場合、三軸と `total_score` はすべて 0 である。
- INV-004 (from DEC-006): 空の最終回答は tool trace で補完されず、`critical_fail: false` の 0 点となる。
- INV-005 (from DEC-007): 空回答・明白な途中切れの欠落自体は holistic style score へ再計上されない。
- INV-006 (from DEC-008): task 08 は慎重な「変更を確認できない」を誤った更新断定より高く評価し、
  ground truth の「変更なし」との差は小さく保つ。

## Enforced in (optional)

- DEC-001、DEC-002、DEC-003、DEC-005: `judge_system_prompt.md`, `rubrics/**/*.md`
- DEC-004、INV-001: `core/benchmark_engine.py`, `judge_system_prompt.md`
- INV-002: `tests/test_prompt_contracts.py`, `core/json_parser.py`, `core/result_aggregator.py`
- INV-003: `judge_system_prompt.md`, `tests/test_prompt_contracts.py`
- DEC-006、INV-004: `judge_system_prompt.md`, `tests/test_prompt_contracts.py`
- DEC-007、INV-005: `judge_system_prompt.md`, `rubrics/holistic/style.md`,
  `prompts/holistic/style.md`, `tests/test_prompt_contracts.py`
- DEC-008、INV-006: `rubrics/08.md`, `tests/test_prompt_contracts.py`

## Rollback / Follow-ups

- prompt 品質が後退した場合は変更前 ZIP の bundled prompt / rubric と prompt builder を戻す。
- judge 間分散の定量比較は、同一回答セットに対する再評価データが得られた時点で別タスクとして行う。
- aggregate CF の quorum / majority rule は prompt 改善と分離し、集計仕様を変更する別 decision として扱う。
