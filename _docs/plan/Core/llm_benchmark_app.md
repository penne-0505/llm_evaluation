# LLMベンチマークアプリ開発計画

## 1. 計画概要

### 1.1 目的
タスク固有のルーブリックに基づいてLLMを自動評価するStreamlitアプリケーションを開発する。

### 1.2 参照ドキュメント
- 要件定義書: `_docs/draft/requirements.md`
- judgeシステムプロンプト: `_docs/draft/judge_sys_instruction.md`
- タスクルーブリック: `_docs/draft/rubrics_draft/01.md`〜`11.md`
- タスクプロンプト: `_docs/draft/prompts_for_subject_model/01.md`〜`11.md`

### 1.3 スコープ
- **内包**: Streamlit UI、アダプタ層、評価実行エンジン、結果表示・保存機能
- **除外**: タスクルーブリックの作成（既に完成済み）

---

## 2. アーキテクチャ設計

### 2.1 ディレクトリ構成

```
project-root/
├── app.py                      # Streamlitエントリポイント
├── .env                        # APIキー（gitignore対象）
├── .env.example                # APIキーのテンプレート
├── pyproject.toml              # 依存関係管理
├── rubrics/                    # タスク固有ルーブリック（Markdownファイル）
│   ├── 01.md                   # ドラフトからコピー
│   ├── 02.md
│   └── ... (11ファイル)
├── prompts/                    # 被験LLMに渡す入力プロンプト
│   ├── 01.txt                  # ドラフトからコピー
│   ├── 02.txt
│   └── ... (11ファイル)
├── judge_system_prompt.md      # judgeのシステムプロンプト（ドラフトからコピー）
├── adapters/                   # プロバイダーごとのAPIアダプタ
│   ├── __init__.py
│   ├── base.py                 # 抽象基底クラス
│   ├── openai_adapter.py
│   ├── anthropic_adapter.py
│   └── gemini_adapter.py
├── core/                       # ビジネスロジック
│   ├── __init__.py
│   ├── benchmark_engine.py     # 評価実行エンジン
│   ├── result_aggregator.py    # 結果集計ロジック
│   └── json_parser.py          # judgeレスポンスパーサー
├── ui/                         # UIコンポーネント
│   ├── __init__.py
│   ├── components.py           # 再利用可能なコンポーネント
│   └── pages.py                # ページ定義
├── results/                    # 実行結果のJSONログ（自動生成・.gitignore対象）
│   └── YYYYMMDD_HHMMSS_<model_name>.json
└── tests/                      # テスト
    ├── __init__.py
    ├── test_adapters.py
    └── test_engine.py
```

### 2.2 データフロー

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface                           │
│  (Streamlit - 設定パネル/実行ボタン/結果表示)                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Benchmark Engine                            │
│  1. 被験LLM呼び出し → 回答取得                                   │
│  2. judge呼び出し × n回 → 評価取得                              │
│  3. 結果集計 → UI反映                                            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
┌───────────────────────────────┐   ┌───────────────────────────────┐
│       LLM Adapters            │   │       File I/O                │
│  - OpenAIAdapter              │   │  - 結果JSON保存               │
│  - AnthropicAdapter           │   │  - 過去結果読み込み           │
│  - GeminiAdapter              │   │  - ルーブリック/プロンプト読込 │
└───────────────────────────────┘   └───────────────────────────────┘
```

---

## 3. 実装仕様

### 3.1 アダプタ層 (`adapters/`)

#### 3.1.1 基底クラス (`base.py`)

```python
from abc import ABC, abstractmethod
from typing import Optional

