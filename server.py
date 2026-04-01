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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from adapters import get_adapter_for_model, get_available_judge_adapters
from core import BenchmarkEngine, GroundingCorpusStore, ResultStorage
from core.app_paths import AppPaths
from core.cost_estimator import summarize_benchmark_usage
from core.logging_utils import configure_logging
from core.model_catalog import ModelCatalog
from core.openrouter_admin import OpenRouterAdminError, fetch_credits
from core.secrets_store import SecretsStore
from core.selection_store import SelectionStore
from core.strict_mode import (
    build_strict_mode_metadata,
    get_official_strict_preset,
)

load_dotenv()
LOG_FILE_PATH = configure_logging()

logger = logging.getLogger(__name__)

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


def _initial_task_progress_state(
    task_id: str, task_index: int, judge_models: List[str]
) -> Dict[str, Any]:
    return {
        "task_id": task_id,
        "task_index": task_index,
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


def _build_progress_snapshot(task_states: List[Dict[str, Any]]) -> Dict[str, Any]:
    completed_count = sum(1 for state in task_states if state["phase"] == "completed")
    completed_states = [state for state in task_states if state["phase"] == "completed"]
    active_states = [
        state
        for state in task_states
        if state["phase"] in ("running_subject", "running_judges")
    ]
    queued_states = [state for state in task_states if state["phase"] == "queued"]
    queued_count = len(queued_states)

    active_tasks = []
    for state in active_states:
        judge_states = state["judge_states"]
        active_tasks.append(
            {
                "task_id": state["task_id"],
                "task_index": state["task_index"],
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
    strict_mode: bool = False
    strict_preset_id: Optional[str] = None


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
        result.append(
            {
                "id": t["id"],
                "type": t["type"],
                "prompt_preview": prompt_preview,
                "prompt_source": t["prompt_source"],
                "rubric_source": t["rubric_source"],
                "has_subject_tools": bool(t.get("config", {}).get("subject_tools")),
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
            logger.info(
                "run started run_id=%s target_model=%s tasks=%d judges=%d judge_runs=%d log_file=%s",
                run_id,
                req.target_model,
                len(selected),
                len(judge_adapters),
                req.judge_runs,
                LOG_FILE_PATH,
            )

            total_tasks = len(selected)
            total_steps = total_tasks * (1 + len(judge_adapters) * (req.judge_runs + 2))
            progress_current = 0
            task_states = [
                _initial_task_progress_state(
                    task_info["id"], idx, list(judge_adapters.keys())
                )
                for idx, task_info in enumerate(selected)
            ]

            # SSE 送信用キュー（非同期コールバック → イベントストリームへ）
            progress_queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()

            def enqueue_progress_event(
                *,
                message: str,
                task_index: int = 0,
                task_id: str = "",
                judge_model: str = "",
                increment_step: bool = True,
            ) -> None:
                nonlocal progress_current
                if increment_step:
                    progress_current += 1
                snapshot = _build_progress_snapshot(task_states)
                progress_queue.put_nowait(
                    {
                        "type": "progress",
                        "message": message,
                        "current": progress_current,
                        "total": total_steps,
                        "task_index": task_index,
                        "task_id": task_id,
                        "judge_model": judge_model,
                        **snapshot,
                    }
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
                )

            def cancel_checker() -> None:
                if _cancel_flags.get(run_id):
                    raise asyncio.CancelledError("ユーザーによってキャンセルされました")

            # 評価を別タスクで実行
            task_results: List[Optional[Dict[str, Any]]] = [None] * total_tasks
            cancelled = False
            cancel_reason = ""

            task_semaphore = asyncio.Semaphore(3)

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
                            subject_tools=task_info.get("config", {}).get(
                                "subject_tools"
                            ),
                        )
                        task_results[idx] = result.to_dict()
                        task_states[idx]["phase"] = "completed"
                        task_states[idx]["subject_done"] = True
                        task_states[idx]["message"] = "Completed"
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
                "judge_runs": req.judge_runs,
                "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "execution_duration_ms": round(
                    (time.perf_counter() - run_started_at) * 1000
                ),
                "strict_mode": strict_mode,
                "tasks": completed,
                "cancelled": False,
                "completed_tasks": len(completed),
                "total_tasks": total_tasks,
            }
            usage_summary = summarize_benchmark_usage(completed)
            benchmark_result["usage_summary"] = usage_summary
            benchmark_result["estimated_cost_usd"] = usage_summary["totals"].get(
                "estimated_cost_usd"
            )
            benchmark_result["cost_estimate_status"] = usage_summary["totals"].get(
                "pricing_status"
            )

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
