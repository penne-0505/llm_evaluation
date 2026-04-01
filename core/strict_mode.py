"""Strict Mode preset 定義、検証、metadata 構築"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List


STRICT_MODE_VERSION = "v2"
OFFICIAL_STRICT_PRESET_ID = "official-v1"

_OFFICIAL_STRICT_PRESET: Dict[str, Any] = {
    "id": OFFICIAL_STRICT_PRESET_ID,
    "label": "Official Strict v1",
    "description": "固定 judge・固定 task set・固定 parameter で leaderboard 比較を成立させる正式モード",
    "subject_model_policy": "variable",
    "judge_models": [
        {
            "id": "openrouter/anthropic/claude-sonnet-4.6",
            "label": "Claude Sonnet 4.6",
            "provider": "openrouter",
        },
        {
            "id": "openrouter/openai/gpt-5.4",
            "label": "GPT-5.4",
            "provider": "openrouter",
        },
        {
            "id": "openrouter/google/gemini-3.1-pro-preview",
            "label": "Gemini 3.1 Pro Preview",
            "provider": "openrouter",
        }
    ],
    "task_ids": [f"{i:02d}" for i in range(1, 12)],
    "judge_runs": 3,
    "subject_temperature": 0.6,
    "judge_temperature": 0.0,
}


def get_official_strict_preset() -> Dict[str, Any]:
    return deepcopy(_OFFICIAL_STRICT_PRESET)


def validate_official_strict_request(
    *,
    selected_tasks: List[Dict[str, Any]],
    judge_models: List[str],
    judge_runs: int,
    subject_temp: float,
    judge_system_prompt_source: str,
    preset: Dict[str, Any] | None = None,
) -> List[str]:
    strict_preset = preset or _OFFICIAL_STRICT_PRESET
    violations: List[str] = []

    actual_task_ids = sorted(task["id"] for task in selected_tasks)
    expected_task_ids = sorted(strict_preset["task_ids"])
    if actual_task_ids != expected_task_ids:
        violations.append(
            "selected_tasks mismatch "
            f"expected={','.join(expected_task_ids)} actual={','.join(actual_task_ids)}"
        )

    actual_judges = sorted(judge_models)
    expected_judges = sorted(
        judge["id"] if isinstance(judge, dict) else judge
        for judge in strict_preset["judge_models"]
    )
    if actual_judges != expected_judges:
        violations.append(
            "judge_models mismatch "
            f"expected={','.join(expected_judges)} actual={','.join(actual_judges)}"
        )

    if judge_runs != strict_preset["judge_runs"]:
        violations.append(
            f"judge_runs mismatch expected={strict_preset['judge_runs']} actual={judge_runs}"
        )

    expected_subject_temp = float(strict_preset["subject_temperature"])
    if round(float(subject_temp), 4) != round(expected_subject_temp, 4):
        violations.append(
            "subject_temp mismatch "
            f"expected={expected_subject_temp:.2f} actual={float(subject_temp):.2f}"
        )

    if judge_system_prompt_source != "bundled":
        violations.append(f"judge_system_prompt source={judge_system_prompt_source}")

    for task in sorted(selected_tasks, key=lambda item: item["id"]):
        prompt_source = str(task.get("prompt_source") or "missing")
        rubric_source = str(task.get("rubric_source") or "missing")
        if prompt_source != "bundled":
            violations.append(f"task {task['id']} prompt source={prompt_source}")
        if rubric_source != "bundled":
            violations.append(f"task {task['id']} rubric source={rubric_source}")

    return violations


def build_strict_mode_metadata(
    *,
    target_model: str,
    selected_tasks: List[Dict[str, Any]],
    judge_models: List[str],
    judge_runs: int,
    subject_temp: float,
    judge_system_prompt_path: Path,
    judge_system_prompt_source: str,
    requested: bool = False,
    preset: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    strict_preset = preset or _OFFICIAL_STRICT_PRESET
    violations = validate_official_strict_request(
        selected_tasks=selected_tasks,
        judge_models=judge_models,
        judge_runs=judge_runs,
        subject_temp=subject_temp,
        judge_system_prompt_source=judge_system_prompt_source,
        preset=strict_preset,
    )

    task_resources = []
    for task in sorted(selected_tasks, key=lambda item: item["id"]):
        prompt_path = Path(task["prompt_file"])
        rubric_path = Path(task["rubric_file"])
        task_resources.append(
            {
                "id": task["id"],
                "type": task.get("type", "fact"),
                "prompt_source": str(task.get("prompt_source") or "missing"),
                "prompt_sha256": _sha256_file(prompt_path),
                "rubric_source": str(task.get("rubric_source") or "missing"),
                "rubric_sha256": _sha256_file(rubric_path),
            }
        )

    profile_payload = {
        "strict_mode_version": STRICT_MODE_VERSION,
        "preset_id": strict_preset["id"],
        "task_ids": strict_preset["task_ids"],
        "judge_models": [
            judge["id"] if isinstance(judge, dict) else judge
            for judge in strict_preset["judge_models"]
        ],
        "judge_runs": strict_preset["judge_runs"],
        "subject_temperature": round(float(strict_preset["subject_temperature"]), 4),
        "judge_temperature": round(float(strict_preset["judge_temperature"]), 4),
        "judge_system_prompt_sha256": _sha256_file(judge_system_prompt_path),
        "task_resources": task_resources,
    }
    manifest_hash = hashlib.sha256(
        json.dumps(profile_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    profile_id = manifest_hash[:16]

    judge_ids = [
        judge["id"] if isinstance(judge, dict) else judge
        for judge in strict_preset["judge_models"]
    ]
    profile_label = (
        f"{strict_preset['label']} · {len(strict_preset['task_ids'])} tasks · "
        f"{len(judge_ids)} judges · runs x{strict_preset['judge_runs']} · "
        f"temp {float(strict_preset['subject_temperature']):.2f}"
    )

    return {
        "version": STRICT_MODE_VERSION,
        "requested": requested,
        "eligible": len(violations) == 0,
        "enforced": requested and len(violations) == 0,
        "preset_id": strict_preset["id"],
        "preset_label": strict_preset["label"],
        "profile_id": profile_id,
        "profile_label": profile_label,
        "manifest_hash": manifest_hash,
        "reasons": violations,
        "config": {
            "subject_model": target_model,
            "task_ids": [task["id"] for task in task_resources],
            "judge_models": sorted(judge_models),
            "judge_runs": judge_runs,
            "subject_temp": round(float(subject_temp), 4),
        },
        "policy": {
            "subject_model_policy": strict_preset["subject_model_policy"],
            "judge_models": deepcopy(strict_preset["judge_models"]),
            "task_ids": list(strict_preset["task_ids"]),
            "judge_runs": strict_preset["judge_runs"],
            "subject_temperature": strict_preset["subject_temperature"],
            "judge_temperature": strict_preset["judge_temperature"],
        },
        "resources": {
            "judge_system_prompt": {
                "source": judge_system_prompt_source,
                "sha256": _sha256_file(judge_system_prompt_path),
            },
            "tasks": task_resources,
        },
    }


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()
