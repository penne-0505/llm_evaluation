# LLMベンチマークアプリ 要件定義書

## 概要

LLMモデルを、タスク固有のルーブリックに基づいてLLM-as-a-judgeで自動評価するStreamlitアプリ。
「被験LLM呼び出し → 複数judgeによる評価 × n回 → 結果表示・保存」をワンセットで実行する。

**設計思想**: 完全公平なjudgeを目指すのではなく、「私視点の実用性・性能を測るベンチマーク」として機能させる。
judgeはGPT系・Claude系・Gemini系それぞれが独立して評価し、結果は集約せずそのまま並置して表示する。

---

## 技術スタック

- **UI**: Streamlit
- **言語**: Python 3.10+
- **主要ライブラリ**: `openai`, `anthropic`, `google-generativeai`, `python-dotenv`, `pandas`, `plotly`

---

## ディレクトリ構成

```
benchmark_app/
├── app.py                      # Streamlitエントリポイント
├── .env                        # APIキー（gitignore対象）
├── .env.example                # APIキーのテンプレート
├── rubrics/                    # タスク固有ルーブリック（Markdownファイル）
│   ├── chloroform.md
│   ├── obsidian.md
│   └── ... (11ファイル)
├── prompts/                    # 被験LLMに渡す入力プロンプト（タスクごと）
│   ├── chloroform.txt
│   ├── obsidian.txt
│   └── ... (11ファイル)
├── judge_system_prompt.md      # judgeのシステムプロンプト
├── adapters/                   # プロバイダーごとのAPIアダプタ
│   ├── base.py                 # 抽象基底クラス
│   ├── openai_adapter.py
│   ├── anthropic_adapter.py
│   └── gemini_adapter.py
├── results/                    # 実行結果のJSONログ（自動生成）
│   └── YYYYMMDD_HHMMSS_<model_name>.json
└── requirements.txt
```

---

## APIキー管理

`.env` ファイルで管理する。UIからの入力は不要。

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...

# judgeに使用するモデル（系統ごとに1モデル指定）
JUDGE_OPENAI_MODEL=gpt-4o
JUDGE_ANTHROPIC_MODEL=claude-sonnet-4-5-20250929
JUDGE_GEMINI_MODEL=gemini-1.5-pro
```

---

## アダプタ層の設計

現在はOpenAI・Anthropic・Geminiを対象とするが、将来の拡張に備えて全APIアクセスをアダプタ経由とする。

```python
# adapters/base.py
from abc import ABC, abstractmethod

class LLMAdapter(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str,
                 temperature: float, max_tokens: int) -> str:
        """テキスト生成。戻り値は文字列のみ。"""
        pass

# 実装例: adapters/openai_adapter.py
class OpenAIAdapter(LLMAdapter):
    def complete(self, system_prompt, user_prompt, temperature, max_tokens):
        # openai.ChatCompletion を呼び出して文字列を返す
        ...
```

新プロバイダーの追加は `LLMAdapter` を継承したクラスを追加するだけでよい。

---

## 対応プロバイダー・モデル

### 被験LLM（評価対象）
- 1回の実行につき1モデルのみ評価
- モデル名はUIのテキストフィールドで自由入力
- プロバイダーはモデル名のプレフィックスから自動判定:
  - `gpt-` / `o1` / `o3` / `o4` → OpenAI
  - `claude-` → Anthropic
  - `gemini-` → Gemini
  - 判定不能な場合はUIでプロバイダーを手動選択

### judge LLM
- GPT系・Claude系・Gemini系の3系統が**それぞれ独立して**評価を実行
- `.env` の `JUDGE_*_MODEL` で各系統のモデルを指定
- APIキーが設定されていない系統のjudgeはスキップ（エラーにしない）
- **judgeの結果は集約しない。各系統の結果をそのまま並置表示する**

---

## 機能要件

### 1. 実行設定パネル（サイドバー）

| 設定項目 | 内容 |
|---------|------|
| 評価対象モデル | テキスト入力（例: `gpt-5.1`） |
| タスク選択 | チェックボックスで11タスクから任意選択（「全選択」ボタンあり） |
| judge実行回数 | スライダー（1〜5回、デフォルト3）※各judge系統ごとに同回数実行 |
| temperature（被験LLM） | スライダー（0.0〜1.0、デフォルト1.0） |
| temperature（judge） | 固定: 0.0（変更不可・表示のみ） |

### 2. 実行フロー

```
for タスク in 選択タスクリスト:
    1. 被験LLMに入力プロンプトを送信 → 回答を取得（1回のみ）

    for judge_family in [OpenAI, Anthropic, Gemini]:  # 有効なもののみ
        for i in range(judge_runs):
            2. judge_system_prompt + ルーブリック + 被験LLM回答 をjudgeに送信
            3. JSONレスポンスをパース・保存

        4. n回分のスコアを集計（judge系統ごと）:
           - 各項目の平均スコア・標準偏差
           - total_scoreの平均・標準偏差
           - confidenceの分布
           - critical_failフラグ

    5. 結果をリアルタイムでUIに反映