class LLMAdapter(ABC):
    """LLMプロバイダー用抽象基底クラス"""
    
    @abstractmethod
    def complete(
        self, 
        system_prompt: str, 
        user_prompt: str,
        temperature: float = 0.0, 
        max_tokens: int = 1024
    ) -> str:
        """
        テキスト生成を実行する
        
        Args:
            system_prompt: システムプロンプト
            user_prompt: ユーザープロンプト
            temperature: 温度パラメータ
            max_tokens: 最大トークン数
            
        Returns:
            生成されたテキスト
            
        Raises:
            LLMError: API呼び出し失敗時
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """APIキーが設定されているか確認"""
        pass

class LLMError(Exception):
    """LLM呼び出しエラー"""
    pass
```

#### 3.1.2 プロバイダー判定ロジック

```python
def get_adapter_for_model(model_name: str) -> Optional[LLMAdapter]:
    """
    モデル名から適切なアダプタを返す
    
    判定ルール:
    - gpt-*, o1*, o3*, o4* → OpenAIAdapter
    - claude-* → AnthropicAdapter  
    - gemini-* → GeminiAdapter
    """
    model_lower = model_name.lower()
    
    if any(model_lower.startswith(p) for p in ['gpt-', 'o1', 'o3', 'o4']):
        return OpenAIAdapter()
    elif model_lower.startswith('claude-'):
        return AnthropicAdapter()
    elif model_lower.startswith('gemini-'):
        return GeminiAdapter()
    
    return None
```

### 3.2 評価エンジン (`core/benchmark_engine.py`)

#### 3.2.1 主要クラス

```python
class BenchmarkEngine:
    """
    LLMベンチマーク実行エンジン
    
    実行フロー:
    1. 被験LLMにタスクプロンプトを送信 → 回答取得
    2. 各judge系統（OpenAI/Anthropic/Gemini）でn回評価実行
    3. 結果を集計して返却
    """
    
    def __init__(
        self,
        subject_adapter: LLMAdapter,
        judge_adapters: Dict[str, LLMAdapter],
        judge_runs: int = 3
    ):
        self.subject_adapter = subject_adapter
        self.judge_adapters = judge_adapters  # {"openai": adapter, ...}
        self.judge_runs = judge_runs
    
    async def run_task(
        self, 
        task_name: str,
        input_prompt: str,
        rubric_content: str,
        system_prompt: str,
        progress_callback: Optional[Callable] = None
    ) -> TaskResult:
        """
        単一タスクの評価を実行
        
        Returns:
            TaskResult: タスク実行結果
        """
        # 1. 被験LLM呼び出し
        subject_response = await self._call_subject_llm(input_prompt)
        
        # 2. 各judgeで評価
        judge_results = {}
        for family, adapter in self.judge_adapters.items():
            if adapter.is_available():
                results = await self._run_judge_evaluation(
                    adapter=adapter,
                    subject_response=subject_response,
                    input_prompt=input_prompt,
                    rubric_content=rubric_content,
                    system_prompt=system_prompt,
                    progress_callback=progress_callback
                )
                judge_results[family] = results
        
        return TaskResult(
            task_name=task_name,
            input_prompt=input_prompt,
            response=subject_response,
            judge_results=judge_results
        )
```

#### 3.2.2 Judge評価実行

```python
async def _run_judge_evaluation(
    self,
    adapter: LLMAdapter,
    subject_response: str,
    input_prompt: str,
    rubric_content: str,
    system_prompt: str,
    progress_callback: Optional[Callable] = None
) -> JudgeResult:
    """
    単一judgeでの複数回評価実行
    """
    runs = []
    
    for i in range(self.judge_runs):
        # プロンプト組み立て
        user_prompt = self._build_judge_user_prompt(
            input_prompt=input_prompt,
            subject_response=subject_response,
            rubric_content=rubric_content
        )
        
        try:
            # judge呼び出し（リトライ1回）
            response = await self._call_judge_with_retry(
                adapter=adapter,
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            # JSONパース
            parsed = self._parse_judge_response(response)
            runs.append(parsed)
            
        except Exception as e:
            # パース失敗時はスキップ
            runs.append({"error": str(e), "skipped": True})
        
        if progress_callback:
            progress_callback(f"judge: {adapter.__class__.__name__} {i+1}/{self.judge_runs}")
    
    # 集計
    return self._aggregate_judge_runs(runs)
```

### 3.3 Judgeプロンプト組み立て

```python
def _build_judge_user_prompt(
    self,
    input_prompt: str,
    subject_response: str,
    rubric_content: str
) -> str:
    """
    judgeへのユーザープロンプトを構築
    
    ルーブリックはuser_promptに含め、system_promptのキャッシュ効率を高める
    """
    return f"""## 入力プロンプト（被験LLMに渡したもの）
{input_prompt}

