"""BenchmarkEngine の並列・失敗制御テスト"""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from adapters import CompletionResult, LLMAdapter, UsageMetrics
from adapters.base import NativeCompletionResult, NativeToolCall
from core.benchmark_engine import BenchmarkEngine


class _StubAdapter(LLMAdapter):
    def __init__(self, responses, reasoning_opt_in=False):
        self._responses = list(responses)
        self._reasoning_opt_in = reasoning_opt_in
        self.call_count = 0
        self.calls = []
        self.PROVIDER = "stub"

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        return self.complete_with_model(
            "stub-model", system_prompt, user_prompt, temperature, max_tokens
        )

    def is_available(self) -> bool:
        return True

    def is_reasoning_opt_in(self, model: str) -> bool:
        return self._reasoning_opt_in

    def complete_with_model(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        return self.complete_with_model_result(
            model, system_prompt, user_prompt, temperature, max_tokens
        ).text

    def complete_with_model_result(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        extra_params=None,
    ) -> CompletionResult:
        self.call_count += 1
        self.calls.append(
            {
                "model": model,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "extra_params": extra_params,
            }
        )
        if self._responses:
            item = self._responses.pop(0)
        else:
            item = ""
        if isinstance(item, CompletionResult):
            return item
        return CompletionResult(
            text=item,
            usage=UsageMetrics(
                provider=self.PROVIDER,
                model=model,
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                duration_ms=100,
            ),
        )


class _NativeToolLoopAdapter(_StubAdapter):
    def __init__(self, native_responses, final_responses):
        super().__init__(final_responses)
        self._native_responses = list(native_responses)
        self.native_call_count = 0
        self.native_calls = []

    def supports_native_tools(self) -> bool:
        return True

    def complete_with_model_native_tools(
        self,
        model,
        messages,
        tools,
        temperature=0.0,
        max_tokens=4096,
        extra_params=None,
    ):
        self.native_call_count += 1
        self.native_calls.append({"extra_params": extra_params})
        if self._native_responses:
            result = self._native_responses.pop(0)
        else:
            result = NativeCompletionResult(content="final", tool_calls=[])
        result.usage = UsageMetrics(
            provider=self.PROVIDER,
            model=model,
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            duration_ms=100,
        )
        return result


class TestBenchmarkEngine(unittest.IsolatedAsyncioTestCase):
    async def test_reasoning_opt_in_subject_uses_high_effort(self):
        subject_adapter = _StubAdapter(["subject-response"], reasoning_opt_in=True)
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="reasoning-model",
            judge_adapters={},
            judge_runs=1,
        )

        await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )

        self.assertEqual(
            subject_adapter.calls[0]["extra_params"],
            {"reasoning": {"effort": "high"}},
        )

    async def test_fail_fast_skips_remaining_runs_after_threshold(self):
        subject_adapter = _StubAdapter(["subject-response"])
        judge_adapter = _StubAdapter(["not-json", "still-not-json"])
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="gpt-4o",
            judge_adapters={"judge-model": judge_adapter},
            judge_runs=5,
            judge_fail_fast_threshold=2,
            max_parallel_runs_per_judge=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        result = await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )

        judge_runs = result.judge_results["judge-model"]["runs"]
        fail_fast_skipped = [run for run in judge_runs if run.get("fail_fast_skipped")]

        self.assertEqual(judge_adapter.call_count, 4)
        self.assertEqual(len(judge_runs), 5)
        self.assertEqual(len(fail_fast_skipped), 3)

    async def test_no_fixed_sleep_between_successful_runs(self):
        valid_response = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 60,
                    "constraint_adherence": 30,
                    "helpfulness_and_creativity": 10,
                },
                "total_score": 100,
                "confidence": "high",
            }
        )
        subject_adapter = _StubAdapter(["subject-response"])
        judge_adapter = _StubAdapter([valid_response, valid_response, valid_response])
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="gpt-4o",
            judge_adapters={"judge-model": judge_adapter},
            judge_runs=3,
            judge_fail_fast_threshold=2,
            max_parallel_runs_per_judge=3,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        with patch(
            "core.benchmark_engine.asyncio.sleep", new=AsyncMock()
        ) as sleep_mock:
            await engine.run_task(
                task_name="01",
                task_type="fact",
                input_prompt="prompt",
                rubric_content="rubric",
                system_prompt="system",
            )

        self.assertEqual(judge_adapter.call_count, 3)
        self.assertEqual(sleep_mock.await_count, 0)

    async def test_task_result_includes_subject_and_judge_usage(self):
        valid_response = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 60,
                    "constraint_adherence": 30,
                    "helpfulness_and_creativity": 10,
                },
                "total_score": 100,
                "confidence": "high",
            }
        )
        subject_adapter = _StubAdapter(["subject-response"])
        judge_adapter = _StubAdapter([valid_response])
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="openrouter/google/gemma-4-31b-it",
            judge_adapters={"judge-model": judge_adapter},
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        result = await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )
        payload = result.to_dict()

        self.assertEqual(payload["subject_usage"]["input_tokens"], 10)
        self.assertFalse(payload["has_subject_tools"])
        self.assertEqual(
            payload["judge_results"]["judge-model"]["runs"][0]["usage"][
                "output_tokens"
            ],
            5,
        )
        self.assertEqual(
            payload["task_timing"],
            {"subject_duration_ms": 100, "judge_duration_ms": 100},
        )

    async def test_merge_subject_usage_sums_duration_ms(self):
        engine = BenchmarkEngine(
            subject_adapter=_StubAdapter([]),
            subject_model="stub-model",
            judge_adapters={},
            judge_runs=1,
        )
        merged = engine._merge_subject_usage(
            "final",
            [
                CompletionResult(
                    text="a",
                    usage=UsageMetrics(
                        provider="stub",
                        model="stub-model",
                        input_tokens=3,
                        output_tokens=1,
                        total_tokens=4,
                        duration_ms=120,
                    ),
                ),
                CompletionResult(
                    text="b",
                    usage=UsageMetrics(
                        provider="stub",
                        model="stub-model",
                        input_tokens=7,
                        output_tokens=2,
                        total_tokens=9,
                        duration_ms=80,
                    ),
                ),
            ],
        )
        self.assertEqual(merged.usage.input_tokens, 10)
        self.assertEqual(merged.usage.duration_ms, 200)

    def test_build_task_timing_sums_judge_runs(self):
        from core.benchmark_engine import TaskResult

        timing = TaskResult.build_task_timing(
            {"duration_ms": 250},
            {
                "judge-a": {
                    "runs": [
                        {"usage": {"duration_ms": 100}},
                        {"usage": {"duration_ms": 50}},
                        {"skipped": True},
                    ]
                },
                "judge-b": {"runs": [{"usage": {"duration_ms": 40}}]},
            },
        )
        self.assertEqual(
            timing,
            {"subject_duration_ms": 250, "judge_duration_ms": 190},
        )

    async def test_reasoning_opt_in_judge_uses_high_effort(self):
        valid_response = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 60,
                    "constraint_adherence": 30,
                    "helpfulness_and_creativity": 10,
                },
                "total_score": 100,
                "confidence": "high",
            }
        )
        subject_adapter = _StubAdapter(["subject-response"])
        judge_adapter = _StubAdapter([valid_response], reasoning_opt_in=True)
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="gpt-4o",
            judge_adapters={"judge-model": judge_adapter},
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )

        self.assertEqual(
            judge_adapter.calls[0]["extra_params"],
            {"reasoning": {"effort": "high"}},
        )

    async def test_gemini_3_judge_omits_temperature(self):
        valid_response = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 60,
                    "constraint_adherence": 30,
                    "helpfulness_and_creativity": 10,
                },
                "total_score": 100,
                "confidence": "high",
            }
        )
        subject_adapter = _StubAdapter(["subject-response"])
        judge_adapter = _StubAdapter([valid_response], reasoning_opt_in=True)
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="subject-model",
            judge_adapters={"openrouter/google/gemini-3.5-flash": judge_adapter},
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )

        self.assertIsNone(judge_adapter.calls[0]["temperature"])
        self.assertEqual(
            judge_adapter.calls[0]["extra_params"],
            {"reasoning": {"effort": "high"}},
        )

    async def test_judge_run_persists_api_reasoning_separate_from_scoring_reasoning(self):
        """AC-002 / DEC-001: api_reasoning と judge JSON reasoning を分離して永続化"""
        valid_response = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 60,
                    "constraint_adherence": 30,
                    "helpfulness_and_creativity": 10,
                },
                "total_score": 100,
                "confidence": "high",
                "reasoning": {
                    "logic_and_fact": "scoring rationale only",
                },
            }
        )
        subject_adapter = _StubAdapter(["subject-response"])
        judge_adapter = _StubAdapter(
            [
                CompletionResult(
                    text=valid_response,
                    usage=UsageMetrics(
                        provider="stub",
                        model="judge-model",
                        input_tokens=10,
                        output_tokens=5,
                        total_tokens=15,
                    ),
                    api_reasoning="model internal thinking",
                )
            ]
        )
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="gpt-4o",
            judge_adapters={"judge-model": judge_adapter},
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        result = await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )
        payload = result.to_dict()
        run = payload["judge_results"]["judge-model"]["runs"][0]
        self.assertEqual(run["api_reasoning"], "model internal thinking")
        self.assertEqual(
            run["reasoning"]["logic_and_fact"],
            "scoring rationale only",
        )
        self.assertEqual(
            payload["judge_results"]["judge-model"]["aggregated"]["total_score_mean"],
            100.0,
        )

    async def test_judge_thinking_tags_stripped_before_parse(self):
        """AC-002 / DEC-003: content 内 <thinking> を strip して JSON パース成功"""
        judge_json = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 60,
                    "constraint_adherence": 30,
                    "helpfulness_and_creativity": 10,
                },
                "total_score": 100,
                "confidence": "high",
                "reasoning": "score reason",
            }
        )
        tagged = f"<thinking>hidden plan</thinking>\n{judge_json}"
        subject_adapter = _StubAdapter(["subject-response"])
        judge_adapter = _StubAdapter([tagged])
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="gpt-4o",
            judge_adapters={"judge-model": judge_adapter},
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        result = await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )
        payload = result.to_dict()
        run = payload["judge_results"]["judge-model"]["runs"][0]
        self.assertEqual(run["api_reasoning"], "hidden plan")
        self.assertEqual(run["reasoning"], "score reason")
        self.assertEqual(
            payload["judge_results"]["judge-model"]["aggregated"]["total_score_mean"],
            100.0,
        )

    async def test_judge_missing_api_reasoning_still_aggregates(self):
        """AC-004: thinking 欠落でもスコア集計は成功"""
        valid_response = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 50,
                    "constraint_adherence": 25,
                    "helpfulness_and_creativity": 10,
                },
                "total_score": 85,
                "confidence": "medium",
            }
        )
        subject_adapter = _StubAdapter(["subject-response"])
        judge_adapter = _StubAdapter([valid_response])
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="gpt-4o",
            judge_adapters={"judge-model": judge_adapter},
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        result = await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )
        payload = result.to_dict()
        run = payload["judge_results"]["judge-model"]["runs"][0]
        self.assertNotIn("api_reasoning", run)
        self.assertEqual(
            payload["judge_results"]["judge-model"]["aggregated"]["total_score_mean"],
            85.0,
        )

    async def test_claude_thinking_suffix_no_effort_persists_api_reasoning(self):
        """AC-003 / AC-004 / DEC-003: :thinking は effort 未送信でも api_reasoning 永続化"""
        valid_response = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 60,
                    "constraint_adherence": 30,
                    "helpfulness_and_creativity": 10,
                },
                "total_score": 100,
                "confidence": "high",
                "reasoning": {"logic_and_fact": "score only"},
            }
        )
        subject_adapter = _StubAdapter(["subject-response"])
        judge_adapter = _StubAdapter(
            [
                CompletionResult(
                    text=valid_response,
                    usage=UsageMetrics(
                        provider="openrouter",
                        model="anthropic/claude-3.7-sonnet:thinking",
                        input_tokens=10,
                        output_tokens=5,
                        total_tokens=15,
                    ),
                    api_reasoning="claude always-on thinking",
                )
            ],
            reasoning_opt_in=False,
        )
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="subject-model",
            judge_adapters={
                "anthropic/claude-3.7-sonnet:thinking": judge_adapter
            },
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        result = await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )
        payload = result.to_dict()
        model_key = "anthropic/claude-3.7-sonnet:thinking"
        run = payload["judge_results"][model_key]["runs"][0]
        self.assertIsNone(judge_adapter.calls[0]["extra_params"])
        self.assertEqual(run["api_reasoning"], "claude always-on thinking")
        self.assertEqual(run["reasoning"]["logic_and_fact"], "score only")
        self.assertEqual(
            payload["judge_results"][model_key]["aggregated"]["total_score_mean"],
            100.0,
        )

    async def test_claude_opt_in_effort_and_api_reasoning(self):
        """AC-004: Claude opt-in は effort high 送信 + api_reasoning 永続化"""
        valid_response = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 60,
                    "constraint_adherence": 30,
                    "helpfulness_and_creativity": 10,
                },
                "total_score": 100,
                "confidence": "high",
                "reasoning": "scoring rationale",
            }
        )
        subject_adapter = _StubAdapter(["subject-response"])
        judge_adapter = _StubAdapter(
            [
                CompletionResult(
                    text=valid_response,
                    usage=UsageMetrics(
                        provider="openrouter",
                        model="anthropic/claude-3.7-sonnet",
                        input_tokens=8,
                        output_tokens=4,
                        total_tokens=12,
                    ),
                    api_reasoning="claude opt-in thinking",
                )
            ],
            reasoning_opt_in=True,
        )
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="subject-model",
            judge_adapters={"anthropic/claude-3.7-sonnet": judge_adapter},
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        result = await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )
        payload = result.to_dict()
        run = payload["judge_results"]["anthropic/claude-3.7-sonnet"]["runs"][0]
        self.assertEqual(
            judge_adapter.calls[0]["extra_params"],
            {"reasoning": {"effort": "high"}},
        )
        self.assertEqual(run["api_reasoning"], "claude opt-in thinking")
        self.assertEqual(run["reasoning"], "scoring rationale")

    async def test_gemini_thinking_persists_api_reasoning(self):
        """AC-002 / AC-003: Gemini thinking モデルの api_reasoning 永続化"""
        valid_response = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 55,
                    "constraint_adherence": 25,
                    "helpfulness_and_creativity": 10,
                },
                "total_score": 90,
                "confidence": "high",
                "reasoning": {"helpfulness_and_creativity": "score note"},
            }
        )
        subject_adapter = _StubAdapter(["subject-response"])
        judge_adapter = _StubAdapter(
            [
                CompletionResult(
                    text=valid_response,
                    usage=UsageMetrics(
                        provider="openrouter",
                        model="google/gemini-2.5-flash-preview",
                        input_tokens=12,
                        output_tokens=6,
                        total_tokens=18,
                    ),
                    api_reasoning="gemini thinking trace",
                )
            ],
            reasoning_opt_in=True,
        )
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="subject-model",
            judge_adapters={"google/gemini-2.5-flash-preview": judge_adapter},
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        result = await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )
        payload = result.to_dict()
        run = payload["judge_results"]["google/gemini-2.5-flash-preview"]["runs"][0]
        self.assertEqual(run["api_reasoning"], "gemini thinking trace")
        self.assertEqual(
            run["reasoning"]["helpfulness_and_creativity"],
            "score note",
        )
        self.assertEqual(
            payload["judge_results"]["google/gemini-2.5-flash-preview"][
                "aggregated"
            ]["total_score_mean"],
            90.0,
        )

    async def test_gemini_non_thinking_missing_api_reasoning_still_aggregates(self):
        """AC-002 / AC-005 / DEC-002: Gemini 非 thinking は空 api_reasoning で採点完走"""
        valid_response = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 40,
                    "constraint_adherence": 20,
                    "helpfulness_and_creativity": 10,
                },
                "total_score": 70,
                "confidence": "medium",
            }
        )
        subject_adapter = _StubAdapter(["subject-response"])
        judge_adapter = _StubAdapter([valid_response], reasoning_opt_in=False)
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="subject-model",
            judge_adapters={"google/gemini-2.0-flash-001": judge_adapter},
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        result = await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )
        payload = result.to_dict()
        run = payload["judge_results"]["google/gemini-2.0-flash-001"]["runs"][0]
        self.assertIsNone(judge_adapter.calls[0]["extra_params"])
        self.assertNotIn("api_reasoning", run)
        self.assertEqual(
            payload["judge_results"]["google/gemini-2.0-flash-001"][
                "aggregated"
            ]["total_score_mean"],
            70.0,
        )

    async def test_judge_parse_failure_retries_model_once_and_excludes_failure(self):
        valid_response = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 60,
                    "constraint_adherence": 30,
                    "helpfulness_and_creativity": 10,
                },
                "total_score": 100,
                "confidence": "high",
            }
        )
        subject_adapter = _StubAdapter(["subject-response"])
        judge_adapter = _StubAdapter(["", valid_response])
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="gpt-4o",
            judge_adapters={"judge-model": judge_adapter},
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        result = await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )

        judge_result = result.judge_results["judge-model"]
        self.assertEqual(judge_adapter.call_count, 2)
        self.assertEqual(len(judge_result["runs"]), 1)
        self.assertNotIn("error", judge_result["runs"][0])
        self.assertEqual(judge_result["aggregated"]["total_score_mean"], 100.0)

    async def test_judge_parse_failure_after_retry_is_skipped_not_zero_scored(self):
        valid_response = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 54,
                    "constraint_adherence": 27,
                    "helpfulness_and_creativity": 9,
                },
                "total_score": 90,
                "confidence": "high",
            }
        )
        subject_adapter = _StubAdapter(["subject-response"])
        judge_adapter = _StubAdapter(["", "", valid_response])
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="gpt-4o",
            judge_adapters={"judge-model": judge_adapter},
            judge_runs=2,
            max_parallel_runs_per_judge=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        result = await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )

        judge_result = result.judge_results["judge-model"]
        self.assertEqual(judge_adapter.call_count, 3)
        self.assertTrue(judge_result["runs"][0]["skipped"])
        self.assertEqual(judge_result["aggregated"]["total_score_mean"], 90.0)
        self.assertEqual(
            judge_result["aggregated"]["confidence_distribution"],
            {"high": 1, "medium": 0, "low": 0},
        )

    async def test_cancel_checker_stops_unstarted_judge_runs(self):
        valid_response = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 60,
                    "constraint_adherence": 30,
                    "helpfulness_and_creativity": 10,
                },
                "total_score": 100,
                "confidence": "high",
            }
        )
        subject_adapter = _StubAdapter(["subject-response"])
        judge_adapter = _StubAdapter([valid_response, valid_response, valid_response])
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="gpt-4o",
            judge_adapters={"judge-model": judge_adapter},
            judge_runs=3,
            max_parallel_runs_per_judge=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        cancel_checks = {"count": 0}

        def cancel_checker():
            cancel_checks["count"] += 1
            if cancel_checks["count"] >= 4:
                raise asyncio.CancelledError("cancel test")

        with self.assertRaises(asyncio.CancelledError):
            await engine.run_task(
                task_name="01",
                task_type="fact",
                input_prompt="prompt",
                rubric_content="rubric",
                system_prompt="system",
                cancel_checker=cancel_checker,
            )

        self.assertLess(judge_adapter.call_count, 3)

    async def test_subject_tool_loop_runs_until_final_answer(self):
        valid_response = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 60,
                    "constraint_adherence": 30,
                    "helpfulness_and_creativity": 10,
                },
                "total_score": 100,
                "confidence": "high",
            }
        )
        subject_adapter = _StubAdapter(
            [
                '<tool_call>{"name":"web_search","arguments":{"query":"deep research model updates"}}</tool_call>',
                "結論として、対象期間中に Deep Research の内部モデルは賢くなっていません。",
            ]
        )
        judge_adapter = _StubAdapter([valid_response])
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="gpt-4o",
            judge_adapters={"judge-model": judge_adapter},
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        with tempfile.TemporaryDirectory() as tmp:
            fixture_path = Path(tmp) / "fixture.json"
            fixture_path.write_text(
                json.dumps(
                    {
                        "query_snapshots": [
                            {
                                "query": "deep research model updates",
                                "results": [
                                    {
                                        "rank": 1,
                                        "title": "Deep Research follow-up update",
                                        "url": "https://example.com/1",
                                        "content": "workflow update, model unchanged",
                                    }
                                ],
                            }
                        ],
                        "documents": [
                            {
                                "url": "https://example.com/1",
                                "title": "Deep Research follow-up update",
                                "text": "The workflow changed, but the internal model stayed the same.",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = await engine.run_task(
                task_name="08",
                task_type="fact",
                input_prompt="prompt",
                rubric_content="rubric",
                system_prompt="system",
                subject_tools={
                    "enabled_tools": ["web_search", "fetch_webpage"],
                    "fixture_path": str(fixture_path),
                    "max_steps": 3,
                },
            )

        payload = result.to_dict()
        self.assertEqual(subject_adapter.call_count, 2)
        self.assertEqual(payload["tool_trace"][0]["tool_name"], "web_search")
        self.assertTrue(payload["has_subject_tools"])
        self.assertEqual(payload["subject_usage"]["total_tokens"], 30)
        self.assertIn("賢くなっていません", payload["response"])
        self.assertIn("<untrusted_tool_trace>", judge_adapter.calls[0]["user_prompt"])
        self.assertIn("被験LLMのtool利用", judge_adapter.calls[0]["user_prompt"])
        self.assertIn("tool_call_count: 1", judge_adapter.calls[0]["user_prompt"])
        self.assertIn("tool_step_count: 1", judge_adapter.calls[0]["user_prompt"])
        self.assertIn("tool=web_search", judge_adapter.calls[0]["user_prompt"])

    async def test_native_tool_loop_finalizes_when_tool_budget_is_exhausted(self):
        valid_response = json.dumps(
            {
                "task_name": "test",
                "task_type": "fact",
                "score": {
                    "logic_and_fact": 60,
                    "constraint_adherence": 30,
                    "helpfulness_and_creativity": 10,
                },
                "total_score": 100,
                "confidence": "high",
            }
        )
        subject_adapter = _NativeToolLoopAdapter(
            native_responses=[
                NativeCompletionResult(
                    content=None,
                    tool_calls=[
                        NativeToolCall(
                            id="call_1",
                            name="web_search",
                            arguments={"query": "deep research model updates"},
                        )
                    ],
                ),
                NativeCompletionResult(
                    content=None,
                    tool_calls=[
                        NativeToolCall(
                            id="call_2",
                            name="web_search",
                            arguments={"query": "more deep research updates"},
                        )
                    ],
                ),
            ],
            final_responses=[
                "結論として、収集済みの根拠から回答します。"
            ],
        )
        subject_adapter._reasoning_opt_in = True
        judge_adapter = _StubAdapter([valid_response])
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="deepseek-test",
            judge_adapters={"judge-model": judge_adapter},
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        with tempfile.TemporaryDirectory() as tmp:
            fixture_path = Path(tmp) / "fixture.json"
            fixture_path.write_text(
                json.dumps(
                    {
                        "query_snapshots": [
                            {
                                "query": "deep research model updates",
                                "results": [
                                    {
                                        "rank": 1,
                                        "title": "Deep Research update",
                                        "url": "https://example.com/1",
                                        "content": "internal model unchanged",
                                    }
                                ],
                            }
                        ],
                        "documents": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = await engine.run_task(
                task_name="08",
                task_type="fact",
                input_prompt="prompt",
                rubric_content="rubric",
                system_prompt="system",
                subject_tools={
                    "enabled_tools": ["web_search", "fetch_webpage"],
                    "fixture_path": str(fixture_path),
                    "max_steps": 1,
                    "tool_mode": "native",
                },
            )

        payload = result.to_dict()
        self.assertNotIn("[ERROR] tool step limit exceeded", payload["response"])
        self.assertIn("収集済みの根拠", payload["response"])
        self.assertEqual(len(payload["tool_trace"]), 1)
        self.assertEqual(subject_adapter.native_call_count, 2)
        self.assertTrue(
            all(
                call["extra_params"] == {"reasoning": {"effort": "high"}}
                for call in subject_adapter.native_calls
            )
        )
        self.assertEqual(
            subject_adapter.calls[0]["extra_params"],
            {"reasoning": {"effort": "high"}},
        )

    async def test_holistic_task_result_includes_explicit_empty_subject_prompt(self):
        """holistic は被験 LLM 非呼び出しのため subject_prompt は明示的な空文字。"""
        valid_response = json.dumps(
            {
                "task_name": "style",
                "task_type": "holistic",
                "score": {
                    "logic_and_fact": 40,
                    "constraint_adherence": 30,
                    "helpfulness_and_creativity": 30,
                },
                "total_score": 100,
                "confidence": "high",
            }
        )
        subject_adapter = _StubAdapter([])
        judge_adapter = _StubAdapter([valid_response])
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="unused-subject",
            judge_adapters={"judge-model": judge_adapter},
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        result = await engine.run_holistic_task(
            task_name="style",
            eval_prompt="holistic-eval",
            rubric_content="rubric",
            bundled_responses=[
                {
                    "task_name": "01",
                    "task_type": "fact",
                    "input_prompt": "q",
                    "response": "a",
                }
            ],
            system_prompt="system",
        )
        payload = result.to_dict()

        self.assertIn("subject_prompt", payload)
        self.assertEqual(payload["subject_prompt"], "")
        self.assertEqual(payload["task_type"], "holistic")
        self.assertEqual(payload["input_prompt"], "holistic-eval")
        self.assertEqual(payload["response"], "")
        self.assertEqual(subject_adapter.call_count, 0)
        self.assertIn("bundling_metadata", payload)
        self.assertFalse(payload["bundling_metadata"]["truncated"])
        self.assertEqual(payload["bundling_metadata"]["action"], "none")

    async def test_run_holistic_task_uses_override_judge_adapters(self):
        """DEC-002: judge_adapters override is used instead of engine defaults."""
        valid_response = json.dumps(
            {
                "task_name": "style",
                "task_type": "holistic",
                "score": {
                    "logic_and_fact": 40,
                    "constraint_adherence": 30,
                    "helpfulness_and_creativity": 30,
                },
                "total_score": 100,
                "confidence": "high",
            }
        )
        subject_adapter = _StubAdapter([])
        standard_judge = _StubAdapter([valid_response])
        holistic_judge = _StubAdapter([valid_response])
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="unused-subject",
            judge_adapters={"standard-judge": standard_judge},
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        result = await engine.run_holistic_task(
            task_name="style",
            eval_prompt="holistic-eval",
            rubric_content="rubric",
            bundled_responses=[
                {
                    "task_name": "01",
                    "task_type": "fact",
                    "input_prompt": "q",
                    "response": "a",
                }
            ],
            system_prompt="system",
            judge_adapters={"holistic-judge": holistic_judge},
        )

        self.assertIn("holistic-judge", result.judge_results)
        self.assertNotIn("standard-judge", result.judge_results)
        self.assertEqual(holistic_judge.call_count, 1)
        self.assertEqual(standard_judge.call_count, 0)
        self.assertEqual(subject_adapter.call_count, 0)

    def test_build_bundled_responses_preserves_task_heading_format(self):
        """AC-003 / INV-001: 通常規模では見出しと区切り形式を維持する。"""
        text = BenchmarkEngine._build_bundled_responses(
            [
                {
                    "task_name": "01",
                    "task_type": "fact",
                    "input_prompt": "q1",
                    "response": "a1",
                },
                {
                    "task_name": "02",
                    "task_type": "speculative",
                    "input_prompt": "q2",
                    "response": "a2",
                },
            ]
        )
        self.assertEqual(
            text,
            "### タスク: 01（fact）\n\n"
            "#### 入力プロンプト\nq1\n\n"
            "#### 被験LLMの回答\na1"
            "\n\n---\n\n"
            "### タスク: 02（speculative）\n\n"
            "#### 入力プロンプト\nq2\n\n"
            "#### 被験LLMの回答\na2",
        )

    def test_resolve_judge_context_limit_uses_conservative_default(self):
        """DEC-001: 未知モデルは保守的デフォルトへ落ちる。"""
        self.assertEqual(
            BenchmarkEngine.resolve_judge_context_limit_tokens(
                "openrouter/anthropic/claude-sonnet-5"
            ),
            200_000,
        )
        self.assertEqual(
            BenchmarkEngine.resolve_judge_context_limit_tokens("unknown-local-model"),
            BenchmarkEngine._DEFAULT_CONTEXT_LIMIT_TOKENS,
        )

    def test_fit_bundled_responses_drops_trailing_tasks_first(self):
        """AC-001 / DEC-003: 超過時は末尾 task から drop する。"""
        responses = [
            {
                "task_name": "01",
                "task_type": "fact",
                "input_prompt": "q1",
                "response": "short-a",
            },
            {
                "task_name": "02",
                "task_type": "fact",
                "input_prompt": "q2",
                "response": "short-b",
            },
            {
                "task_name": "03",
                "task_type": "fact",
                "input_prompt": "q3",
                "response": "short-c",
            },
        ]
        full = BenchmarkEngine._build_bundled_responses(responses)
        # 先頭 task だけ残るくらいの予算にする
        first_only = BenchmarkEngine._build_bundled_responses(responses[:1])
        max_chars = len(first_only) + 10
        self.assertLess(max_chars, len(full))

        text, metadata = BenchmarkEngine._fit_bundled_responses_to_budget(
            responses,
            max_chars=max_chars,
            context_limit_tokens=1024,
            overhead_chars=100,
            binding_model="stub",
        )
        self.assertTrue(metadata["truncated"])
        self.assertEqual(metadata["action"], "task_drop")
        self.assertEqual(metadata["dropped_tasks"], ["03", "02"])
        self.assertIn("### タスク: 01（fact）", text)
        self.assertNotIn("### タスク: 02（fact）", text)
        self.assertNotIn("### タスク: 03（fact）", text)
        self.assertLessEqual(len(text), max_chars)

    def test_fit_bundled_responses_truncates_oversized_single_response(self):
        """AC-001: 1 task でも収まらない場合は回答本文のみ truncate する。"""
        huge = "X" * 5000
        responses = [
            {
                "task_name": "01",
                "task_type": "fact",
                "input_prompt": "keep-prompt",
                "response": huge,
            }
        ]
        max_chars = 400
        text, metadata = BenchmarkEngine._fit_bundled_responses_to_budget(
            responses,
            max_chars=max_chars,
            context_limit_tokens=1024,
            overhead_chars=100,
        )
        self.assertTrue(metadata["truncated"])
        self.assertEqual(metadata["action"], "response_truncate")
        self.assertEqual(metadata["dropped_tasks"], [])
        self.assertIn("### タスク: 01（fact）", text)
        self.assertIn("#### 入力プロンプト\nkeep-prompt", text)
        self.assertIn("#### 被験LLMの回答\n", text)
        self.assertIn("...[truncated]", text)
        self.assertNotIn(huge, text)
        self.assertLessEqual(len(text), max_chars)

    async def test_holistic_overflow_records_bundling_metadata_and_bounds_judge_prompt(
        self,
    ):
        """AC-002 / AC-004 / INV-002: overflow 時 metadata を残し oversized prompt を送らない。"""
        valid_response = json.dumps(
            {
                "task_name": "style",
                "task_type": "holistic",
                "score": {
                    "logic_and_fact": 40,
                    "constraint_adherence": 30,
                    "helpfulness_and_creativity": 30,
                },
                "total_score": 100,
                "confidence": "high",
            }
        )
        subject_adapter = _StubAdapter([])
        judge_adapter = _StubAdapter([valid_response])
        engine = BenchmarkEngine(
            subject_adapter=subject_adapter,
            subject_model="unused-subject",
            judge_adapters={"unknown-tiny-judge": judge_adapter},
            judge_runs=1,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )

        oversized_responses = [
            {
                "task_name": f"{index:02d}",
                "task_type": "fact",
                "input_prompt": f"prompt-{index}",
                "response": "R" * 20_000,
            }
            for index in range(1, 6)
        ]
        raw_bundle = BenchmarkEngine._build_bundled_responses(oversized_responses)

        with patch.object(
            engine,
            "_resolve_holistic_context_limit",
            return_value=(8192, "unknown-tiny-judge"),
        ):
            result = await engine.run_holistic_task(
                task_name="style",
                eval_prompt="holistic-eval-prompt",
                rubric_content="rubric-body",
                bundled_responses=oversized_responses,
                system_prompt="system-prompt",
            )
        payload = result.to_dict()
        metadata = payload["bundling_metadata"]

        self.assertTrue(metadata["truncated"])
        self.assertIn(metadata["action"], ("task_drop", "response_truncate"))
        self.assertGreater(metadata["estimated_chars_before"], metadata["estimated_chars_after"])
        self.assertLessEqual(
            metadata["estimated_chars_after"],
            metadata["answer_budget_chars"],
        )
        self.assertEqual(judge_adapter.call_count, 1)
        user_prompt = judge_adapter.calls[0]["user_prompt"]
        self.assertNotIn(raw_bundle, user_prompt)
        self.assertLess(len(user_prompt), len(raw_bundle))
        # context length exceeded 相当の error だけで終わっていない
        self.assertNotIn("error", payload["judge_results"]["unknown-tiny-judge"])
        self.assertIsNotNone(
            payload["judge_results"]["unknown-tiny-judge"]["aggregated"]
        )


def _valid_judge_json() -> str:
    return json.dumps(
        {
            "task_name": "test",
            "task_type": "fact",
            "score": {
                "logic_and_fact": 60,
                "constraint_adherence": 30,
                "helpfulness_and_creativity": 10,
            },
            "total_score": 100,
            "confidence": "high",
            "critical_fail": False,
            "critical_fail_reason": None,
            "reasoning": {
                "logic_and_fact": "ok",
                "constraint_adherence": "ok",
                "helpfulness_and_creativity": "ok",
            },
        }
    )


class TestSubjectMultiRunJudgeBatch(unittest.IsolatedAsyncioTestCase):
    def test_clamp_subject_runs(self):
        self.assertEqual(BenchmarkEngine.clamp_subject_runs(0), 1)
        self.assertEqual(BenchmarkEngine.clamp_subject_runs(3), 3)
        self.assertEqual(BenchmarkEngine.clamp_subject_runs(99), 5)
        self.assertEqual(BenchmarkEngine.clamp_subject_runs(-2), 1)

    def test_build_bundled_subject_runs_single_is_plain_response(self):
        text = BenchmarkEngine._build_bundled_subject_runs(
            [{"run_index": 1, "response": "only-one"}]
        )
        self.assertEqual(text, "only-one")
        self.assertNotIn("被験試行", text)

    def test_build_bundled_subject_runs_multi_lists_runs(self):
        text = BenchmarkEngine._build_bundled_subject_runs(
            [
                {"run_index": 1, "response": "alpha"},
                {"run_index": 2, "response": "[ERROR] boom", "error": "boom"},
                {"run_index": 3, "response": "gamma"},
            ]
        )
        self.assertIn("### 被験試行 #1\nalpha", text)
        self.assertIn("### 被験試行 #2\n[ERROR] boom", text)
        self.assertIn("### 被験試行 #3\ngamma", text)
        self.assertIn("---", text)

    def test_subject_bundler_is_separate_from_holistic_bundler(self):
        # intent-invariant: INV-002 — 関数を共有せず、見出し語彙も異なる
        subject_text = BenchmarkEngine._build_bundled_subject_runs(
            [
                {"run_index": 1, "response": "a"},
                {"run_index": 2, "response": "b"},
            ]
        )
        holistic_text = BenchmarkEngine._build_bundled_responses(
            [
                {
                    "task_name": "01",
                    "task_type": "fact",
                    "input_prompt": "p",
                    "response": "a",
                },
                {
                    "task_name": "02",
                    "task_type": "fact",
                    "input_prompt": "p",
                    "response": "b",
                },
            ]
        )
        self.assertIn("被験試行", subject_text)
        self.assertNotIn("### タスク:", subject_text)
        self.assertIn("### タスク:", holistic_text)
        self.assertNotIn("被験試行", holistic_text)

    def test_build_bundled_subject_runs_extreme_length_does_not_raise(self):
        huge = "x" * 200_000
        text = BenchmarkEngine._build_bundled_subject_runs(
            [
                {"run_index": 1, "response": huge},
                {"run_index": 2, "response": huge},
                {"run_index": 3, "response": huge},
            ]
        )
        self.assertGreater(len(text), 500_000)
        self.assertIn("被験試行 #3", text)

    async def test_subject_runs_n_batches_to_one_judge_input(self):
        valid = _valid_judge_json()
        subject = _StubAdapter(["run-a", "run-b", "run-c"])
        judge = _StubAdapter([valid, valid])
        engine = BenchmarkEngine(
            subject_adapter=subject,
            subject_model="stub-model",
            judge_adapters={"judge-model": judge},
            judge_runs=2,
            subject_runs=3,
            judge_dispatch_min_interval_sec=0.0,
            judge_dispatch_jitter_sec=0.0,
        )
        result = await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )
        payload = result.to_dict()

        self.assertEqual(subject.call_count, 3)
        # INV-001: judge outer calls = judge_runs (not × subject_runs)
        self.assertEqual(judge.call_count, 2)
        self.assertEqual(payload["subject_run_count"], 3)
        self.assertEqual(len(payload["subject_runs"]), 3)
        self.assertEqual(payload["response"], "run-a")
        user_prompt = judge.calls[0]["user_prompt"]
        self.assertIn("### 被験試行 #1\nrun-a", user_prompt)
        self.assertIn("### 被験試行 #2\nrun-b", user_prompt)
        self.assertIn("### 被験試行 #3\nrun-c", user_prompt)

    async def test_subject_runs_one_keeps_plain_judge_answer(self):
        valid = _valid_judge_json()
        subject = _StubAdapter(["solo"])
        judge = _StubAdapter([valid])
        engine = BenchmarkEngine(
            subject_adapter=subject,
            subject_model="stub-model",
            judge_adapters={"judge-model": judge},
            judge_runs=1,
            subject_runs=1,
        )
        result = await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )
        payload = result.to_dict()
        self.assertEqual(payload["response"], "solo")
        self.assertEqual(payload["subject_run_count"], 1)
        self.assertEqual(len(payload["subject_runs"]), 1)
        user_prompt = judge.calls[0]["user_prompt"]
        self.assertIn("<untrusted_subject_answer>\nsolo\n</untrusted_subject_answer>", user_prompt)
        self.assertNotIn("被験試行", user_prompt)

    async def test_partial_subject_failure_includes_error_and_continues(self):
        from adapters import LLMError

        valid = _valid_judge_json()

        class FlakySubject(_StubAdapter):
            def complete_with_model_result(
                self,
                model,
                system_prompt,
                user_prompt,
                temperature=0.0,
                max_tokens=1024,
                extra_params=None,
            ):
                self.call_count += 1
                self.calls.append(
                    {
                        "model": model,
                        "system_prompt": system_prompt,
                        "user_prompt": user_prompt,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "extra_params": extra_params,
                    }
                )
                if self.call_count == 2:
                    raise LLMError("mid-fail")
                if self._responses:
                    item = self._responses.pop(0)
                else:
                    item = ""
                if isinstance(item, CompletionResult):
                    return item
                return CompletionResult(
                    text=item,
                    usage=UsageMetrics(
                        provider=self.PROVIDER,
                        model=model,
                        input_tokens=10,
                        output_tokens=5,
                        total_tokens=15,
                        duration_ms=100,
                    ),
                )

        subject = FlakySubject(["ok-1", "ok-3"])
        judge = _StubAdapter([valid])
        engine = BenchmarkEngine(
            subject_adapter=subject,
            subject_model="stub-model",
            judge_adapters={"judge-model": judge},
            judge_runs=1,
            subject_runs=3,
        )
        result = await engine.run_task(
            task_name="01",
            task_type="fact",
            input_prompt="prompt",
            rubric_content="rubric",
            system_prompt="system",
        )
        payload = result.to_dict()
        self.assertEqual(judge.call_count, 1)
        self.assertEqual(payload["subject_runs"][1]["error"], "mid-fail")
        self.assertTrue(payload["subject_runs"][1]["response"].startswith("[ERROR]"))
        user_prompt = judge.calls[0]["user_prompt"]
        self.assertIn("[ERROR] mid-fail", user_prompt)
        self.assertIn("ok-1", user_prompt)
        self.assertIn("ok-3", user_prompt)

    async def test_all_subject_failures_raise_when_n_gt_one(self):
        from adapters import LLMError

        class AlwaysFail(_StubAdapter):
            def complete_with_model_result(self, *args, **kwargs):
                self.call_count += 1
                raise LLMError("dead")

        engine = BenchmarkEngine(
            subject_adapter=AlwaysFail([]),
            subject_model="stub-model",
            judge_adapters={"judge-model": _StubAdapter([_valid_judge_json()])},
            judge_runs=1,
            subject_runs=2,
        )
        with self.assertRaises(LLMError) as ctx:
            await engine.run_task(
                task_name="01",
                task_type="fact",
                input_prompt="prompt",
                rubric_content="rubric",
                system_prompt="system",
            )
        self.assertIn("全 2 回失敗", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
