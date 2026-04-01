"""LLMベンチマーク実行エンジン"""

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from adapters import CompletionResult, LLMAdapter, LLMError
from core.json_parser import JudgeResponseParser, ParseError
from core.result_aggregator import ResultAggregator
from core.tool_runtime import LocalToolRuntime, ToolRuntimeConfig, parse_tool_call


@dataclass
class SubjectRunResult:
    result: CompletionResult
    tool_trace: List[Dict[str, Any]]


class TaskResult:
    """単一タスクの評価結果"""

    def __init__(
        self,
        task_name: str,
        task_type: str,
        input_prompt: str,
        response: str,
        judge_results: Dict[str, Dict[str, Any]],
        subject_usage: Optional[Dict[str, Any]] = None,
        tool_trace: Optional[List[Dict[str, Any]]] = None,
    ):
        self.task_name = task_name
        self.task_type = task_type
        self.input_prompt = input_prompt
        self.response = response
        self.judge_results = judge_results
        self.subject_usage = subject_usage
        self.tool_trace = tool_trace or []

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "task_name": self.task_name,
            "task_type": self.task_type,
            "input_prompt": self.input_prompt,
            "response": self.response,
            "judge_results": self.judge_results,
            "subject_usage": self.subject_usage,
            "tool_trace": self.tool_trace,
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
        judge_fail_fast_threshold: int = 2,
        max_parallel_runs_per_judge: int = 3,
        judge_dispatch_min_interval_sec: float = 0.25,
        judge_dispatch_jitter_sec: float = 0.15,
    ):
        """
        Args:
            subject_adapter: 被験LLM用アダプタ
            subject_model: 被験LLMのモデル名
            judge_adapters: judge用アダプタ辞書 {"model_name": adapter, ...}
            judge_runs: 各judgeでの評価回数
            max_parallel_judges: judge並列実行の最大数
            judge_fail_fast_threshold: 失敗累積時の早期スキップ閾値
            max_parallel_runs_per_judge: 各judgeモデル内のrun並列数
            judge_dispatch_min_interval_sec: 同一judgeモデル内の最小投入間隔(秒)
            judge_dispatch_jitter_sec: 同一judgeモデル内の投入ジッター最大値(秒)
        """
        self.subject_adapter = subject_adapter
        self.subject_model = subject_model
        self.judge_adapters = judge_adapters
        self.judge_runs = judge_runs
        self.max_parallel_judges = max_parallel_judges
        self.judge_fail_fast_threshold = judge_fail_fast_threshold
        self.max_parallel_runs_per_judge = max_parallel_runs_per_judge
        self.judge_dispatch_min_interval_sec = max(0.0, judge_dispatch_min_interval_sec)
        self.judge_dispatch_jitter_sec = max(0.0, judge_dispatch_jitter_sec)

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
        subject_tools: Optional[Dict[str, Any]] = None,
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
            subject_run = await self._call_subject_llm(
                input_prompt,
                temperature=subject_temp,
                progress_callback=progress_callback,
                cancel_checker=cancel_checker,
                subject_tools=subject_tools,
            )
            subject_result = subject_run.result
            subject_response = subject_result.text
        except LLMError as e:
            subject_response = f"[ERROR] {str(e)}"
            subject_result = CompletionResult(text=subject_response, usage=None)
            subject_run = SubjectRunResult(result=subject_result, tool_trace=[])
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
                        cancel_checker=cancel_checker,
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
            subject_usage=subject_result.usage.to_dict()
            if subject_result.usage
            else None,
            tool_trace=subject_run.tool_trace,
        )

    async def _call_subject_llm(
        self,
        input_prompt: str,
        temperature: float = 1.0,
        progress_callback: Optional[Callable[[str], None]] = None,
        cancel_checker: Optional[Callable[[], None]] = None,
        subject_tools: Optional[Dict[str, Any]] = None,
    ) -> SubjectRunResult:
        """
        被験LLMを呼び出し

        Args:
            input_prompt: 入力プロンプト
            temperature: 温度パラメータ

        Returns:
            LLMの回答と tool trace
        """
        config = ToolRuntimeConfig.from_dict(subject_tools)
        if config is None:
            response = await self._complete_subject_once(
                user_prompt=input_prompt,
                temperature=temperature,
                cancel_checker=cancel_checker,
            )
            return SubjectRunResult(result=response, tool_trace=[])

        runtime = LocalToolRuntime(config)
        tool_trace: List[Dict[str, Any]] = []
        history: List[Tuple[str, str]] = []
        usage_records: List[CompletionResult] = []

        for step_index in range(config.max_steps + 1):
            if cancel_checker:
                cancel_checker()

            user_prompt = self._build_subject_user_prompt(
                input_prompt=input_prompt,
                history=history,
                tool_instruction=runtime.render_tool_instruction(),
            )
            response = await self._complete_subject_once(
                user_prompt=user_prompt,
                temperature=temperature,
                cancel_checker=cancel_checker,
            )
            usage_records.append(response)
            tool_call = parse_tool_call(response.text)

            if tool_call is None:
                return SubjectRunResult(
                    result=self._merge_subject_usage(response.text, usage_records),
                    tool_trace=tool_trace,
                )

            if step_index >= config.max_steps:
                return SubjectRunResult(
                    result=self._merge_subject_usage(
                        "[ERROR] tool step limit exceeded before final answer",
                        usage_records,
                    ),
                    tool_trace=tool_trace,
                )

            if progress_callback:
                progress_callback(
                    f"タスク検索: {tool_call.name} step {step_index + 1}/{config.max_steps}"
                )

            tool_result = runtime.execute(tool_call)
            tool_trace.append(
                {
                    "step_index": step_index + 1,
                    "tool_name": tool_call.name,
                    "arguments": tool_call.arguments,
                    "result_summary": runtime.summarize_result(tool_result),
                    "ok": bool(tool_result.get("ok")),
                }
            )
            history.append(("assistant", response.text))
            history.append(("tool", runtime.render_tool_result(tool_result)))

        return SubjectRunResult(
            result=self._merge_subject_usage(
                "[ERROR] tool loop terminated without final answer", usage_records
            ),
            tool_trace=tool_trace,
        )

    async def _complete_subject_once(
        self,
        user_prompt: str,
        temperature: float,
        cancel_checker: Optional[Callable[[], None]] = None,
    ) -> CompletionResult:
        if cancel_checker:
            cancel_checker()
        return await asyncio.to_thread(
            self.subject_adapter.complete_with_model_result,
            self.subject_model,
            "",
            user_prompt,
            temperature,
            4096,
        )

    @staticmethod
    def _build_subject_user_prompt(
        input_prompt: str,
        history: List[Tuple[str, str]],
        tool_instruction: str,
    ) -> str:
        parts = [
            "## ユーザー依頼",
            input_prompt,
            "",
            "## ツール利用ルール",
            tool_instruction,
        ]
        if history:
            parts.extend(["", "## 途中経過"])
            for role, content in history:
                label = "assistant" if role == "assistant" else "tool"
                parts.extend([f"### {label}", content])
        return "\n".join(parts)

    def _merge_subject_usage(
        self, text: str, responses: List[CompletionResult]
    ) -> CompletionResult:
        usage_payloads = [item.usage for item in responses if item.usage is not None]
        if not usage_payloads:
            return CompletionResult(text=text, usage=None)

        first = usage_payloads[0]
        return CompletionResult(
            text=text,
            usage=type(first)(
                provider=first.provider,
                model=first.model,
                input_tokens=sum(item.input_tokens or 0 for item in usage_payloads),
                output_tokens=sum(item.output_tokens or 0 for item in usage_payloads),
                total_tokens=sum(item.total_tokens or 0 for item in usage_payloads),
                cache_creation_input_tokens=sum(
                    item.cache_creation_input_tokens or 0 for item in usage_payloads
                ),
                cache_read_input_tokens=sum(
                    item.cache_read_input_tokens or 0 for item in usage_payloads
                ),
            ),
        )

    async def _run_judge_evaluation(
        self,
        adapter: LLMAdapter,
        model_name: str,
        subject_response: str,
        input_prompt: str,
        rubric_content: str,
        system_prompt: str,
        progress_callback: Optional[Callable[[str], None]] = None,
        cancel_checker: Optional[Callable[[], None]] = None,
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
        runs_by_index: List[Optional[Dict[str, Any]]] = [None] * self.judge_runs
        failure_count = 0
        should_skip_remaining = False
        cancelled_during_judge = False
        state_lock = asyncio.Lock()
        queue: asyncio.Queue[Optional[int]] = asyncio.Queue()
        pacing_lock = asyncio.Lock()
        last_dispatch_at = 0.0

        # プロンプトは各runで不変のため1回だけ組み立てる
        user_prompt = self._build_judge_user_prompt(
            input_prompt=input_prompt,
            subject_response=subject_response,
            rubric_content=rubric_content,
        )

        def _is_cancelled() -> bool:
            if cancel_checker is None:
                return False
            try:
                cancel_checker()
            except asyncio.CancelledError:
                return True
            return False

        async def _wait_for_dispatch_slot() -> None:
            nonlocal last_dispatch_at
            if _is_cancelled():
                raise asyncio.CancelledError("ユーザーによってキャンセルされました")
            if (
                self.judge_dispatch_min_interval_sec <= 0
                and self.judge_dispatch_jitter_sec <= 0
            ):
                return

            async with pacing_lock:
                now = asyncio.get_running_loop().time()
                min_interval = self.judge_dispatch_min_interval_sec
                wait_time = max(0.0, min_interval - (now - last_dispatch_at))
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    if _is_cancelled():
                        raise asyncio.CancelledError(
                            "ユーザーによってキャンセルされました"
                        )

                jitter = 0.0
                if self.judge_dispatch_jitter_sec > 0:
                    jitter = random.uniform(0.0, self.judge_dispatch_jitter_sec)
                    await asyncio.sleep(jitter)
                    if _is_cancelled():
                        raise asyncio.CancelledError(
                            "ユーザーによってキャンセルされました"
                        )

                last_dispatch_at = asyncio.get_running_loop().time()

        async def _register_failure() -> int:
            nonlocal failure_count, should_skip_remaining
            async with state_lock:
                failure_count += 1
                if (
                    self.judge_fail_fast_threshold > 0
                    and failure_count >= self.judge_fail_fast_threshold
                ):
                    should_skip_remaining = True
                return failure_count

        async def _worker() -> None:
            nonlocal cancelled_during_judge
            while True:
                run_index = await queue.get()
                if run_index is None:
                    queue.task_done()
                    break

                try:
                    if _is_cancelled():
                        cancelled_during_judge = True
                        runs_by_index[run_index] = {
                            "error": "ユーザーによってキャンセルされました",
                            "skipped": True,
                            "cancelled": True,
                        }
                        continue

                    if progress_callback:
                        progress_callback(
                            f"judge: {model_name} {run_index + 1}/{self.judge_runs}回目"
                        )

                    async with state_lock:
                        skip_now = should_skip_remaining
                        current_failures = failure_count

                    if skip_now:
                        runs_by_index[run_index] = {
                            "error": f"失敗累計({current_failures})のため残り試行をスキップ",
                            "skipped": True,
                            "fail_fast_skipped": True,
                        }
                        continue

                    await _wait_for_dispatch_slot()

                    response = await self._call_judge_with_retry(
                        adapter=adapter,
                        model_name=model_name,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        cancel_checker=cancel_checker,
                    )

                    try:
                        parsed = JudgeResponseParser.parse_with_retry(
                            response.text, max_retries=1
                        )
                        if response.usage is not None:
                            parsed["usage"] = response.usage.to_dict()
                        runs_by_index[run_index] = parsed
                    except ParseError as e:
                        failures = await _register_failure()
                        runs_by_index[run_index] = {
                            "error": f"パース失敗: {str(e)}",
                            "raw_response": response.text,
                            "skipped": True,
                            "failure_count": failures,
                            "usage": response.usage.to_dict()
                            if response.usage is not None
                            else None,
                        }
                except asyncio.CancelledError:
                    cancelled_during_judge = True
                    runs_by_index[run_index] = {
                        "error": "ユーザーによってキャンセルされました",
                        "skipped": True,
                        "cancelled": True,
                    }
                except LLMError as e:
                    failures = await _register_failure()
                    runs_by_index[run_index] = {
                        "error": f"APIエラー: {str(e)}",
                        "skipped": True,
                        "failure_count": failures,
                    }
                finally:
                    queue.task_done()

        for run_index in range(self.judge_runs):
            queue.put_nowait(run_index)

        worker_count = min(self.max_parallel_runs_per_judge, self.judge_runs)
        workers = [asyncio.create_task(_worker()) for _ in range(worker_count)]

        await queue.join()

        for _ in workers:
            queue.put_nowait(None)
        await asyncio.gather(*workers)

        if cancelled_during_judge:
            raise asyncio.CancelledError("ユーザーによってキャンセルされました")

        runs = [run for run in runs_by_index if run is not None]

        # 集計
        return ResultAggregator.aggregate(runs)

    async def _call_judge_with_retry(
        self,
        adapter: LLMAdapter,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 1,
        cancel_checker: Optional[Callable[[], None]] = None,
    ) -> CompletionResult:
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
            if cancel_checker:
                cancel_checker()
            try:
                judge_temperature = 0.0
                if "gemini-3" in model_name.lower():
                    judge_temperature = 1.0
                response = await asyncio.to_thread(
                    adapter.complete_with_model_result,
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
                    if cancel_checker:
                        cancel_checker()
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
