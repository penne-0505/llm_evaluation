"""FastAPI バックエンドサーバー

core/ と adapters/ を HTTP API として公開する。
Streamlit 依存は一切持たない。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import traceback
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from adapters import (
    get_adapter_for_model,
    get_available_judge_adapters,
    resolve_api_key_for_model,
)
from core import BenchmarkEngine, GroundingCorpusStore, ResultStorage
from core.app_paths import AppPaths
from core.cost_estimator import (
    summarize_benchmark_usage,
    summarize_judge_usage,
    summarize_subject_usage,
    summarize_task_timing,
)
from core.judge_reliability import compute_score_aggregation
from core.logging_utils import configure_logging
from core.progress_eta import compute_progress_eta as _compute_progress_eta_core
from core.model_catalog import ModelCatalog
from core.openrouter_admin import OpenRouterAdminError, fetch_credits
from core.provider_config_store import ProviderConfigStore
from core.provider_registry import ProviderEntry, ProviderRegistry
from core.secrets_store import SecretsStore
from core.selection_store import SelectionStore
from core.strict_mode import (
    build_strict_mode_metadata,
    get_official_strict_preset,
)

load_dotenv()
LOG_FILE_PATH = configure_logging()

logger = logging.getLogger(__name__)

_registry_bootstrapped = False


def _bootstrap_provider_registry() -> None:
    """起動時に builtin seed と secrets 写像を確保する。"""
    global _registry_bootstrapped
    if _registry_bootstrapped:
        return
    # intent: DEC-010/008 — seed + OPENROUTER 等の aliases
    ProviderRegistry.list_providers()
    SecretsStore.ensure_builtin_secret_aliases()
    _registry_bootstrapped = True


@asynccontextmanager
async def _app_lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    _bootstrap_provider_registry()
    yield


app = FastAPI(title="LLM Benchmark API", version="1.0.0", lifespan=_app_lifespan)

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


@dataclass(frozen=True)
class ResourceCandidate:
    path: Path
    source: str


@dataclass(frozen=True)
class ResolvedResource:
    path: Path
    source: str


def _resolve_path_override(env_name: str, *, kind: str) -> Optional[Path]:
    raw = os.getenv(env_name)
    if not raw:
        return None

    path = Path(raw).expanduser()
    is_valid = path.is_dir() if kind == "dir" else path.is_file()
    if is_valid:
        return path

    logger.warning("Ignoring invalid %s override: %s", env_name, path)
    return None


def _directory_candidates(
    *,
    env_name: str,
    user_dir: Path,
    bundled_dir: Path,
) -> List[ResourceCandidate]:
    candidates: List[ResourceCandidate] = []
    env_path = _resolve_path_override(env_name, kind="dir")
    if env_path is not None:
        candidates.append(ResourceCandidate(env_path, "env_override"))
    candidates.append(ResourceCandidate(user_dir, "user_override"))
    candidates.append(ResourceCandidate(bundled_dir, "bundled"))
    return candidates


def _file_candidates(
    *,
    env_name: str,
    user_file: Path,
    bundled_file: Path,
) -> List[ResourceCandidate]:
    candidates: List[ResourceCandidate] = []
    env_path = _resolve_path_override(env_name, kind="file")
    if env_path is not None:
        candidates.append(ResourceCandidate(env_path, "env_override"))
    candidates.append(ResourceCandidate(user_file, "user_override"))
    candidates.append(ResourceCandidate(bundled_file, "bundled"))
    return candidates


def _resolve_candidate_file(
    candidates: List[ResourceCandidate],
    filename: Optional[str] = None,
) -> ResolvedResource:
    fallback: Optional[Path] = None
    for candidate in candidates:
        current = candidate.path if filename is None else candidate.path / filename
        fallback = current
        if current.is_file():
            return ResolvedResource(current, candidate.source)

    return ResolvedResource(fallback or Path(filename or "."), "missing")


def _rubrics_candidates() -> List[ResourceCandidate]:
    return _directory_candidates(
        env_name=RUBRICS_DIR_ENV,
        user_dir=AppPaths.rubrics_override_dir(),
        bundled_dir=AppPaths.bundled_rubrics_dir(),
    )


def _prompts_candidates() -> List[ResourceCandidate]:
    return _directory_candidates(
        env_name=PROMPTS_DIR_ENV,
        user_dir=AppPaths.prompts_override_dir(),
        bundled_dir=AppPaths.bundled_prompts_dir(),
    )


def _holistic_rubrics_candidates() -> List[ResourceCandidate]:
    return _directory_candidates(
        env_name="LLM_BENCHMARK_HOLISTIC_RUBRICS_DIR",
        user_dir=AppPaths.holistic_rubrics_override_dir(),
        bundled_dir=AppPaths.bundled_holistic_rubrics_dir(),
    )


def _holistic_prompts_candidates() -> List[ResourceCandidate]:
    return _directory_candidates(
        env_name="LLM_BENCHMARK_HOLISTIC_PROMPTS_DIR",
        user_dir=AppPaths.holistic_prompts_override_dir(),
        bundled_dir=AppPaths.bundled_holistic_prompts_dir(),
    )


def _judge_system_prompt_candidates() -> List[ResourceCandidate]:
    return _file_candidates(
        env_name=JUDGE_SYSTEM_PROMPT_ENV,
        user_file=AppPaths.judge_system_prompt_override_file(),
        bundled_file=AppPaths.bundled_judge_system_prompt_file(),
    )


def _resolve_rubric_file(filename: str) -> ResolvedResource:
    return _resolve_candidate_file(_rubrics_candidates(), filename)


def _resolve_prompt_file(filename: str) -> ResolvedResource:
    return _resolve_candidate_file(_prompts_candidates(), filename)


def _resolve_judge_system_prompt_resource() -> ResolvedResource:
    return _resolve_candidate_file(_judge_system_prompt_candidates())


def _load_task_config(task_id: str) -> Dict[str, Any]:
    config_path = AppPaths.bundled_task_configs_dir() / f"{task_id}.json"
    if not config_path.is_file():
        return {}

    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    subject_tools = data.get("subject_tools")
    if isinstance(subject_tools, dict):
        fixture_path = subject_tools.get("fixture_path")
        if isinstance(fixture_path, str) and fixture_path.strip():
            subject_tools = dict(subject_tools)
            subject_tools["fixture_path"] = str(AppPaths.runtime_root() / fixture_path)
            data = dict(data)
            data["subject_tools"] = subject_tools

    return data


def _serialize_candidates(candidates: List[ResourceCandidate]) -> List[Dict[str, Any]]:
    return [
        {
            "source": candidate.source,
            "path": str(candidate.path),
            "exists": candidate.path.exists(),
        }
        for candidate in candidates
    ]


def get_runtime_diagnostics() -> Dict[str, Any]:
    rubrics_candidates = _rubrics_candidates()
    prompts_candidates = _prompts_candidates()
    judge_resource = _resolve_judge_system_prompt_resource()
    frontend_index = _frontend_dist_dir() / "index.html"
    tasks = _load_tasks()

    issues: List[str] = []
    if not frontend_index.is_file():
        issues.append(
            "frontend/dist/index.html が見つかりません。開発環境では `npm run build --prefix frontend` を実行し、配布 ZIP では再展開してください。"
        )
    if not tasks:
        issues.append(
            "有効な task が 0 件です。prompt/rubric の同梱漏れ、または override 設定を確認してください。"
        )
    if not judge_resource.path.is_file():
        issues.append(
            "judge_system_prompt.md が見つかりません。配布 ZIP の再展開、または override 設定を確認してください。"
        )

    return {
        "issues": issues,
        "frontend": {
            "dist_dir": str(_frontend_dist_dir()),
            "index_exists": frontend_index.is_file(),
        },
        "resources": {
            "rubrics": {"layers": _serialize_candidates(rubrics_candidates)},
            "prompts": {"layers": _serialize_candidates(prompts_candidates)},
            "judge_system_prompt": {
                "resolved_path": str(judge_resource.path),
                "resolved_source": judge_resource.source,
                "exists": judge_resource.path.is_file(),
                "layers": _serialize_candidates(_judge_system_prompt_candidates()),
            },
        },
    }


def _frontend_dist_dir() -> Path:
    return AppPaths.frontend_dist_dir()


def _resolve_frontend_asset(full_path: str) -> Optional[Path]:
    dist_dir = _frontend_dist_dir()
    candidate = (dist_dir / full_path.lstrip("/")).resolve()
    try:
        candidate.relative_to(dist_dir.resolve())
    except ValueError:
        return None

    if candidate.is_file():
        return candidate
    return None


def _serve_frontend(full_path: str):
    dist_dir = _frontend_dist_dir()
    index_file = dist_dir / "index.html"
    if not index_file.exists():
        return PlainTextResponse(
            (
                "配布用 frontend が見つかりません。\n"
                "開発環境では `npm run build --prefix frontend` を実行してください。\n"
                "portable ZIP を使っている場合は、ZIP を再展開して `frontend/dist` が含まれているか確認してください。"
            ),
            status_code=503,
        )

    asset = _resolve_frontend_asset(full_path)
    if asset is not None:
        return FileResponse(asset)

    if full_path and "." in Path(full_path).name:
        raise HTTPException(status_code=404, detail="静的ファイルが見つかりません")

    return FileResponse(index_file)


def _load_tasks() -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []

    task_ids = set()
    for candidate in _rubrics_candidates():
        if candidate.path.is_dir():
            task_ids.update(path.stem for path in candidate.path.glob("*.md"))
    for candidate in _prompts_candidates():
        if candidate.path.is_dir():
            task_ids.update(path.stem for path in candidate.path.glob("*.md"))

    for task_id in sorted(task_ids):
        rubric_resource = _resolve_rubric_file(f"{task_id}.md")
        prompt_resource = _resolve_prompt_file(f"{task_id}.md")
        rubric_file = rubric_resource.path
        prompt_file = prompt_resource.path
        if not rubric_file.is_file() or not prompt_file.is_file():
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
                "rubric_source": rubric_resource.source,
                "prompt_source": prompt_resource.source,
                "type": task_type,
                "config": _load_task_config(task_id),
            }
        )

    return tasks


def _load_holistic_tasks() -> List[Dict[str, Any]]:
    """rubrics/holistic/ と prompts/holistic/ から包括評価タスクを読み込む。"""
    tasks: List[Dict[str, Any]] = []

    task_ids: set = set()
    for candidate in _holistic_rubrics_candidates():
        if candidate.path.is_dir():
            task_ids.update(path.stem for path in candidate.path.glob("*.md"))
    for candidate in _holistic_prompts_candidates():
        if candidate.path.is_dir():
            task_ids.update(path.stem for path in candidate.path.glob("*.md"))

    for task_id in sorted(task_ids):
        rubric_resource = _resolve_candidate_file(
            _holistic_rubrics_candidates(), f"{task_id}.md"
        )
        prompt_resource = _resolve_candidate_file(
            _holistic_prompts_candidates(), f"{task_id}.md"
        )
        if not rubric_resource.path.is_file() or not prompt_resource.path.is_file():
            continue
        tasks.append(
            {
                "id": task_id,
                "rubric_file": str(rubric_resource.path),
                "prompt_file": str(prompt_resource.path),
            }
        )

    return tasks


def _resolve_subject_key(model_name: str, api_keys: Dict[str, str]) -> Optional[str]:
    return resolve_api_key_for_model(model_name, api_keys)


def _provider_public_dict(entry: ProviderEntry) -> Dict[str, Any]:
    """ProviderEntry → API 応答（key は含めない）。"""
    data = entry.to_dict()
    data["has_key"] = bool(SecretsStore.load_provider_secret(entry.id))
    return data


def _lmstudio_config_response() -> Dict[str, Any]:
    config = ProviderConfigStore.load_provider("lmstudio")
    base_url = str(config.get("base_url") or "").strip()
    token = SecretsStore.load_existing().get("lmstudio")
    return {
        "configured": bool(base_url),
        "base_url": base_url,
        "api_token_configured": bool(token),
    }


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


def _initial_task_progress_state(
    task_id: str,
    task_index: int,
    judge_models: List[str],
    task_kind: str = "standard",
) -> Dict[str, Any]:
    return {
        "task_id": task_id,
        "task_index": task_index,
        "task_kind": task_kind,
        "phase": "queued",
        "message": "Queued",
        "subject_done": False,
        "judge_states": {judge_model: "pending" for judge_model in judge_models},
    }


def _apply_progress_message(
    task_state: Dict[str, Any], message: str, judge_model: str = ""
) -> None:
    task_state["message"] = message

    if "被験LLM出力待ち" in message:
        task_state["phase"] = "running_subject"
        return

    if "被験LLMエラー" in message:
        task_state["phase"] = "running_subject"
        task_state["subject_done"] = True
        return

    if not judge_model:
        judge_model = _extract_judge_model(message)

    if not judge_model:
        return

    task_state["subject_done"] = True
    task_state["phase"] = "running_judges"

    if "評価確認" in message:
        task_state["judge_states"][judge_model] = "completed"
    elif "エラー" in message:
        task_state["judge_states"][judge_model] = "error"
    else:
        task_state["judge_states"][judge_model] = "running"


def _remaining_task_count_for_eta(
    *,
    snapshot: Dict[str, Any],
    task_states: List[Dict[str, Any]],
    holistic_task_count: int,
) -> int:
    """ETA 用の残タスク数。standard lane に holistic 残件を加算する。

    intent: DEC-002 (Core/task-duration-eta) —
    standard 完了後も holistic 未完了なら remaining=0 の measured 0 にしない。
    snapshot の active/queued は standard-only（DEC-001 holistic-run-progress）のまま。
    """
    remaining = int(snapshot["active_task_count"]) + int(snapshot["queued_task_count"])
    if holistic_task_count <= 0:
        return remaining
    # holistic phase 開始後（task_states に holistic が載った時点）だけ加算する
    if not any(state.get("task_kind") == "holistic" for state in task_states):
        return remaining
    holistic_done = sum(
        1
        for state in task_states
        if state.get("task_kind") == "holistic"
        and state.get("phase") in ("completed", "failed")
    )
    return remaining + max(0, holistic_task_count - holistic_done)


def _compute_progress_eta(
    *,
    completed_task_count: int,
    remaining_task_count: int,
    elapsed_ms: int,
    current_step: int,
    total_steps: int,
    history_summaries: Optional[List[Dict[str, Any]]] = None,
    subject_model: str = "",
    task_count: int = 0,
    judge_count: int = 0,
    subject_run_count: int = 1,
    judge_run_count: int = 1,
    now_ms: Optional[float] = None,
) -> Dict[str, Any]:
    """Wall-clock remaining ETA with heavy in-run pace and weak history prior.

    intent: DEC-002 (Core/task-duration-eta) — wait remaining; measured dominates;
    history is similarity-weighted prior on SSE (not task_timing average).
    """
    return _compute_progress_eta_core(
        completed_task_count=completed_task_count,
        remaining_task_count=remaining_task_count,
        elapsed_ms=elapsed_ms,
        current_step=current_step,
        total_steps=total_steps,
        history_summaries=history_summaries,
        subject_model=subject_model,
        task_count=task_count,
        judge_count=judge_count,
        subject_run_count=subject_run_count,
        judge_run_count=judge_run_count,
        now_ms=now_ms,
    )


def _holistic_subject_response_text(task_result: Dict[str, Any]) -> str:
    """包括評価へ渡す被験回答テキストを構築する。

    intent: DEC-007 (Core/subject-multi-run-judge-batch) —
    subject_runs > 1 では list-eval と同じ `_build_bundled_subject_runs` 全文を渡す。
    """
    subject_runs = task_result.get("subject_runs")
    if isinstance(subject_runs, list) and len(subject_runs) > 1:
        return BenchmarkEngine._build_bundled_subject_runs(subject_runs)
    return str(task_result.get("response", ""))


def _build_non_creative_holistic_inputs(
    completed: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """creative 除外済みの包括評価入力リストを構築する。"""
    return [
        {
            "task_name": r["task_name"],
            "task_type": r["task_type"],
            "input_prompt": r["input_prompt"],
            "response": _holistic_subject_response_text(r),
        }
        for r in completed
        if r.get("task_type") != "creative"
    ]


def _build_progress_snapshot(task_states: List[Dict[str, Any]]) -> Dict[str, Any]:
    # intent: DEC-001 (Core/holistic-run-progress) — 通常 task の lane と post-processing phase を混同させない。
    standard_task_states = [
        state for state in task_states if state.get("task_kind", "standard") == "standard"
    ]
    completed_count = sum(
        1 for state in standard_task_states if state["phase"] == "completed"
    )
    completed_states = [
        state for state in standard_task_states if state["phase"] == "completed"
    ]
    active_states = [
        state
        for state in standard_task_states
        if state["phase"] in ("running_subject", "running_judges")
    ]
    queued_states = [
        state for state in standard_task_states if state["phase"] == "queued"
    ]
    queued_count = len(queued_states)

    active_tasks = []
    for state in active_states:
        judge_states = state["judge_states"]
        active_tasks.append(
            {
                "task_id": state["task_id"],
                "task_index": state["task_index"],
                "task_kind": state.get("task_kind", "standard"),
                "phase": state["phase"],
                "message": state["message"],
                "subject_done": state["subject_done"],
                "judge_states": judge_states,
                "judge_completed_count": sum(
                    1 for phase in judge_states.values() if phase == "completed"
                ),
                "judge_error_count": sum(
                    1 for phase in judge_states.values() if phase == "error"
                ),
                "judge_total_count": len(judge_states),
                "active_judges": [
                    judge for judge, phase in judge_states.items() if phase == "running"
                ],
            }
        )

    queued_tasks = []
    for state in queued_states:
        judge_states = state["judge_states"]
        queued_tasks.append(
            {
                "task_id": state["task_id"],
                "task_index": state["task_index"],
                "task_kind": state.get("task_kind", "standard"),
                "phase": state["phase"],
                "message": state["message"],
                "subject_done": state["subject_done"],
                "judge_states": judge_states,
                "judge_completed_count": 0,
                "judge_error_count": 0,
                "judge_total_count": len(judge_states),
                "active_judges": [],
            }
        )

    completed_tasks = []
    for state in completed_states:
        judge_states = state["judge_states"]
        completed_tasks.append(
            {
                "task_id": state["task_id"],
                "task_index": state["task_index"],
                "task_kind": state.get("task_kind", "standard"),
                "phase": state["phase"],
                "message": state["message"],
                "subject_done": state["subject_done"],
                "judge_states": judge_states,
                "judge_completed_count": sum(
                    1 for phase in judge_states.values() if phase == "completed"
                ),
                "judge_error_count": sum(
                    1 for phase in judge_states.values() if phase == "error"
                ),
                "judge_total_count": len(judge_states),
                "active_judges": [],
            }
        )

    return {
        "completed_task_count": completed_count,
        "active_task_count": len(active_states),
        "queued_task_count": queued_count,
        "completed_tasks": sorted(completed_tasks, key=lambda item: item["task_index"]),
        "active_tasks": sorted(active_tasks, key=lambda item: item["task_index"]),
        "queued_tasks": sorted(queued_tasks, key=lambda item: item["task_index"]),
    }


def _build_holistic_progress_event(
    *,
    status: str,
    completed_task_count: int,
    failed_task_count: int,
    total_task_count: int,
    message: str,
    current_task_index: Optional[int] = None,
    current_task_id: str = "",
) -> Dict[str, Any]:
    """包括評価専用の SSE progress payload を構築する。"""
    return {
        "type": "holistic_progress",
        "status": status,
        "completed_task_count": completed_task_count,
        "failed_task_count": failed_task_count,
        "total_task_count": total_task_count,
        "current_task_index": current_task_index,
        "current_task_id": current_task_id,
        "message": message,
    }


async def _drain_progress_events_while_task_runs(
    running_task: asyncio.Task[Any],
    progress_queue: asyncio.Queue[Optional[Dict[str, Any]]],
    cancel_checker: Callable[[], None],
) -> AsyncGenerator[Dict[str, Any], None]:
    """実行中 task の progress event を接続へ遅延なく渡す。"""
    try:
        while not running_task.done() or not progress_queue.empty():
            cancel_checker()
            try:
                event = progress_queue.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.05)
                continue

            if event is not None:
                yield event
    except asyncio.CancelledError:
        if not running_task.done():
            running_task.cancel()
        await asyncio.gather(running_task, return_exceptions=True)
        raise


# ---------------------------------------------------------------------------
# Pydantic モデル
# ---------------------------------------------------------------------------


class ApiKeySaveRequest(BaseModel):
    openrouter: Optional[str] = None


class ApiKeyClearRequest(BaseModel):
    openrouter: bool = False


class ProviderKeyRequest(BaseModel):
    key: str


class ProviderCreateRequest(BaseModel):
    display_name: str
    kind: str
    base_url: Optional[str] = None
    pricing_profile: Optional[str] = None
    profile: Optional[str] = None


class ProviderUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    base_url: Optional[str] = None
    clear_base_url: bool = False
    pricing_profile: Optional[str] = None
    profile: Optional[str] = None


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
    # intent: DEC-002/005 (Core/subject-multi-run-judge-batch) — judge_runs と独立、1–5 clamp
    subject_runs: int = 1
    subject_temp: float = 0.6
    strict_mode: bool = False
    strict_preset_id: Optional[str] = None
    task_tool_mode_overrides: Dict[str, str] = {}
    run_holistic: bool = True
    # intent: DEC-001 (Core/holistic-judge-model) — 空は judge_models へ fallback（後方互換）
    holistic_judge_models: List[str] = []
    # intent: DEC-003 (Core/exclude-unreliable-judges) — run 時固定、default OFF
    exclude_unreliable_judges: bool = False
    subject_parallel: bool = True
    judge_parallel: bool = True

    def clamped_subject_runs(self) -> int:
        return BenchmarkEngine.clamp_subject_runs(self.subject_runs)


def _effective_holistic_judge_models(
    judge_models: List[str],
    holistic_judge_models: Optional[List[str]] = None,
) -> List[str]:
    """Resolve holistic judge IDs; empty/unspecified falls back to judge_models."""
    # intent: DEC-001 (Core/holistic-judge-model) — optional override with judge_models fallback
    if holistic_judge_models:
        return list(holistic_judge_models)
    return list(judge_models)


class ClientErrorRequest(BaseModel):
    source: str
    message: str
    stack: Optional[str] = None
    path: Optional[str] = None


class GroundingDocumentRequest(BaseModel):
    url: str
    title: Optional[str] = None
    text: str
    source_type: Optional[str] = None
    published_at: Optional[str] = None
    retrieved_at: Optional[str] = None


class GroundingCorpusRequest(BaseModel):
    query: str
    search_results: Any = None
    documents: List[GroundingDocumentRequest]
    notes: Optional[str] = None


class OpenRouterManagementKeyRequest(BaseModel):
    key: str


class LMStudioConfigRequest(BaseModel):
    base_url: str
    api_token: Optional[str] = None


# ---------------------------------------------------------------------------
# エンドポイント: タスク
# ---------------------------------------------------------------------------


@app.get("/api/tasks")
def get_tasks() -> List[Dict[str, Any]]:
    """利用可能なタスク一覧を返す（一覧表示向けプレビュー付き）"""
    tasks = _load_tasks()
    result = []
    for t in tasks:
        prompt_preview = ""
        try:
            prompt = Path(t["prompt_file"]).read_text(encoding="utf-8")
            normalized = " ".join(prompt.split())
            prompt_preview = normalized[:140]
        except Exception:
            pass
        subject_tools_cfg = t.get("config", {}).get("subject_tools") or {}
        result.append(
            {
                "id": t["id"],
                "type": t["type"],
                "prompt_preview": prompt_preview,
                "prompt_source": t["prompt_source"],
                "rubric_source": t["rubric_source"],
                "has_subject_tools": bool(subject_tools_cfg),
                "tool_mode": subject_tools_cfg.get("tool_mode") if subject_tools_cfg else None,
            }
        )
    return result


@app.get("/api/resources")
def get_resources() -> Dict[str, Any]:
    """現在の resource 解決状態を返す。"""
    return get_runtime_diagnostics()["resources"]


@app.get("/api/strict-mode/preset")
def get_strict_mode_preset() -> Dict[str, Any]:
    """Official Strict preset を返す。"""
    return get_official_strict_preset()


@app.post("/api/client-errors")
def log_client_error(req: ClientErrorRequest) -> Dict[str, str]:
    """フロントエンドの runtime error をサーバーログへ記録する。"""
    logger.error(
        "client runtime error source=%s path=%s message=%s stack=%s",
        req.source,
        req.path or "",
        req.message,
        req.stack or "",
    )
    return {"status": "ok"}


@app.get("/api/grounding-corpus")
def list_grounding_corpus() -> List[Dict[str, Any]]:
    """保存済み grounding corpus レコード一覧を返す。"""
    return GroundingCorpusStore.list_records()


@app.get("/api/grounding-corpus/{record_id}")
def get_grounding_corpus(record_id: str) -> Dict[str, Any]:
    filepath = GroundingCorpusStore.resolve_record_path(record_id)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="grounding corpus record not found")
    return GroundingCorpusStore.load(filepath)


@app.post("/api/grounding-corpus")
def save_grounding_corpus(req: GroundingCorpusRequest) -> Dict[str, Any]:
    filepath = GroundingCorpusStore.save(req.model_dump())
    return {
        "status": "ok",
        "record_id": filepath.stem,
        "saved_path": str(filepath),
    }


# ---------------------------------------------------------------------------
# エンドポイント: APIキー管理
# ---------------------------------------------------------------------------


@app.get("/api/keys/status")
def get_keys_status() -> Dict[str, Any]:
    """registry 各プロバイダのキー有無（値は返さない）。lmstudio は別エンドポイント。"""
    _bootstrap_provider_registry()
    providers = {
        entry.id: bool(SecretsStore.load_provider_secret(entry.id))
        for entry in ProviderRegistry.list_providers()
    }
    return {
        "openrouter": bool(providers.get("openrouter")),
        "providers": providers,
    }


@app.post("/api/keys")
def save_keys(req: ApiKeySaveRequest) -> Dict[str, str]:
    """APIキーを保存する（後方互換: openrouter）。"""
    values = req.model_dump()
    if not any(values.values()):
        raise HTTPException(status_code=400, detail="APIキーが入力されていません")
    SecretsStore.save(values)
    load_dotenv(override=True)
    return {"status": "ok"}


@app.delete("/api/keys")
def clear_keys(req: ApiKeyClearRequest) -> Dict[str, str]:
    """指定プロバイダーのAPIキーを削除する（後方互換: openrouter）。"""
    providers = req.model_dump()
    if not any(providers.values()):
        raise HTTPException(
            status_code=400, detail="削除するプロバイダを選択してください"
        )
    SecretsStore.clear(providers)
    load_dotenv(override=True)
    return {"status": "ok"}


@app.get("/api/providers")
def list_providers() -> Dict[str, Any]:
    _bootstrap_provider_registry()
    return {
        "providers": [
            _provider_public_dict(entry)
            for entry in ProviderRegistry.list_providers()
        ]
    }


@app.post("/api/providers")
def create_provider(req: ProviderCreateRequest) -> Dict[str, Any]:
    _bootstrap_provider_registry()
    try:
        entry = ProviderRegistry.add(
            display_name=req.display_name,
            kind=req.kind,  # type: ignore[arg-type]
            base_url=req.base_url,
            pricing_profile=req.pricing_profile,  # type: ignore[arg-type]
            profile=req.profile,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _provider_public_dict(entry)


@app.patch("/api/providers/{provider_id}")
def update_provider(provider_id: str, req: ProviderUpdateRequest) -> Dict[str, Any]:
    _bootstrap_provider_registry()
    try:
        entry = ProviderRegistry.update(
            provider_id,
            display_name=req.display_name,
            base_url=req.base_url,
            clear_base_url=req.clear_base_url,
            pricing_profile=req.pricing_profile,  # type: ignore[arg-type]
            profile=req.profile,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _provider_public_dict(entry)


@app.delete("/api/providers/{provider_id}")
def delete_provider(provider_id: str) -> Dict[str, str]:
    _bootstrap_provider_registry()
    try:
        ProviderRegistry.delete(provider_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    SecretsStore.clear_provider_secret(provider_id)
    load_dotenv(override=True)
    return {"status": "ok"}


@app.post("/api/providers/{provider_id}/key")
def save_provider_key(provider_id: str, req: ProviderKeyRequest) -> Dict[str, str]:
    _bootstrap_provider_registry()
    entry = ProviderRegistry.get(provider_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"provider not found: {provider_id}")
    key = req.key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="APIキーが入力されていません")
    SecretsStore.save_provider_secret(provider_id, key)
    load_dotenv(override=True)
    return {"status": "ok"}


@app.delete("/api/providers/{provider_id}/key")
def clear_provider_key(provider_id: str) -> Dict[str, str]:
    _bootstrap_provider_registry()
    entry = ProviderRegistry.get(provider_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"provider not found: {provider_id}")
    SecretsStore.clear_provider_secret(provider_id)
    load_dotenv(override=True)
    return {"status": "ok"}


@app.post("/api/providers/{provider_id}/test")
def test_provider_connection(provider_id: str) -> Dict[str, Any]:
    """接続テスト（models 一覧または最小 complete）。key はエコーしない。"""
    _bootstrap_provider_registry()
    entry = ProviderRegistry.get(provider_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"provider not found: {provider_id}")
    api_key = SecretsStore.load_provider_secret(provider_id)
    if not api_key:
        raise HTTPException(status_code=400, detail="APIキーが未設定です")

    probe_model = f"{provider_id}/probe"
    adapter = get_adapter_for_model(probe_model, api_key=api_key)
    if adapter is None or not adapter.is_available():
        return {"ok": False, "error": "アダプタを初期化できません（base_url 等を確認）"}

    try:
        if entry.kind == "openai_compatible" and entry.base_url:
            models = ModelCatalog._fetch_openai_compatible_models(
                {
                    "provider_id": provider_id,
                    "base_url": entry.base_url,
                    "api_key": api_key,
                }
            )
            return {"ok": True, "model_count": len(models)}

        adapter.complete(
            system_prompt="Reply with ok.",
            user_prompt="ping",
            temperature=0.0,
            max_tokens=8,
        )
        return {"ok": True}
    except Exception as exc:
        logger.warning("provider connection test failed id=%s error=%s", provider_id, exc)
        # intent-invariant: INV-002 — エラー文言に key を含めない
        message = str(exc)
        if api_key and api_key in message:
            message = "接続テストに失敗しました"
        return {"ok": False, "error": message}


@app.get("/api/lmstudio/config")
def get_lmstudio_config() -> Dict[str, Any]:
    return _lmstudio_config_response()


@app.post("/api/lmstudio/config")
def save_lmstudio_config(req: LMStudioConfigRequest) -> Dict[str, Any]:
    base_url = req.base_url.strip()
    if not base_url:
        raise HTTPException(status_code=400, detail="LM Studio の URL を入力してください")

    ProviderConfigStore.save_provider("lmstudio", {"base_url": base_url})

    if req.api_token is not None:
        token = req.api_token.strip()
        if token:
            SecretsStore.save({"lmstudio": token})
        else:
            SecretsStore.clear_provider_secret("lmstudio")

    load_dotenv(override=True)
    return _lmstudio_config_response()


@app.delete("/api/lmstudio/config")
def clear_lmstudio_config() -> Dict[str, str]:
    ProviderConfigStore.clear_provider("lmstudio")
    SecretsStore.clear_provider_secret("lmstudio")
    load_dotenv(override=True)
    return {"status": "ok"}


@app.get("/api/openrouter/admin/status")
def get_openrouter_admin_status() -> Dict[str, bool]:
    return {"configured": bool(SecretsStore.load_openrouter_management_key())}


@app.post("/api/openrouter/admin/key")
def save_openrouter_admin_key(req: OpenRouterManagementKeyRequest) -> Dict[str, str]:
    key = req.key.strip()
    if not key:
        raise HTTPException(
            status_code=400, detail="Management key が入力されていません"
        )
    SecretsStore.save_openrouter_management_key(key)
    load_dotenv(override=True)
    return {"status": "ok"}


@app.delete("/api/openrouter/admin/key")
def clear_openrouter_admin_key() -> Dict[str, str]:
    SecretsStore.clear_openrouter_management_key()
    load_dotenv(override=True)
    return {"status": "ok"}


@app.get("/api/openrouter/credits")
def get_openrouter_credits() -> Dict[str, Any]:
    key = SecretsStore.load_openrouter_management_key()
    if not key:
        return {"configured": False}

    try:
        credits = fetch_credits(key)
    except OpenRouterAdminError as error:
        logger.warning("openrouter credits fetch failed: %s", error)
        raise HTTPException(status_code=502, detail=str(error)) from error

    return {
        "configured": True,
        "total_credits": credits["total_credits"],
        "total_usage": credits["total_usage"],
        "remaining_credits": credits["remaining_credits"],
    }


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


def _apply_tool_mode_override(
    subject_tools: Optional[Dict[str, Any]],
    mode_override: Optional[str],
) -> Optional[Dict[str, Any]]:
    _VALID = {"native", "text", "auto"}
    if subject_tools is None or mode_override not in _VALID:
        return subject_tools
    return {**subject_tools, "tool_mode": mode_override}


# ---------------------------------------------------------------------------
# エンドポイント: ベンチマーク実行 (SSE)
# ---------------------------------------------------------------------------


@app.post("/api/run")
async def run_benchmark(req: RunRequest) -> StreamingResponse:
    """
    ベンチマーク評価を実行し、進捗を SSE でストリームする。

    イベント種別:
      {"type": "progress", "message": str, "current": int, "total": int}
      {"type": "holistic_progress", "status": "started|running|completed", ...}
      {"type": "complete", "result": {...}, "saved_path": str}
      {"type": "cancelled", "completed_tasks": int, "total_tasks": int}
      {"type": "error", "message": str, "traceback": str}
    """
    run_id = f"{time.strftime('%Y%m%d_%H%M%S')}_{req.target_model}"
    run_started_at = time.perf_counter()
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
                logger.warning("run aborted: no valid selected tasks run_id=%s", run_id)
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
                logger.warning(
                    "run aborted: subject adapter unavailable run_id=%s target_model=%s",
                    run_id,
                    req.target_model,
                )
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
                logger.warning(
                    "run aborted: no judge adapters run_id=%s judge_models=%s",
                    run_id,
                    req.judge_models,
                )
                yield _sse_event(
                    {
                        "type": "error",
                        "message": "judgeモデルに対応するAPIキーがありません",
                        "traceback": "",
                    }
                )
                return

            judge_system_prompt_resource = _resolve_judge_system_prompt_resource()
            judge_system_prompt_path = judge_system_prompt_resource.path
            logger.info(
                "judge system prompt source=%s path=%s",
                judge_system_prompt_resource.source,
                judge_system_prompt_path,
            )
            system_prompt = (
                judge_system_prompt_path.read_text(encoding="utf-8")
                if judge_system_prompt_path.exists()
                else ""
            )
            strict_preset = get_official_strict_preset()
            if req.strict_mode and req.strict_preset_id not in (
                None,
                strict_preset["id"],
            ):
                logger.warning(
                    "run aborted: strict preset mismatch run_id=%s requested=%s expected=%s",
                    run_id,
                    req.strict_preset_id,
                    strict_preset["id"],
                )
                yield _sse_event(
                    {
                        "type": "error",
                        "message": "Strict Mode preset が一致しません。設定画面を再読み込みしてください。",
                        "traceback": "",
                    }
                )
                return

            strict_mode = build_strict_mode_metadata(
                target_model=req.target_model,
                selected_tasks=selected,
                judge_models=req.judge_models,
                judge_runs=req.judge_runs,
                subject_temp=req.subject_temp,
                judge_system_prompt_path=judge_system_prompt_path,
                judge_system_prompt_source=judge_system_prompt_resource.source,
                requested=req.strict_mode,
                preset=strict_preset,
            )
            if req.strict_mode and not strict_mode.get("enforced", False):
                logger.warning(
                    "run aborted: strict mode validation failed run_id=%s reasons=%s",
                    run_id,
                    strict_mode.get("reasons", []),
                )
                yield _sse_event(
                    {
                        "type": "error",
                        "message": "Strict Mode 条件を満たしていません: "
                        + " / ".join(strict_mode.get("reasons", [])),
                        "traceback": "",
                    }
                )
                return

            subject_runs = req.clamped_subject_runs()
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
                judge_parallel=req.judge_parallel,
                subject_runs=subject_runs,
            )
            logger.info(
                "run started run_id=%s target_model=%s tasks=%d judges=%d "
                "judge_runs=%d subject_runs=%d log_file=%s",
                run_id,
                req.target_model,
                len(selected),
                len(judge_adapters),
                req.judge_runs,
                subject_runs,
                LOG_FILE_PATH,
            )

            total_tasks = len(selected)
            holistic_tasks_meta = _load_holistic_tasks()
            holistic_task_count = len(holistic_tasks_meta)
            steps_per_task = subject_runs + len(judge_adapters) * (req.judge_runs + 2)
            total_steps = (total_tasks + holistic_task_count) * steps_per_task
            progress_current = 0
            task_states = [
                _initial_task_progress_state(
                    task_info["id"], idx, list(judge_adapters.keys())
                )
                for idx, task_info in enumerate(selected)
            ]

            # ETA history prior: load once per run (DEC-002 wall prior).
            try:
                eta_history_summaries = ResultStorage.list_summaries()
            except Exception:
                logger.exception("failed to load result summaries for progress ETA")
                eta_history_summaries = []

            # SSE 送信用キュー（非同期コールバック → イベントストリームへ）
            progress_queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()

            def enqueue_progress_event(
                *,
                message: str,
                task_index: int = 0,
                task_id: str = "",
                judge_model: str = "",
                task_kind: str = "standard",
                increment_step: bool = True,
            ) -> None:
                nonlocal progress_current
                if increment_step:
                    progress_current += 1
                snapshot = _build_progress_snapshot(task_states)
                completed_task_count = int(snapshot.get("completed_task_count") or 0)
                remaining_task_count = _remaining_task_count_for_eta(
                    snapshot=snapshot,
                    task_states=task_states,
                    holistic_task_count=holistic_task_count,
                )
                elapsed_ms = int((time.perf_counter() - run_started_at) * 1000)
                eta = _compute_progress_eta(
                    completed_task_count=completed_task_count,
                    remaining_task_count=remaining_task_count,
                    elapsed_ms=elapsed_ms,
                    current_step=progress_current,
                    total_steps=total_steps,
                    history_summaries=eta_history_summaries,
                    subject_model=req.target_model,
                    task_count=total_tasks,
                    judge_count=len(judge_adapters),
                    subject_run_count=subject_runs,
                    judge_run_count=req.judge_runs,
                )
                progress_queue.put_nowait(
                    {
                        "type": "progress",
                        "message": message,
                        "current": progress_current,
                        "total": total_steps,
                        "task_index": task_index,
                        "task_id": task_id,
                        "judge_model": judge_model,
                        "task_kind": task_kind,
                        "elapsed_ms": elapsed_ms,
                        **snapshot,
                        **eta,
                    }
                )

            def enqueue_holistic_progress_event(
                *,
                status: str,
                completed_task_count: int,
                failed_task_count: int,
                message: str,
                current_task_index: Optional[int] = None,
                current_task_id: str = "",
            ) -> None:
                progress_queue.put_nowait(
                    _build_holistic_progress_event(
                        status=status,
                        completed_task_count=completed_task_count,
                        failed_task_count=failed_task_count,
                        total_task_count=holistic_task_count,
                        message=message,
                        current_task_index=current_task_index,
                        current_task_id=current_task_id,
                    )
                )

            def progress_callback(
                message: str,
                *,
                task_index: int = 0,
                task_id: str = "",
                judge_model: str = "",
            ) -> None:
                if 0 <= task_index < len(task_states):
                    _apply_progress_message(
                        task_states[task_index], message, judge_model
                    )
                enqueue_progress_event(
                    message=message,
                    task_index=task_index,
                    task_id=task_id,
                    judge_model=judge_model,
                    task_kind=(
                        task_states[task_index].get("task_kind", "standard")
                        if 0 <= task_index < len(task_states)
                        else "standard"
                    ),
                )

            def cancel_checker() -> None:
                if _cancel_flags.get(run_id):
                    raise asyncio.CancelledError("ユーザーによってキャンセルされました")

            # 評価を別タスクで実行
            task_results: List[Optional[Dict[str, Any]]] = [None] * total_tasks
            cancelled = False
            cancel_reason = ""

            task_semaphore = asyncio.Semaphore(3 if req.subject_parallel else 1)

            async def _run_single_task(idx: int, task_info: Dict[str, Any]) -> None:
                async with task_semaphore:
                    try:
                        cancel_checker()
                        task_states[idx]["phase"] = "running_subject"
                        task_states[idx]["message"] = "Task started"
                        enqueue_progress_event(
                            message=f"タスク {idx + 1}/{total_tasks}: 実行開始",
                            task_index=idx,
                            task_id=task_info["id"],
                            increment_step=False,
                        )
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
                            subject_tools=_apply_tool_mode_override(
                                task_info.get("config", {}).get("subject_tools"),
                                req.task_tool_mode_overrides.get(task_info["id"]),
                            ),
                        )
                        task_results[idx] = result.to_dict()
                        task_states[idx]["phase"] = "completed"
                        task_states[idx]["subject_done"] = True
                        task_states[idx]["message"] = "Completed"
                        task_states[idx]["task_timing"] = task_results[idx].get(
                            "task_timing"
                        )
                        for judge_model_name, phase in list(
                            task_states[idx]["judge_states"].items()
                        ):
                            if phase == "running":
                                task_states[idx]["judge_states"][judge_model_name] = (
                                    "completed"
                                )
                        enqueue_progress_event(
                            message=f"タスク {idx + 1}/{total_tasks}: 完了",
                            task_index=idx,
                            task_id=task_info["id"],
                            increment_step=False,
                        )
                    except Exception:
                        task_states[idx]["phase"] = "failed"
                        task_states[idx]["message"] = "Failed"
                        for judge_model_name, phase in list(
                            task_states[idx]["judge_states"].items()
                        ):
                            if phase == "running":
                                task_states[idx]["judge_states"][judge_model_name] = (
                                    "error"
                                )
                        enqueue_progress_event(
                            message=f"タスク {idx + 1}/{total_tasks}: 失敗",
                            task_index=idx,
                            task_id=task_info["id"],
                            increment_step=False,
                        )
                        raise

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
                    except asyncio.QueueEmpty:
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
                except asyncio.QueueEmpty:
                    break

            # キャンセルフラグが立っていたらタスクを停止
            if not cancelled and _cancel_flags.get(run_id):
                cancelled = True
                cancel_reason = "ユーザーによってキャンセルされました"
                for f in futures:
                    f.cancel()
                await asyncio.gather(*futures, return_exceptions=True)

            completed = [r for r in task_results if r is not None]

            # --- 包括評価フェーズ ---
            holistic_results: List[Dict[str, Any]] = []
            # intent: DEC-003 (Core/holistic-judge-model) — 未実行時は空、実行時は実効モデルを記録
            effective_holistic_judge_models: List[str] = []
            if not cancelled and holistic_tasks_meta and req.run_holistic:
                # intent: DEC-002/INV-002 (Core/holistic-judge-model) — holistic 開始時だけ別解決
                holistic_judge_model_ids = _effective_holistic_judge_models(
                    req.judge_models, req.holistic_judge_models
                )
                holistic_judge_adapters = get_available_judge_adapters(
                    holistic_judge_model_ids, api_keys=api_keys
                )
                if not holistic_judge_adapters:
                    # intent: Core-Bug-50 / Consequences (Core/holistic-judge-model) —
                    # adapter 空でも return せず、完了済み標準結果を ResultStorage へ保存する。
                    logger.warning(
                        "holistic aborted: no judge adapters run_id=%s "
                        "holistic_judge_models=%s",
                        run_id,
                        holistic_judge_model_ids,
                    )
                    yield _sse_event(
                        {
                            "type": "error",
                            "message": "包括評価用 judgeモデルに対応するAPIキーがありません",
                            "traceback": "",
                        }
                    )
                    # holistic_results=[] / effective_holistic_judge_models=[] のまま保存へ進む
                else:
                    effective_holistic_judge_models = list(
                        holistic_judge_adapters.keys()
                    )

                    failed_holistic_task_count = 0
                    non_creative_responses = _build_non_creative_holistic_inputs(
                        completed
                    )
                    enqueue_holistic_progress_event(
                        status="started",
                        completed_task_count=0,
                        failed_task_count=0,
                        message="包括評価を開始します",
                    )

                    for h_idx, h_task in enumerate(holistic_tasks_meta):
                        try:
                            cancel_checker()
                        except asyncio.CancelledError:
                            cancelled = True
                            cancel_reason = "ユーザーによってキャンセルされました"
                            break

                        h_state_index = total_tasks + h_idx
                        h_state = _initial_task_progress_state(
                            h_task["id"],
                            h_state_index,
                            list(holistic_judge_adapters.keys()),
                            task_kind="holistic",
                        )
                        task_states.append(h_state)

                        enqueue_holistic_progress_event(
                            status="running",
                            completed_task_count=len(holistic_results),
                            failed_task_count=failed_holistic_task_count,
                            current_task_index=h_idx,
                            current_task_id=h_task["id"],
                            message=f"包括評価 {h_idx + 1}/{holistic_task_count}: 実行中",
                        )

                        enqueue_progress_event(
                            message=f"包括評価 {h_idx + 1}/{holistic_task_count}: 実行開始",
                            task_index=h_state_index,
                            task_id=h_task["id"],
                            task_kind="holistic",
                            increment_step=False,
                        )

                        rubric_content = Path(h_task["rubric_file"]).read_text(
                            encoding="utf-8"
                        )
                        eval_prompt = Path(h_task["prompt_file"]).read_text(
                            encoding="utf-8"
                        )

                        holistic_future = asyncio.create_task(
                            engine.run_holistic_task(
                                task_name=h_task["id"],
                                eval_prompt=eval_prompt,
                                rubric_content=rubric_content,
                                bundled_responses=non_creative_responses,
                                system_prompt=system_prompt,
                                progress_callback=lambda msg, _idx=h_state_index, _tid=h_task["id"]: (
                                    progress_callback(
                                        f"包括評価: {msg}",
                                        task_index=_idx,
                                        task_id=_tid,
                                        judge_model=_extract_judge_model(msg),
                                    )
                                ),
                                cancel_checker=cancel_checker,
                                # intent: DEC-002 (Core/holistic-judge-model) — 共有 engine を差し替えず override 注入
                                judge_adapters=holistic_judge_adapters,
                            )
                        )
                        try:
                            # intent: DEC-001 (Core/holistic-run-progress) — 専用イベントを完了後まで滞留させず、実行中の phase を観測可能にする。
                            async for event in _drain_progress_events_while_task_runs(
                                holistic_future, progress_queue, cancel_checker
                            ):
                                yield _sse_event(event)

                            h_result = await holistic_future
                            holistic_results.append(h_result.to_dict())
                            task_states[h_state_index]["phase"] = "completed"
                            task_states[h_state_index]["subject_done"] = True
                            task_states[h_state_index]["message"] = "Completed"
                            enqueue_progress_event(
                                message=f"包括評価 {h_idx + 1}/{holistic_task_count}: 完了",
                                task_index=h_state_index,
                                task_id=h_task["id"],
                                task_kind="holistic",
                                increment_step=False,
                            )
                            enqueue_holistic_progress_event(
                                status="running",
                                completed_task_count=len(holistic_results),
                                failed_task_count=failed_holistic_task_count,
                                message=f"包括評価 {h_idx + 1}/{holistic_task_count}: 完了",
                            )
                        except asyncio.CancelledError:
                            cancelled = True
                            cancel_reason = "ユーザーによってキャンセルされました"
                            break
                        except Exception as h_exc:
                            logger.exception(
                                "holistic task failed run_id=%s task_id=%s",
                                run_id,
                                h_task["id"],
                            )
                            task_states[h_state_index]["phase"] = "failed"
                            task_states[h_state_index]["message"] = f"Failed: {h_exc}"
                            failed_holistic_task_count += 1
                            enqueue_progress_event(
                                message=f"包括評価 {h_idx + 1}/{holistic_task_count}: 失敗",
                                task_index=h_state_index,
                                task_id=h_task["id"],
                                task_kind="holistic",
                                increment_step=False,
                            )
                            enqueue_holistic_progress_event(
                                status="running",
                                completed_task_count=len(holistic_results),
                                failed_task_count=failed_holistic_task_count,
                                message=f"包括評価 {h_idx + 1}/{holistic_task_count}: 失敗",
                            )

                    # キューの残りをフラッシュ
                    while not progress_queue.empty():
                        try:
                            event = progress_queue.get_nowait()
                            yield _sse_event(event)
                        except asyncio.QueueEmpty:
                            break

                    if not cancelled:
                        enqueue_holistic_progress_event(
                            status="completed",
                            completed_task_count=len(holistic_results),
                            failed_task_count=failed_holistic_task_count,
                            message="包括評価が完了しました",
                        )
                        while not progress_queue.empty():
                            try:
                                event = progress_queue.get_nowait()
                                yield _sse_event(event)
                            except asyncio.QueueEmpty:
                                break

            if cancelled:
                logger.info(
                    "run cancelled run_id=%s completed_tasks=%d total_tasks=%d reason=%s",
                    run_id,
                    len(completed),
                    total_tasks,
                    cancel_reason,
                )
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
                # intent: DEC-003 (Core/holistic-judge-model) — judge_models を上書きせず別キーで記録
                "holistic_judge_models": effective_holistic_judge_models,
                "judge_runs": req.judge_runs,
                "subject_runs": subject_runs,
                "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "execution_duration_ms": round(
                    (time.perf_counter() - run_started_at) * 1000
                ),
                "strict_mode": strict_mode,
                "tasks": completed,
                "holistic_tasks": holistic_results,
                "cancelled": False,
                "completed_tasks": len(completed),
                "total_tasks": total_tasks,
            }
            all_tasks = completed + holistic_results
            usage_summary = summarize_benchmark_usage(all_tasks)
            usage_summary_subject = summarize_subject_usage(completed)
            usage_summary_judge = summarize_judge_usage(all_tasks)
            benchmark_result["usage_summary"] = usage_summary
            benchmark_result["usage_summary_subject"] = usage_summary_subject
            benchmark_result["usage_summary_judge"] = usage_summary_judge
            benchmark_result["estimated_cost_usd"] = usage_summary["totals"].get(
                "estimated_cost_usd"
            )
            benchmark_result["cost_estimate_status"] = usage_summary["totals"].get(
                "pricing_status"
            )
            # intent: DEC-001/002 (Core/time-roi-task-timing) — 通常タスク task_timing 合算のみ
            # （holistic 除外・wall-clock 非使用）。欠落時はキー自体を付けず N/A 表示へ。
            timing_summary = summarize_task_timing(completed)
            if timing_summary is not None:
                benchmark_result["timing_summary"] = timing_summary

            # intent: DEC-003/004 — toggle 確定値を保存し、全除外時は null（0 禁止）
            score_meta = compute_score_aggregation(
                completed,
                exclude_unreliable_judges=req.exclude_unreliable_judges,
            )
            benchmark_result["exclude_unreliable_judges"] = score_meta[
                "exclude_unreliable_judges"
            ]
            benchmark_result["average_score"] = score_meta["average_score"]
            benchmark_result["best_score"] = score_meta["best_score"]
            benchmark_result["score_aggregation"] = score_meta["score_aggregation"]

            saved_path = ResultStorage.save(benchmark_result)
            logger.info(
                "run completed run_id=%s saved_path=%s completed_tasks=%d duration_ms=%s average_score=%s estimated_cost_usd=%s cost_estimate_status=%s",
                run_id,
                saved_path,
                len(completed),
                benchmark_result.get("execution_duration_ms"),
                benchmark_result.get("average_score"),
                benchmark_result.get("estimated_cost_usd"),
                benchmark_result.get("cost_estimate_status"),
            )

            yield _sse_event(
                {
                    "type": "complete",
                    "result": benchmark_result,
                    "saved_path": str(saved_path),
                }
            )

        except Exception as e:
            logger.exception("run failed run_id=%s", run_id)
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
            missing_cost = (
                "estimated_cost_usd" not in s or "cost_estimate_status" not in s
            )
            missing_strict = (
                "strict_mode_requested" not in s
                or "strict_mode_enforced" not in s
                or "strict_mode_eligible" not in s
                or "strict_mode_preset_id" not in s
                or "strict_mode_preset_label" not in s
                or "strict_mode_profile_id" not in s
                or "strict_mode_profile_label" not in s
            )
            missing_subject_cost = (
                "subject_total_tokens" not in s
                or "subject_estimated_cost_usd" not in s
                or "subject_cost_per_1m_tokens_usd" not in s
            )
            if (
                missing_run_id
                or missing_scores
                or missing_cost
                or missing_subject_cost
                or missing_strict
            ):
                filename = s.get("filename", "")
                if filename:
                    try:
                        filepath = ResultStorage.resolve_result_path(filename)
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
                            if missing_cost:
                                s["estimated_cost_usd"] = data.get("estimated_cost_usd")
                                s["cost_estimate_status"] = data.get(
                                    "cost_estimate_status"
                                )
                                needs_reindex = True
                            if missing_subject_cost:
                                rebuilt = ResultStorage._build_summary(data, filepath)
                                s["subject_total_tokens"] = rebuilt.get(
                                    "subject_total_tokens"
                                )
                                s["subject_estimated_cost_usd"] = rebuilt.get(
                                    "subject_estimated_cost_usd"
                                )
                                s["subject_cost_per_1m_tokens_usd"] = rebuilt.get(
                                    "subject_cost_per_1m_tokens_usd"
                                )
                                needs_reindex = True
                            if missing_strict:
                                rebuilt = ResultStorage._build_summary(data, filepath)
                                s["strict_mode_requested"] = rebuilt.get(
                                    "strict_mode_requested"
                                )
                                s["strict_mode_enforced"] = rebuilt.get(
                                    "strict_mode_enforced"
                                )
                                s["strict_mode_eligible"] = rebuilt.get(
                                    "strict_mode_eligible"
                                )
                                s["strict_mode_preset_id"] = rebuilt.get(
                                    "strict_mode_preset_id"
                                )
                                s["strict_mode_preset_label"] = rebuilt.get(
                                    "strict_mode_preset_label"
                                )
                                s["strict_mode_profile_id"] = rebuilt.get(
                                    "strict_mode_profile_id"
                                )
                                s["strict_mode_profile_label"] = rebuilt.get(
                                    "strict_mode_profile_label"
                                )
                                needs_reindex = True
                        else:
                            if missing_run_id:
                                s["run_id"] = Path(filename).stem
                            if missing_scores:
                                s.setdefault("max_score", 0)
                                s.setdefault("min_score", 0)
                            if missing_cost:
                                s.setdefault("estimated_cost_usd", None)
                                s.setdefault("cost_estimate_status", "unavailable")
                            if missing_subject_cost:
                                s.setdefault("subject_total_tokens", 0)
                                s.setdefault("subject_estimated_cost_usd", None)
                                s.setdefault("subject_cost_per_1m_tokens_usd", None)
                            if missing_strict:
                                s.setdefault("strict_mode_requested", False)
                                s.setdefault("strict_mode_enforced", False)
                                s.setdefault("strict_mode_eligible", False)
                                s.setdefault("strict_mode_preset_id", None)
                                s.setdefault("strict_mode_preset_label", None)
                                s.setdefault("strict_mode_profile_id", None)
                                s.setdefault("strict_mode_profile_label", None)
                    except Exception:
                        if missing_run_id:
                            s["run_id"] = Path(filename).stem
                        if missing_scores:
                            s.setdefault("max_score", 0)
                            s.setdefault("min_score", 0)
                        if missing_cost:
                            s.setdefault("estimated_cost_usd", None)
                            s.setdefault("cost_estimate_status", "unavailable")
                        if missing_subject_cost:
                            s.setdefault("subject_total_tokens", 0)
                            s.setdefault("subject_estimated_cost_usd", None)
                            s.setdefault("subject_cost_per_1m_tokens_usd", None)
                        if missing_strict:
                            s.setdefault("strict_mode_requested", False)
                            s.setdefault("strict_mode_enforced", False)
                            s.setdefault("strict_mode_eligible", False)
                            s.setdefault("strict_mode_preset_id", None)
                            s.setdefault("strict_mode_preset_label", None)
                            s.setdefault("strict_mode_profile_id", None)
                            s.setdefault("strict_mode_profile_label", None)
            # スコアを小数1桁に丸める。
            # intent: DEC-004 (Core/exclude-unreliable-judges) — all-excluded 時は
            # avg/max/min が null のまま一覧へ通し、0 に潰さない。
            # dict.get(key, 0) は key が存在して値が None のとき None を返すため、
            # round 前に None を明示分岐する。
            for _score_key in ("avg_score", "max_score", "min_score"):
                _score_val = s.get(_score_key, 0)
                s[_score_key] = (
                    None if _score_val is None else round(_score_val, 1)
                )
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
    filepath = ResultStorage.resolve_result_path(filename)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="結果ファイルが見つかりません")
    try:
        return ResultStorage.load(filepath)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"結果の読み込みに失敗しました: {e}"
        )


@app.delete("/api/results/{filename}")
def delete_result(filename: str) -> Dict[str, Any]:
    """指定ファイルの評価結果を削除する"""
    filepath = ResultStorage.resolve_result_path(filename)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="結果ファイルが見つかりません")

    run_id = filepath.stem
    try:
        data = ResultStorage.load(filepath)
        run_id = data.get("run_id", run_id)
    except Exception:
        pass

    deleted = ResultStorage.delete(filepath)
    if not deleted:
        raise HTTPException(status_code=500, detail="結果ファイルの削除に失敗しました")

    logger.info("result deleted run_id=%s filename=%s", run_id, filepath.name)
    return {
        "status": "deleted",
        "filename": filepath.name,
        "run_id": run_id,
    }


@app.get("/", include_in_schema=False)
def serve_frontend_root():
    return _serve_frontend("")


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend_path(full_path: str):
    return _serve_frontend(full_path)