```

### 3. 結果表示

#### タスク別スコアカード

各タスクカードの中に、**judge系統ごとのタブ**を設ける（OpenAI / Anthropic / Gemini）。

各タブに表示する内容:
- task_type バッジ（fact=青, creative=緑, speculative=橙）
- 各スコア項目: 平均 ± 標準偏差
- total_score のゲージ
- critical_failの場合は赤バナー
- confidence分布（high/medium/lowのバッジ）
- reasoning（各項目の採点根拠）をアコーディオンで展開可能

被験LLMの回答原文はタブ外（カード上部）に1つ表示。

#### 横断サマリー（全タスク完了後）

- judge系統ごとのtask_type別平均スコア（棒グラフ3本並び）
- judge系統ごとの全タスクスコア一覧テーブル
- 標準偏差 > 5点のタスクを「分散警告」としてリスト表示
- confidence: lowまたはcritical_failのタスクを「要確認リスト」として表示

**judge間のスコア比較グラフは表示するが、集計・統合は行わない**
（例: タスクXに対して GPT-judge=82点、Claude-judge=74点、Gemini-judge=79点 を並べて表示）

### 4. 結果の永続化

実行完了後、`results/YYYYMMDD_HHMMSS_<model_name>.json` として自動保存。

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
  "tasks": [
    {
      "task_name": "クロロホルムの医学的リアリティ",
      "task_type": "fact",
      "input_prompt": "（被験LLMに渡した入力プロンプト）",
      "response": "（被験LLMの回答原文）",
      "judge_results": {
        "openai": {
          "runs": [ /* judge 1〜3回目のJSONそのまま */ ],
          "aggregated": {
            "logic_and_fact_mean": 55.0,
            "logic_and_fact_std": 2.5,
            "constraint_adherence_mean": 28.0,
            "constraint_adherence_std": 1.0,
            "helpfulness_mean": 8.0,
            "helpfulness_std": 0.0,
            "total_score_mean": 91.0,
            "total_score_std": 3.5,
            "critical_fail": false,
            "confidence_distribution": { "high": 3, "medium": 0, "low": 0 }
          }
        },
        "anthropic": { /* 同構造 */ },
        "gemini": { /* 同構造 */ }
      }
    }
  ]
}
```

サイドバーに「過去結果を読み込む」ボタンを設置し、保存済みJSONをUIに再表示可能にする。

---

## 非機能要件

- 実行中はプログレスバーとステータスメッセージを表示（例: 「タスク 3/11 | judge: Anthropic 2/3回目」）
- API呼び出しエラー時はタスク×judge単位でスキップしてエラーメッセージを表示（全体を止めない）
- judgeのJSON出力が不正な場合（パース失敗）はリトライを1回行い、失敗したらそのrunをスキップ
- 被験LLMの `max_tokens`: `2048` 固定
- judgeの `max_tokens`: `1024` 固定

---

## judgeへのプロンプト組み立て

```python
system_prompt = open("judge_system_prompt.md").read()

user_prompt = f"""
## 入力プロンプト（被験LLMに渡したもの）
{input_prompt}

## 被験LLMの回答
{llm_response}

## タスク固有ルーブリック
{rubric_content}
"""
```

> **実装上の注意**: `{{Task_Specific_Rubric}}` プレースホルダはシステムプロンプトに含めず、
> ルーブリックはuser_promptに直接組み込む。システムプロンプトのキャッシュ効率を高めるため。