## 被験LLMの回答
{subject_response}

## タスク固有ルーブリック
{rubric_content}
"""
```

### 3.4 JSONレスポンスパーサー (`core/json_parser.py`)

```python
class JudgeResponseParser:
    """
    judgeからのJSONレスポンスをパースする
    
    期待されるスキーマ:
    {
        "task_name": str,
        "task_type": "fact" | "creative" | "speculative",
        "inferred_task_type": str | null,
        "weights": {...},
        "score": {...},
        "total_score": int,
        "reasoning": {...},
        "critical_fail": bool,
        "critical_fail_reason": str | null,
        "confidence": "high" | "medium" | "low"
    }
    """
    
    @staticmethod
    def parse(response: str) -> Dict[str, Any]:
        """
        JSONレスポンスをパース
        
        - Markdownコードブロックを除去
        - 必須フィールドの検証
        - 型変換
        """
        # Markdownコードブロックの除去
        cleaned = re.sub(r'```json\n?', '', response)
        cleaned = re.sub(r'\n?```', '', cleaned)
        
        # JSONパース
        data = json.loads(cleaned)
        
        # 必須フィールド検証
        required = ['task_name', 'task_type', 'score', 'total_score']
        for field in required:
            if field not in data:
                raise ParseError(f"Missing required field: {field}")
        
        return data
```

### 3.5 結果集計 (`core/result_aggregator.py`)

```python
class ResultAggregator:
    """
    複数回のjudge評価結果を集計する
    """
    
    @staticmethod
    def aggregate(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        n回分の評価結果を集計
        
        Returns:
            {
                "runs": [...],  # 個別結果
                "aggregated": {
                    "logic_and_fact_mean": float,
                    "logic_and_fact_std": float,
                    "constraint_adherence_mean": float,
                    "constraint_adherence_std": float,
                    "helpfulness_mean": float,
                    "helpfulness_std": float,
                    "total_score_mean": float,
                    "total_score_std": float,
                    "critical_fail": bool,
                    "confidence_distribution": {"high": n, "medium": n, "low": n}
                }
            }
        """
        valid_runs = [r for r in runs if not r.get("skipped")]
        
        if not valid_runs:
            return {"runs": runs, "aggregated": None}
        
        # 各スコアの平均・標準偏差を計算
        scores = {
            "logic_and_fact": [],
            "constraint_adherence": [],
            "helpfulness": [],
            "total_score": []
        }
        
        confidences = {"high": 0, "medium": 0, "low": 0}
        critical_fails = 0
        
        for run in valid_runs:
            scores["logic_and_fact"].append(run["score"]["logic_and_fact"])
            scores["constraint_adherence"].append(run["score"]["constraint_adherence"])
            scores["helpfulness"].append(run["score"]["helpfulness_and_creativity"])
            scores["total_score"].append(run["total_score"])
            
            confidences[run.get("confidence", "low")] += 1
            
            if run.get("critical_fail", False):
                critical_fails += 1
        
        return {
            "runs": runs,
            "aggregated": {
                "logic_and_fact_mean": statistics.mean(scores["logic_and_fact"]),
                "logic_and_fact_std": statistics.stdev(scores["logic_and_fact"]) if len(scores["logic_and_fact"]) > 1 else 0.0,
                "constraint_adherence_mean": statistics.mean(scores["constraint_adherence"]),
                "constraint_adherence_std": statistics.stdev(scores["constraint_adherence"]) if len(scores["constraint_adherence"]) > 1 else 0.0,
                "helpfulness_mean": statistics.mean(scores["helpfulness"]),
                "helpfulness_std": statistics.stdev(scores["helpfulness"]) if len(scores["helpfulness"]) > 1 else 0.0,
                "total_score_mean": statistics.mean(scores["total_score"]),
                "total_score_std": statistics.stdev(scores["total_score"]) if len(scores["total_score"]) > 1 else 0.0,
                "critical_fail": critical_fails > 0,
                "confidence_distribution": confidences
            }
        }
