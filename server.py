"""FastAPI バックエンドサーバー

core/ と adapters/ を HTTP API として公開する。
Streamlit 依存は一切持たない。
"""

from __future__ import annotations

import asyncio
import json
import os
import queue as _queue
import time
import traceback
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from adapters import get_adapter_for_model, get_available_judge_adapters
from core import BenchmarkEngine, ResultStorage
from core.model_catalog import ModelCatalog
from core.secrets_store import SecretsStore
from core.selection_store import SelectionStore

load_dotenv()

app = FastAPI(title="LLM Benchmark API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 定数・ヘルパー
# ---------------------------------------------------------------------------

RUBRICS_DIR_ENV = "LLM_BENCHMARK_RUBRICS_DIR"
PROMPTS_DIR_ENV = "LLM_BENCHMARK_PROMPTS_DIR"
JUDGE_SYSTEM_PROMPT_ENV = "LLM_BENCHMARK_JUDGE_SYSTEM_PROMPT_PATH"

# 実行中のキャンセルフラグ（run_id → bool）
_cancel_flags: Dict[str, bool] = {}


def _resolve_rubrics_dir() -> Path:
    env = os.getenv(RUBRICS_DIR_ENV)
    if env:
        p = Path(env)
        if p.exists() and p.is_dir():
            return p
    return Path("rubrics")


def _resolve_prompts_dir() -> Path:
    env = os.getenv(PROMPTS_DIR_ENV)
    if env:
        p = Path(env)
        if p.exists() and p.is_dir():
            return p
    return Path("prompts")


def _resolve_judge_system_prompt_path() -> Path:
    env = os.getenv(JUDGE_SYSTEM_PROMPT_ENV)
    if env:
        p = Path(env)
        if p.exists() and p.is_file():
            return p
    return Path("judge_system_prompt.md")


def _load_tasks() -> List[Dict[str, str]]:
    rubrics_dir = _resolve_rubrics_dir()
    prompts_dir = _resolve_prompts_dir()
    tasks: List[Dict[str, str]] = []

    if not rubrics_dir.exists() or not prompts_dir.exists():
        return tasks

    for rubric_file in sorted(rubrics_dir.glob("*.md")):
        task_id = rubric_file.stem
        prompt_file = prompts_dir / f"{task_id}.md"
        if not prompt_file.exists():
            continue

        task_type = "fact"
        try:
            content = rubric_file.read_text(encoding="utf-8")
            for line in content.split("\n"):
                if "task_type:" in line.lower():
                    if "speculative" in line.lower():
                        task_type = "speculative"
                    elif "creative" in line.lower():
                        task_type = "creative"
                    break
        except Exception:
            pass

        tasks.append(
            {
                "id": task_id,
                "rubric_file": str(rubric_file),
                "prompt_file": str(prompt_file),
                "type": task_type,
            }
        )

    return tasks


def _resolve_subject_key(model_name: str, api_keys: Dict[str, str]) -> Optional[str]:
    model_lower = model_name.lower()
    if any(model_lower.startswith(p) for p in ["gpt-", "o1", "o3", "o4"]):
        return api_keys.get("openai")
    if model_lower.startswith("claude-"):
        return api_keys.get("anthropic")
    if model_lower.startswith("gemini-"):
        return api_keys.get("gemini")
    if any(model_lower.startswith(p) for p in ["openrouter/", "or/"]):
        return api_keys.get("openrouter")
    return None


def _sse_event(data: Any) -> str:
    """SSE フォーマットに変換"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _extract_judge_model(message: str) -> str:
    """progress_callback の message から judge モデル名を抽出する"""
    # "judge claude-3.5-sonnet 評価1/3開始" のようなパターン
    if "judge " in message:
        after = message.split("judge ", 1)[1]
        # 空白または " 評価" の手前まで
        for sep in [" 評価", " エラー", " "]:
            if sep in after:
                return after.split(sep, 1)[0]
        return after.strip()
    return ""


# ---------------------------------------------------------------------------
# Pydantic モデル
# ---------------------------------------------------------------------------


class ApiKeySaveRequest(BaseModel):
    openai: Optional[str] = None
    anthropic: Optional[str] = None
    gemini: Optional[str] = None
    openrouter: Optional[str] = None


class ApiKeyClearRequest(BaseModel):
    openai: bool = False
    anthropic: bool = False
    gemini: bool = False
    openrouter: bool = False


class SelectionSaveRequest(BaseModel):
    target_model: Optional[str] = None
    judge_models: List[str] = []
    judge_runs: int = 1
    subject_temp: float = 0.6
    selected_tasks: List[str] = []


class RunRequest(BaseModel):
    target_model: str
    judge_models: List[str]
    selected_task_ids: List[str]
    judge_runs: int = 3
    subject_temp: float = 0.6


# ---------------------------------------------------------------------------
# エンドポイント: タスク
# ---------------------------------------------------------------------------


@app.get("/api/tasks")
def get_tasks() -> List[Dict[str, str]]:
    """利用可能なタスク一覧を返す（prompt 付き）"""
    tasks = _load_tasks()
    result = []
    for t in tasks:
        prompt = ""
        try:
            prompt = Path(t["prompt_file"]).read_text(encoding="utf-8")
        except Exception:
            pass
        result.append({"id": t["id"], "type": t["type"], "prompt": prompt})
    return result


# ---------------------------------------------------------------------------
# エンドポイント: APIキー管理
# ---------------------------------------------------------------------------


@app.get("/api/keys/status")
def get_keys_status() -> Dict[str, Any]:
    """各プロバイダーのAPIキー設定状況を返す"""
    existing = SecretsStore.load_existing()
    return {
        provider: bool(existing.get(provider))
        for provider in ["openai", "anthropic", "gemini", "openrouter"]
    }


@app.post("/api/keys")
def save_keys(req: ApiKeySaveRequest) -> Dict[str, str]:
    """APIキーを保存する"""
    values = req.model_dump()
    if not any(values.values()):
        raise HTTPException(status_code=400, detail="APIキーが入力されていません")
    SecretsStore.save(values)
    load_dotenv(override=True)
    return {"status": "ok"}


@app.delete("/api/keys")
def clear_keys(req: ApiKeyClearRequest) -> Dict[str, str]:
    """指定プロバイダーのAPIキーを削除する"""
    providers = req.model_dump()
    if not any(providers.values()):
        raise HTTPException(
            status_code=400, detail="削除するプロバイダを選択してください"
        )
    SecretsStore.clear(providers)
    load_dotenv(override=True)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# エンドポイント: モデルカタログ
# ---------------------------------------------------------------------------


@app.get("/api/models")
def get_models(force: bool = False) -> Dict[str, Any]:
    """利用可能なモデル一覧を返す"""
    catalog = ModelCatalog.update(force=force)
    return catalog


# ---------------------------------------------------------------------------
# エンドポイント: 選択状態の永続化
# ---------------------------------------------------------------------------


@app.get("/api/selection")
def get_selection() -> Dict[str, Any]:
    """前回の選択状態を返す"""
    return SelectionStore.load()


@app.post("/api/selection")
def save_selection(req: SelectionSaveRequest) -> Dict[str, str]:
    """現在の選択状態を保存する"""
    SelectionStore.save(req.model_dump())
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# エンドポイント: ベンチマーク実行 (SSE)
# ---------------------------------------------------------------------------


@app.post("/api/run")
async def run_benchmark(req: RunRequest) -> StreamingResponse:
    """
    ベンチマーク評価を実行し、進捗を SSE でストリームする。

    イベント種別:
      {"type": "progress", "message": str, "current": int, "total": int}
      {"type": "complete", "result": {...}, "saved_path": str}
      {"type": "cancelled", "completed_tasks": int, "total_tasks": int}
      {"type": "error", "message": str, "traceback": str}
    """
    run_id = f"{time.strftime('%Y%m%d_%H%M%S')}_{req.target_model}"
    _cancel_flags[run_id] = False

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            yield _sse_event({"type": "run_id", "run_id": run_id})

            all_tasks = _load_tasks()
            task_map = {t["id"]: t for t in all_tasks}
            selected = [
                task_map[tid] for tid in req.selected_task_ids if tid in task_map
            ]

            if not selected:
                yield _sse_event(
                    {
                        "type": "error",
                        "message": "有効なタスクが選択されていません",
                        "traceback": "",
                    }
                )
                return

            api_keys = SecretsStore.load_existing()

            subject_adapter = get_adapter_for_model(
                req.target_model,
                api_key=_resolve_subject_key(req.target_model, api_keys),
            )
            if subject_adapter is None or not subject_adapter.is_available():
                yield _sse_event(
                    {
                        "type": "error",
                        "message": f"モデル '{req.target_model}' のアダプタまたはAPIキーが見つかりません",
                        "traceback": "",
                    }
                )
                return

            judge_adapters = get_available_judge_adapters(
                req.judge_models, api_keys=api_keys
            )
            if not judge_adapters:
                yield _sse_event(
                    {
                        "type": "error",
                        "message": "judgeモデルに対応するAPIキーがありません",
                        "traceback": "",
                    }
                )
                return

            judge_system_prompt_path = _resolve_judge_system_prompt_path()
            system_prompt = (
                judge_system_prompt_path.read_text(encoding="utf-8")
                if judge_system_prompt_path.exists()
                else ""
            )

            engine = BenchmarkEngine(
                subject_adapter=subject_adapter,
                subject_model=req.target_model,
                judge_adapters=judge_adapters,
                judge_runs=req.judge_runs,
                max_parallel_judges=5,
                judge_fail_fast_threshold=2,
                max_parallel_runs_per_judge=3,
                judge_dispatch_min_interval_sec=0.25,
                judge_dispatch_jitter_sec=0.15,
            )

            total_tasks = len(selected)
            total_steps = total_tasks * (1 + len(judge_adapters) * (req.judge_runs + 2))
            progress_current = 0

            # SSE 送信用キュー（非同期コールバック → イベントストリームへ）
            progress_queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()

            def progress_callback(
                message: str,
                *,
                task_index: int = 0,
                task_id: str = "",
                judge_model: str = "",
            ) -> None:
                nonlocal progress_current
                progress_current += 1
                progress_queue.put_nowait(
                    {
                        "type": "progress",
                        "message": message,
                        "current": progress_current,
                        "total": total_steps,
                        "task_index": task_index,
                        "task_id": task_id,
                        "judge_model": judge_model,
                    }
                )

            def cancel_checker() -> None:
                if _cancel_flags.get(run_id):
                    raise asyncio.CancelledError("ユーザーによってキャンセルされました")

            # 評価を別タスクで実行
            task_results: List[Optional[Dict[str, Any]]] = [None] * total_tasks
            cancelled = False
            cancel_reason = ""

            task_semaphore = asyncio.Semaphore(3)

            async def _run_single_task(idx: int, task_info: Dict[str, str]) -> None:
                async with task_semaphore:
                    cancel_checker()
                    rubric_content = Path(task_info["rubric_file"]).read_text(
                        encoding="utf-8"
                    )
                    input_prompt = Path(task_info["prompt_file"]).read_text(
                        encoding="utf-8"
                    )
                    cancel_checker()

                    result = await engine.run_task(
                        task_name=task_info["id"],
                        task_type=task_info["type"],
                        input_prompt=input_prompt,
                        rubric_content=rubric_content,
                        system_prompt=system_prompt,
                        subject_temp=req.subject_temp,
                        progress_callback=lambda msg, _idx=idx, _tid=task_info["id"]: (
                            progress_callback(
                                f"タスク {_idx + 1}/{total_tasks}: {msg}",
                                task_index=_idx,
                                task_id=_tid,
                                judge_model=_extract_judge_model(msg),
                            )
                        ),
                        cancel_checker=cancel_checker,
                    )
                    task_results[idx] = result.to_dict()

            futures = [
                asyncio.create_task(_run_single_task(i, task))
                for i, task in enumerate(selected)
            ]

            async def _drain_queue_until_done() -> None:
                """評価タスク完了まで進捗キューをフラッシュし続ける"""
                nonlocal cancelled, cancel_reason
                try:
                    done, pending = await asyncio.wait(
                        futures, return_when=asyncio.ALL_COMPLETED
                    )
                except asyncio.CancelledError:
                    pass

            drain_task = asyncio.create_task(_drain_queue_until_done())

            # メインループ: 進捗をクライアントへ送りながら完了を待つ
            try:
                while not drain_task.done() or not progress_queue.empty():
                    try:
                        event = progress_queue.get_nowait()
                        yield _sse_event(event)
                    except _queue.Empty:
                        await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                cancelled = True
                cancel_reason = "ユーザーによってキャンセルされました"
                for f in futures:
                    f.cancel()
                await asyncio.gather(*futures, return_exceptions=True)

            # キューの残りをフラッシュ
            while not progress_queue.empty():
                try:
                    event = progress_queue.get_nowait()
                    yield _sse_event(event)
                except _queue.Empty:
                    break

            # キャンセルフラグが立っていたらタスクを停止
            if not cancelled and _cancel_flags.get(run_id):
                cancelled = True
                cancel_reason = "ユーザーによってキャンセルされました"
                for f in futures:
                    f.cancel()
                await asyncio.gather(*futures, return_exceptions=True)

            completed = [r for r in task_results if r is not None]

            if cancelled:
                yield _sse_event(
                    {
                        "type": "cancelled",
                        "completed_tasks": len(completed),
                        "total_tasks": total_tasks,
                        "reason": cancel_reason,
                    }
                )
                return

            # 結果構築・保存
            benchmark_result = {
                "run_id": run_id,
                "target_model": req.target_model,
                "judge_models": req.judge_models,
                "judge_runs": req.judge_runs,
                "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "tasks": completed,
                "cancelled": False,
                "completed_tasks": len(completed),
                "total_tasks": total_tasks,
            }

            # average_score / best_score を計算して付与
            all_total_scores: List[float] = []
            for task_data in completed:
                jr = task_data.get("judge_results", {})
                for judge_result in jr.values():
                    agg = judge_result.get("aggregated")
                    if agg:
                        ts = agg.get("total_score_mean", 0)
                        if ts:
                            all_total_scores.append(float(ts))
            benchmark_result["average_score"] = (
                round(sum(all_total_scores) / len(all_total_scores), 1)
                if all_total_scores
                else 0
            )
            benchmark_result["best_score"] = (
                round(max(all_total_scores), 1) if all_total_scores else 0
            )

            saved_path = ResultStorage.save(benchmark_result)

            yield _sse_event(
                {
                    "type": "complete",
                    "result": benchmark_result,
                    "saved_path": str(saved_path),
                }
            )

        except Exception as e:
            yield _sse_event(
                {
                    "type": "error",
                    "message": str(e),
                    "traceback": traceback.format_exc(),
                }
            )
        finally:
            _cancel_flags.pop(run_id, None)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/run/cancel")
async def cancel_run(run_id: str) -> Dict[str, str]:
    """実行中のベンチマークをキャンセルする"""
    if run_id not in _cancel_flags:
        raise HTTPException(
            status_code=404, detail="指定された run_id が見つかりません"
        )
    _cancel_flags[run_id] = True
    return {"status": "cancel_requested"}


# ---------------------------------------------------------------------------
# エンドポイント: 評価結果
# ---------------------------------------------------------------------------


@app.get("/api/results")
def list_results() -> List[Dict[str, Any]]:
    """評価結果のサマリー一覧を返す（新しい順）。run_id を付与する。"""
    try:
        summaries = ResultStorage.list_summaries()
        needs_reindex = False
        for s in summaries:
            # 古いキャッシュに欠落しているフィールドを結果ファイルから補完
            missing_run_id = "run_id" not in s
            missing_scores = "max_score" not in s or "min_score" not in s
            if missing_run_id or missing_scores:
                filename = s.get("filename", "")
                if filename:
                    try:
                        filepath = ResultStorage.RESULTS_DIR / filename
                        if filepath.exists():
                            data = ResultStorage.load(filepath)
                            if missing_run_id:
                                s["run_id"] = data.get("run_id", filepath.stem)
                            if missing_scores:
                                # _build_summary と同じロジックでスコアを再計算
                                tasks = data.get("tasks", [])
                                total_scores = []
                                for task in tasks:
                                    for result in task.get(
                                        "judge_results", {}
                                    ).values():
                                        agg = result.get("aggregated")
                                        if agg:
                                            total_scores.append(
                                                agg.get("total_score_mean", 0)
                                            )
                                s["max_score"] = (
                                    max(total_scores) if total_scores else 0
                                )
                                s["min_score"] = (
                                    min(total_scores) if total_scores else 0
                                )
                                needs_reindex = True
                        else:
                            if missing_run_id:
                                s["run_id"] = Path(filename).stem
                            if missing_scores:
                                s.setdefault("max_score", 0)
                                s.setdefault("min_score", 0)
                    except Exception:
                        if missing_run_id:
                            s["run_id"] = Path(filename).stem
                        if missing_scores:
                            s.setdefault("max_score", 0)
                            s.setdefault("min_score", 0)
            # スコアを小数1桁に丸める
            s["avg_score"] = round(s.get("avg_score", 0), 1)
            s["max_score"] = round(s.get("max_score", 0), 1)
            s["min_score"] = round(s.get("min_score", 0), 1)
        # キャッシュに欠落があった場合、再保存して次回以降は高速に
        if needs_reindex:
            try:
                ResultStorage._save_index(summaries)
            except Exception:
                pass
        return summaries
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"履歴の読み込みに失敗しました: {e}"
        )


@app.get("/api/results/{filename}")
def get_result(filename: str) -> Dict[str, Any]:
    """指定ファイルの評価結果詳細を返す"""
    filepath = ResultStorage.RESULTS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="結果ファイルが見つかりません")
    try:
        return ResultStorage.load(filepath)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"結果の読み込みに失敗しました: {e}"
        )
