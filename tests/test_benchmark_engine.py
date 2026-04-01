"""BenchmarkEngine の並列・失敗制御テスト"""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from adapters import CompletionResult, LLMAdapter, UsageMetrics
from core.benchmark_engine import BenchmarkEngine


class _StubAdapter(LLMAdapter):
    def __init__(self, responses):
        self._responses = list(responses)
        self.call_count = 0
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
    ) -> CompletionResult:
        self.call_count += 1
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


class TestBenchmarkEngine(unittest.IsolatedAsyncioTestCase):
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

        self.assertEqual(judge_adapter.call_count, 2)
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
                '<tool_call>{"name":"web-search","arguments":{"query":"deep research model updates"}}</tool_call>',
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
                                        "doc_id": "doc-1",
                                        "title": "Deep Research follow-up update",
                                        "url": "https://example.com/1",
                                        "content": "workflow update, model unchanged",
                                    }
                                ],
                            }
                        ],
                        "documents": [
                            {
                                "id": "doc-1",
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
                    "enabled_tools": ["web-search", "open-document"],
                    "fixture_path": str(fixture_path),
                    "max_steps": 3,
                },
            )

        payload = result.to_dict()
        self.assertEqual(subject_adapter.call_count, 2)
        self.assertEqual(payload["tool_trace"][0]["tool_name"], "web-search")
        self.assertEqual(payload["subject_usage"]["total_tokens"], 30)
        self.assertIn("賢くなっていません", payload["response"])


if __name__ == "__main__":
    unittest.main()