```

### 3.6 Streamlit UI (`app.py` + `ui/`)

#### 3.6.1 サイドバー設定パネル

```python
# app.py
import streamlit as st

def render_sidebar():
    """サイドバーの設定パネルをレンダリング"""
    st.sidebar.header("実行設定")
    
    # 評価対象モデル
    target_model = st.sidebar.text_input(
        "評価対象モデル",
        value="gpt-4o",
        help="例: gpt-4o, claude-sonnet-4-5-20250929, gemini-1.5-pro"
    )
    
    # タスク選択
    st.sidebar.subheader("タスク選択")
    all_tasks = load_task_list()  # 11個のタスクを読み込み
    
    if st.sidebar.button("全選択"):
        st.session_state.selected_tasks = all_tasks
    
    selected_tasks = st.sidebar.multiselect(
        "評価するタスク",
        options=all_tasks,
        default=st.session_state.get("selected_tasks", [])
    )
    
    # judge実行回数
    judge_runs = st.sidebar.slider(
        "judge実行回数",
        min_value=1,
        max_value=5,
        value=3,
        help="各judge系統ごとの評価回数"
    )
    
    # temperature設定
    subject_temp = st.sidebar.slider(
        "Temperature（被験LLM）",
        min_value=0.0,
        max_value=1.0,
        value=1.0,
        step=0.1
    )
    
    st.sidebar.text("Temperature（judge）: 0.0（固定）")
    
    return {
        "target_model": target_model,
        "selected_tasks": selected_tasks,
        "judge_runs": judge_runs,
        "subject_temp": subject_temp
    }
```

#### 3.6.2 結果表示コンポーネント

```python
def render_task_result_card(task_result: TaskResult):
    """
    タスク別結果カードを表示
    
    - judge系統ごとのタブ（OpenAI/Anthropic/Gemini）
    - 被験LLM回答原文（タブ外）
    - 各タブ: スコア、confidence分布、reasoning（アコーディオン）
    """
    with st.container():
        st.subheader(task_result.task_name)
        
        # task_typeバッジ
        task_type = get_task_type(task_result.task_name)
        badge_color = {"fact": "blue", "creative": "green", "speculative": "orange"}[task_type]
        st.badge(task_type.upper(), color=badge_color)
        
        # 被験LLM回答（タブ外）
        with st.expander("被験LLMの回答原文"):
            st.markdown(task_result.response)
        
        # judge系統ごとのタブ
        tabs = st.tabs(["OpenAI", "Anthropic", "Gemini"])
        
        for tab, (family, result) in zip(tabs, task_result.judge_results.items()):
            with tab:
                render_judge_family_result(result)

def render_judge_family_result(result: JudgeResult):
    """単一judge系統の結果を表示"""
    if result.aggregated is None:
        st.warning("評価結果がありません")
        return
    
    agg = result.aggregated
    
    # Critical Fail警告
    if agg["critical_fail"]:
        st.error("⚠️ Critical Failが検出されました")
    
    # スコア表示（平均±標準偏差）
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Logic & Fact",
            f"{agg['logic_and_fact_mean']:.1f}±{agg['logic_and_fact_std']:.1f}"
        )
    with col2:
        st.metric(
            "Constraint Adherence",
            f"{agg['constraint_adherence_mean']:.1f}±{agg['constraint_adherence_std']:.1f}"
        )
    with col3:
        st.metric(
            "Helpfulness",
            f"{agg['helpfulness_mean']:.1f}±{agg['helpfulness_std']:.1f}"
        )
    
    # Total Scoreゲージ
    st.progress(agg["total_score_mean"] / 100)
    st.text(f"Total Score: {agg['total_score_mean']:.1f}±{agg['total_score_std']:.1f}")
    
    # Confidence分布
    st.write("Confidence分布:")
    for level, count in agg["confidence_distribution"].items():
        st.badge(f"{level}: {count}", color={"high": "green", "medium": "yellow", "low": "red"}[level])
    
    # Reasoning（アコーディオン）
    with st.expander("採点根拠（Reasoning）"):
        for i, run in enumerate(result.runs):
            if not run.get("skipped"):
                st.write(f"**Run {i+1}**")
                st.json(run.get("reasoning", {}))
