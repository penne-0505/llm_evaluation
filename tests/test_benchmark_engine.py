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
            text = self._responses.pop(0)
        else:
            text = ""
        return CompletionResult(
            text=text,
            usage=UsageMetrics(
                provider=self.PROVIDER,
                model=model,
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
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
        self.assertEqual(
            payload["judge_results"]["judge-model"]["runs"][0]["usage"][
                "output_tokens"
            ],
            5,
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


if __name__ == "__main__":
    unittest.main()
