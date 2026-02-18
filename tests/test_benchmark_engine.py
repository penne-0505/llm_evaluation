"""BenchmarkEngine の並列・失敗制御テスト"""

import json
import unittest
from unittest.mock import AsyncMock, patch

from adapters import LLMAdapter
from core.benchmark_engine import BenchmarkEngine


class _StubAdapter(LLMAdapter):
    def __init__(self, responses):
        self._responses = list(responses)
        self.call_count = 0

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
        self.call_count += 1
        if self._responses:
            return self._responses.pop(0)
        return ""


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


if __name__ == "__main__":
    unittest.main()