```

### 3.7 結果永続化

```python
class ResultStorage:
    """
    実行結果の保存・読み込みを管理
    """
    
    RESULTS_DIR = Path("results")
    
    @classmethod
    def save(cls, benchmark_result: BenchmarkResult):
        """
        実行結果をJSONとして保存
        
        ファイル名: YYYYMMDD_HHMMSS_<model_name>.json
        """
        cls.RESULTS_DIR.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_model_name = re.sub(r'[^\w\-]', '_', benchmark_result.target_model)
        filename = f"{timestamp}_{safe_model_name}.json"
        
        filepath = cls.RESULTS_DIR / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(benchmark_result.to_dict(), f, ensure_ascii=False, indent=2)
        
        return filepath
    
    @classmethod
    def load(cls, filepath: Path) -> BenchmarkResult:
        """保存済み結果を読み込み"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return BenchmarkResult.from_dict(data)
    
    @classmethod
    def list_results(cls) -> List[Path]:
        """保存済み結果ファイルの一覧を取得"""
        if not cls.RESULTS_DIR.exists():
            return []
        return sorted(cls.RESULTS_DIR.glob("*.json"), reverse=True)
```

---

## 4. 実装ステップ

### Phase 1: 基盤構築（Day 1）

| ステップ | 内容 | 成果物 |
|---------|------|--------|
| 1.1 | プロジェクト構造作成 | `adapters/`, `core/`, `ui/`, `tests/` ディレクトリ |
| 1.2 | 依存関係設定 | `pyproject.toml` に必要パッケージ追加 |
| 1.3 | アダプタ基底クラス実装 | `adapters/base.py` |
| 1.4 | OpenAIアダプタ実装 | `adapters/openai_adapter.py` |
| 1.5 | 環境設定ファイル作成 | `.env.example` |

### Phase 2: コア機能実装（Day 1-2）

| ステップ | 内容 | 成果物 |
|---------|------|--------|
| 2.1 | Anthropic/Geminiアダプタ実装 | `adapters/anthropic_adapter.py`, `gemini_adapter.py` |
| 2.2 | Judgeレスポンスパーサー | `core/json_parser.py` |
| 2.3 | 結果集計ロジック | `core/result_aggregator.py` |
| 2.4 | 評価エンジン実装 | `core/benchmark_engine.py` |

### Phase 3: UI実装（Day 2）

| ステップ | 内容 | 成果物 |
|---------|------|--------|
| 3.1 | UIコンポーネント作成 | `ui/components.py` |
| 3.2 | サイドバー設定パネル | `app.py` - 設定部分 |
| 3.3 | 結果表示カード | タスク別結果カード |
| 3.4 | サマリー表示 | 横断サマリービュー |

### Phase 4: 統合・テスト（Day 3）

| ステップ | 内容 | 成果物 |
|---------|------|--------|
| 4.1 | ルーブリック・プロンプト配置 | `rubrics/`, `prompts/` ディレクトリにコピー |
| 4.2 | 動作確認 | 1タスクでE2Eテスト |
| 4.3 | エラーハンドリング確認 | エラーケースの動作確認 |
| 4.4 | 結果保存・読み込みテスト | JSON永続化の確認 |

---

## 5. テスト戦略

### 5.1 ユニットテスト

```python
# tests/test_adapters.py

class TestOpenAIAdapter:
    """OpenAIアダプタのテスト"""
    
    def test_is_available_with_key(self):
        """APIキーが設定されている場合"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            adapter = OpenAIAdapter()
            assert adapter.is_available() is True
    
    def test_is_available_without_key(self):
        """APIキーが未設定の場合"""
        with patch.dict(os.environ, {}, clear=True):
            adapter = OpenAIAdapter()
            assert adapter.is_available() is False

