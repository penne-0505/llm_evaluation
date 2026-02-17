"""LLMベンチマーク実行エンジン"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from adapters import LLMAdapter, LLMError
from core.json_parser import JudgeResponseParser, ParseError
from core.result_aggregator import ResultAggregator


class TaskResult:
    """単一タスクの評価結果"""

    def __init__(
        self,
        task_name: str,
        task_type: str,
        input_prompt: str,
        response: str,
        judge_results: Dict[str, Dict[str, Any]],
    ):
        self.task_name = task_name
        self.task_type = task_type
        self.input_prompt = input_prompt
        self.response = response
        self.judge_results = judge_results

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "task_name": self.task_name,
            "task_type": self.task_type,
            "input_prompt": self.input_prompt,
            "response": self.response,
            "judge_results": self.judge_results,
        }


class BenchmarkResult:
    """ベンチマーク全体の結果"""

    def __init__(
        self,
        run_id: str,
        target_model: str,
        judge_models: Dict[str, str],
        judge_runs: int,
        tasks: List[TaskResult],
    ):
        self.run_id = run_id
        self.target_model = target_model
        self.judge_models = judge_models
        self.judge_runs = judge_runs
        self.tasks = tasks
        self.executed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "run_id": self.run_id,
            "target_model": self.target_model,
            "judge_models": self.judge_models,
            "judge_runs": self.judge_runs,
            "executed_at": self.executed_at,
            "tasks": [task.to_dict() for task in self.tasks],
        }


class BenchmarkEngine:
    """
    LLMベンチマーク実行エンジン

    実行フロー:
    1. 被験LLM呼び出し → 回答取得
    2. 各judge系統（OpenAI/Anthropic/Gemini）でn回評価実行
    3. 結果を集計して返却
    """

    def __init__(
        self,
        subject_adapter: LLMAdapter,
        subject_model: str,
        judge_adapters: Dict[str, LLMAdapter],
        judge_runs: int = 3,
        max_parallel_judges: int = 5,
    ):
        """
        Args:
            subject_adapter: 被験LLM用アダプタ
            subject_model: 被験LLMのモデル名
            judge_adapters: judge用アダプタ辞書 {"model_name": adapter, ...}
            judge_runs: 各judgeでの評価回数
            max_parallel_judges: judge並列実行の最大数
        """
        self.subject_adapter = subject_adapter
        self.subject_model = subject_model
        self.judge_adapters = judge_adapters
        self.judge_runs = judge_runs
        self.max_parallel_judges = max_parallel_judges

    async def run_task(
        self,
        task_name: str,
        task_type: str,
        input_prompt: str,
        rubric_content: str,
        system_prompt: str,
        subject_temp: float = 1.0,
        progress_callback: Optional[Callable[[str], None]] = None,
        cancel_checker: Optional[Callable[[], None]] = None,
    ) -> TaskResult:
        """
        単一タスクの評価を実行

        Args:
            task_name: タスク名
            task_type: タスク型（fact/creative/speculative）
            input_prompt: 被験LLMへの入力プロンプト
            rubric_content: タスク固有ルーブリック
            system_prompt: judgeのシステムプロンプト
            subject_temp: 被験LLMのtemperature
            progress_callback: 進捗コールバック関数

        Returns:
            TaskResult: タスク実行結果
        """
        # 1. 被験LLM呼び出し
        if progress_callback:
            progress_callback(f"タスク '{task_name}': 被験LLM出力待ち...")

        if cancel_checker:
            cancel_checker()

        try:
            subject_response = await self._call_subject_llm(
                input_prompt, temperature=subject_temp
            )
        except LLMError as e:
            subject_response = f"[ERROR] {str(e)}"
            if progress_callback:
                progress_callback(f"タスク '{task_name}': 被験LLMエラー - {e}")

        if cancel_checker:
            cancel_checker()

        # 2. 各judgeで評価（並列）
        judge_results = {}
        semaphore = asyncio.Semaphore(self.max_parallel_judges)

        async def _evaluate_judge(model_name: str, adapter: LLMAdapter):
            if not adapter.is_available():
                return model_name, None

            if cancel_checker:
                cancel_checker()

            async with semaphore:
                if progress_callback:
                    progress_callback(
                        f"タスク '{task_name}': judge {model_name} 評価1/{self.judge_runs}開始"
                    )

                if cancel_checker:
                    cancel_checker()

                try:
                    result = await self._run_judge_evaluation(
                        adapter=adapter,
                        model_name=model_name,
                        subject_response=subject_response,
                        input_prompt=input_prompt,
                        rubric_content=rubric_content,
                        system_prompt=system_prompt,
                        progress_callback=progress_callback,
                    )
                    if progress_callback:
                        progress_callback(
                            f"タスク '{task_name}': judge {model_name} 評価確認"
                        )
                    return model_name, result
                except Exception as e:
                    if progress_callback:
                        progress_callback(
                            f"タスク '{task_name}': judge {model_name} エラー - {e}"
                        )
                    return model_name, {
                        "runs": [],
                        "aggregated": None,
                        "error": str(e),
                    }

        tasks = [
            _evaluate_judge(model_name, adapter)
            for model_name, adapter in self.judge_adapters.items()
        ]

        if tasks:
            results = await asyncio.gather(*tasks)
            for model_name, result in results:
                if result is not None:
                    judge_results[model_name] = result

        return TaskResult(
            task_name=task_name,
            task_type=task_type,
            input_prompt=input_prompt,
            response=subject_response,
            judge_results=judge_results,
        )

    async def _call_subject_llm(
        self, input_prompt: str, temperature: float = 1.0
    ) -> str:
        """
        被験LLMを呼び出し

        Args:
            input_prompt: 入力プロンプト
            temperature: 温度パラメータ

        Returns:
            LLMの回答
        """
        # 被験LLMにはシステムプロンプトなし
        response = await asyncio.to_thread(
            self.subject_adapter.complete_with_model,
            self.subject_model,
            "",
            input_prompt,
            temperature,
            4096,
        )

        return response

    async def _run_judge_evaluation(
        self,
        adapter: LLMAdapter,
        model_name: str,
        subject_response: str,
        input_prompt: str,
        rubric_content: str,
        system_prompt: str,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """
        単一judgeでの複数回評価実行

        Args:
            adapter: judge用アダプタ
            model_name: judgeモデル名
            subject_response: 被験LLMの回答
            input_prompt: 入力プロンプト
            rubric_content: ルーブリック内容
            system_prompt: judgeのシステムプロンプト
            progress_callback: 進捗コールバック

        Returns:
            評価結果（runs + aggregated）
        """
        runs = []

        for i in range(self.judge_runs):
            if progress_callback:
                progress_callback(f"judge: {model_name} {i + 1}/{self.judge_runs}回目")

            # プロンプト組み立て
            user_prompt = self._build_judge_user_prompt(
                input_prompt=input_prompt,
                subject_response=subject_response,
                rubric_content=rubric_content,
            )

            try:
                # judge呼び出し（リトライ1回）
                response = await self._call_judge_with_retry(
                    adapter=adapter,
                    model_name=model_name,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )

                # JSONパース
                try:
                    parsed = JudgeResponseParser.parse_with_retry(
                        response, max_retries=1
                    )
                    runs.append(parsed)
                except ParseError as e:
                    # パース失敗
                    runs.append(
                        {
                            "error": f"パース失敗: {str(e)}",
                            "raw_response": response,
                            "skipped": True,
                        }
                    )

            except LLMError as e:
                # API呼び出し失敗
                runs.append({"error": f"APIエラー: {str(e)}", "skipped": True})

            # レート制限対策のため少し待機
            if i < self.judge_runs - 1:
                await asyncio.sleep(0.5)

        # 集計
        return ResultAggregator.aggregate(runs)

    async def _call_judge_with_retry(
        self,
        adapter: LLMAdapter,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 1,
    ) -> str:
        """
        judge呼び出し（リトライ付き）

        Args:
            adapter: judgeアダプタ
            system_prompt: システムプロンプト
            user_prompt: ユーザープロンプト
            max_retries: 最大リトライ回数

        Returns:
            生成されたテキスト

        Raises:
            LLMError: 全てのリトライで失敗した場合
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                judge_temperature = 0.0
                if "gemini-3" in model_name.lower():
                    judge_temperature = 1.0
                response = await asyncio.to_thread(
                    adapter.complete_with_model,
                    model_name,
                    system_prompt,
                    user_prompt,
                    judge_temperature,
                    4096,
                )
                return response

            except LLMError as e:
                last_error = e
                if attempt < max_retries:
                    # 指数バックオフ
                    await asyncio.sleep(2**attempt)

        raise last_error or LLMError("judge呼び出しに失敗しました")

    def _build_judge_user_prompt(
        self, input_prompt: str, subject_response: str, rubric_content: str
    ) -> str:
        """
        judgeへのユーザープロンプトを構築

        ルーブリックはuser_promptに含め、system_promptのキャッシュ効率を高める

        Args:
            input_prompt: 被験LLMへの入力プロンプト
            subject_response: 被験LLMの回答
            rubric_content: ルーブリック内容

        Returns:
            組み立てられたプロンプト
        """
        return f"""## 入力プロンプト（被験LLMに渡したもの）
{input_prompt}

## 被験LLMの回答
{subject_response}

## タスク固有ルーブリック
{rubric_content}
"""