class TestJsonParser:
    """JSONパーサーのテスト"""
    
    def test_parse_valid_json(self):
        """有効なJSONレスポンス"""
        response = '{"task_name": "test", "task_type": "fact", ...}'
        result = JudgeResponseParser.parse(response)
        assert result["task_name"] == "test"
    
    def test_parse_with_markdown_code_block(self):
        """Markdownコードブロック付きJSON"""
        response = '```json\n{"task_name": "test"}\n```'
        result = JudgeResponseParser.parse(response)
        assert result["task_name"] == "test"
```

### 5.2 統合テスト

- 1タスク（例: 01.md）で完全な評価フローを実行
- 各judge系統での評価が正しく動作することを確認
- 結果が正しく集計・表示されることを確認

---

## 6. リスクと対策

| リスク | 影響 | 対策 |
|--------|------|------|
| APIレート制限 | 実行中断 | 指数バックオフ実装、エラー時はスキップ |
| JSONパース失敗 | 評価結果欠落 | リトライ1回、失敗時はスキップして継続 |
| 高額API費用 | コスト超過 | 被験LLM max_tokens=2048固定、judge max_tokens=1024固定 |
| UI表示遅延 | ユーザ体験低下 | 非同期処理、プログレスバー表示 |

---

## 7. 成果物チェックリスト

- [ ] アダプタ層（3プロバイダー）
- [ ] 評価エンジン（並列・非同期対応）
- [ ] JSONパーサー（リトライ付き）
- [ ] 結果集計ロジック
- [ ] Streamlit UI（設定パネル・結果表示）
- [ ] 結果永続化（JSON保存・読み込み）
- [ ] 11個のルーブリック・プロンプト配置
- [ ] 環境設定ファイル
- [ ] README更新（実行方法）

---

## 8. 参考: JSONスキーマ

### 8.1 Judgeレスポンススキーマ

```json
{
  "task_name": "タスク名",
  "task_type": "fact | creative | speculative",
  "inferred_task_type": "task_typeが未記載の場合のみ記載。それ以外はnull",
  "weights": {
    "logic_and_fact": 60 | 30 | 40,
    "constraint_adherence": 30 | 30 | 20,
    "helpfulness_and_creativity": 10 | 40 | 40
  },
  "score": {
    "logic_and_fact": 0-40 | 0-60,
    "constraint_adherence": 0-20 | 0-30,
    "helpfulness_and_creativity": 0-40 | 0-10
  },
  "total_score": 0-100,
  "reasoning": {
    "logic_and_fact": "採点根拠（100文字以内）",
    "constraint_adherence": "採点根拠（100文字以内）",
    "helpfulness_and_creativity": "採点根拠（100文字以内）"
  },
  "critical_fail": false,
  "critical_fail_reason": "critical_failがtrueの場合のみ記載。それ以外はnull",
  "confidence": "high | medium | low"
}
```

### 8.2 結果保存スキーマ

```json
{
  "run_id": "20260217_153000_gpt-5.1",
  "target_model": "gpt-5.1",
  "judge_models": {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-5-20250929",
    "gemini": "gemini-1.5-pro"
  },
  "judge_runs": 3,
  "executed_at": "2026-02-17T15:30:00Z",
  "execution_duration_ms": 12345,
  "estimated_cost_usd": 0.0123,
  "cost_estimate_status": "partial",
  "usage_summary": {
    "calls": [...],
    "totals": {
      "call_count": 44,
      "input_tokens": 123456,
      "output_tokens": 7890,
      "estimated_cost_usd": 0.0123,
      "pricing_status": "partial",
      "unpriced_models": ["gemini:gemini-3.1-pro-preview"]
    }
  },
  "tasks": [...]
}
```
