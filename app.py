"""LLMベンチマークアプリケーション

StreamlitベースのUIで、タスク固有ルーブリックに基づく
LLM自動評価を実行します。
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
from dotenv import load_dotenv

from adapters import (
    get_adapter_for_model,
    get_available_judge_adapters,
)
from core import BenchmarkEngine, ResultStorage
from core.model_catalog import ModelCatalog
from core.selection_store import SelectionStore
from core.secrets_store import SecretsStore
from ui.components import (
    render_sidebar,
    render_task_result_card,
    render_summary_stats,
)

# .envファイル読み込み
load_dotenv()

# ページ設定
st.set_page_config(
    page_title="LLM Benchmark",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)


RUBRICS_DIR_ENV = "LLM_BENCHMARK_RUBRICS_DIR"
PROMPTS_DIR_ENV = "LLM_BENCHMARK_PROMPTS_DIR"
JUDGE_SYSTEM_PROMPT_ENV = "LLM_BENCHMARK_JUDGE_SYSTEM_PROMPT_PATH"


def _resolve_dir_path(
    env_name: str, default_path: Path, label: str, warnings: List[str]
) -> Path:
    env_value = os.getenv(env_name)
    if env_value:
        candidate = Path(env_value)
        if candidate.exists() and candidate.is_dir():
            return candidate
        warnings.append(
            f"{label}ディレクトリの指定が無効です: {env_value}。既定の '{default_path}' を使用します。"
        )
    return default_path


def _resolve_file_path(
    env_name: str, default_path: Path, label: str, warnings: List[str]
) -> Path:
    env_value = os.getenv(env_name)
    if env_value:
        candidate = Path(env_value)
        if candidate.exists() and candidate.is_file():
            return candidate
        warnings.append(
            f"{label}の指定が無効です: {env_value}。既定の '{default_path}' を使用します。"
        )
    return default_path


def resolve_resource_paths() -> Dict[str, Any]:
    warnings: List[str] = []
    rubrics_dir = _resolve_dir_path(
        RUBRICS_DIR_ENV, Path("rubrics"), "ルーブリック", warnings
    )
    prompts_dir = _resolve_dir_path(
        PROMPTS_DIR_ENV, Path("prompts"), "プロンプト", warnings
    )
    judge_system_prompt_path = _resolve_file_path(
        JUDGE_SYSTEM_PROMPT_ENV,
        Path("judge_system_prompt.md"),
        "judgeシステムプロンプト",
        warnings,
    )
    return {
        "rubrics_dir": rubrics_dir,
        "prompts_dir": prompts_dir,
        "judge_system_prompt_path": judge_system_prompt_path,
        "warnings": warnings,
    }


def load_tasks(rubrics_dir: Path, prompts_dir: Path) -> List[Dict[str, str]]:
    """タスクリストを読み込み"""
    tasks = []

    if not rubrics_dir.exists() or not prompts_dir.exists():
        return tasks

    # ルーブリックファイルを列挙
    for rubric_file in sorted(rubrics_dir.glob("*.md")):
        task_id = rubric_file.stem
        prompt_file = prompts_dir / f"{task_id}.md"

        if prompt_file.exists():
            # ルーブリックからtask_typeを抽出
            task_type = "fact"  # デフォルト
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


def load_judge_system_prompt(prompt_file: Path) -> str:
    """judgeシステムプロンプトを読み込み"""
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return ""


def initialize_session_state():
    """セッション状態を初期化"""
    if "benchmark_running" not in st.session_state:
        st.session_state.benchmark_running = False
    if "results" not in st.session_state:
        st.session_state.results = None
    if "progress_message" not in st.session_state:
        st.session_state.progress_message = ""
    if "progress_current" not in st.session_state:
        st.session_state.progress_current = 0
    if "progress_total" not in st.session_state:
        st.session_state.progress_total = 0
    if "progress_detail" not in st.session_state:
        st.session_state.progress_detail = "待機中"
    if "model_catalog" not in st.session_state:
        st.session_state.model_catalog = None
    if "model_refresh_requested" not in st.session_state:
        st.session_state.model_refresh_requested = False
    if "secrets_saved" not in st.session_state:
        st.session_state.secrets_saved = False
    if "secrets_cleared" not in st.session_state:
        st.session_state.secrets_cleared = False
    if "previous_selection" not in st.session_state:
        st.session_state.previous_selection = SelectionStore.load()
    if "selected_tasks" not in st.session_state:
        st.session_state.selected_tasks = st.session_state.previous_selection.get(
            "selected_tasks", []
        )
    if "cancel_requested" not in st.session_state:
        st.session_state.cancel_requested = False


class CancelledError(Exception):
    """ユーザーによるキャンセル"""

    pass


def update_progress(
    message: str, current: Optional[int] = None, total: Optional[int] = None
):
    """進捗メッセージを更新"""
    if current is not None:
        st.session_state.progress_current = current
    if total is not None:
        st.session_state.progress_total = total
    st.session_state.progress_detail = message

    progress_bar = st.session_state.get("progress_bar")
    progress_text = st.session_state.get("progress_text")
    if progress_bar is None or progress_text is None:
        return

    if st.session_state.progress_total:
        progress_value = min(
            st.session_state.progress_current / st.session_state.progress_total, 1.0
        )
    else:
        progress_value = 0.0

    progress_bar.progress(progress_value)
    progress_text.caption(st.session_state.progress_detail)


def _check_cancel() -> None:
    if st.session_state.cancel_requested:
        raise CancelledError("ユーザーによってキャンセルされました")


def advance_progress(message: str, step: int = 1) -> None:
    _check_cancel()
    current = st.session_state.progress_current + step
    update_progress(
        message,
        current=current,
        total=st.session_state.progress_total,
    )


def _save_current_selection() -> None:
    judge_models = st.session_state.get("judge_models", [])
    if not judge_models and st.session_state.get("judge_models_text"):
        judge_models = [
            item.strip()
            for item in st.session_state.get("judge_models_text", "").split(",")
            if item.strip()
        ]

    SelectionStore.save(
        {
            "target_model": st.session_state.get("target_model"),
            "judge_models": judge_models,
            "judge_runs": st.session_state.get("judge_runs", 1),
            "subject_temp": st.session_state.get("subject_temp", 0.6),
            "selected_tasks": st.session_state.get("selected_tasks", []),
        }
    )
    st.session_state.previous_selection = SelectionStore.load()


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


async def run_benchmark(
    target_model: str,
    selected_task_ids: List[str],
    judge_runs: int,
    subject_temp: float,
    judge_models: List[str],
    tasks: List[Dict[str, str]],
    system_prompt: str,
) -> Dict[str, Any]:
    """
    ベンチマークを実行

    Args:
        target_model: 評価対象モデル名
        selected_task_ids: 選択されたタスクIDリスト
        judge_runs: judge実行回数
        subject_temp: 被験LLM temperature
        tasks: 全タスクリスト

    Returns:
        ベンチマーク結果
    """
    api_keys = SecretsStore.load_existing()

    _check_cancel()

    # 被験LLMアダプタ取得
    subject_adapter = get_adapter_for_model(
        target_model, api_key=_resolve_subject_key(target_model, api_keys)
    )
    if subject_adapter is None:
        raise ValueError(f"モデル '{target_model}' に対応するアダプタが見つかりません")

    if not subject_adapter.is_available():
        raise ValueError(f"モデル '{target_model}' のAPIキーが設定されていません")

    _check_cancel()

    # judgeアダプタ取得
    judge_adapters = get_available_judge_adapters(judge_models, api_keys=api_keys)
    if not judge_adapters:
        raise ValueError("選択されたjudgeモデルに対応するAPIキーがありません")

    _check_cancel()

    # エンジン初期化
    engine = BenchmarkEngine(
        subject_adapter=subject_adapter,
        subject_model=target_model,
        judge_adapters=judge_adapters,
        judge_runs=judge_runs,
        max_parallel_judges=5,
    )

    # タスク実行
    task_results = []
    total_tasks = len(selected_task_ids)
    total_steps = total_tasks * (2 + len(judge_adapters) * judge_runs)

    update_progress("評価を開始します", current=0, total=total_steps)

    cancelled = False
    cancel_reason = None

    try:
        for i, task_id in enumerate(selected_task_ids):
            # タスク情報取得
            _check_cancel()
            task_info = next((t for t in tasks if t["id"] == task_id), None)
            if task_info is None:
                continue

            # ファイル読み込み
            _check_cancel()
            rubric_content = Path(task_info["rubric_file"]).read_text(encoding="utf-8")
            input_prompt = Path(task_info["prompt_file"]).read_text(encoding="utf-8")

            # タスク実行
            _check_cancel()
            result = await engine.run_task(
                task_name=task_id,
                task_type=task_info["type"],
                input_prompt=input_prompt,
                rubric_content=rubric_content,
                system_prompt=system_prompt,
                subject_temp=subject_temp,
                progress_callback=lambda msg: advance_progress(
                    f"タスク {i + 1}/{total_tasks}: {msg}"
                ),
                cancel_checker=_check_cancel,
            )

            task_results.append(result.to_dict())
    except CancelledError as e:
        cancelled = True
        cancel_reason = str(e)

    # 結果構築
    import time

    benchmark_result = {
        "run_id": f"{time.strftime('%Y%m%d_%H%M%S')}_{target_model}",
        "target_model": target_model,
        "judge_models": judge_models,
        "judge_runs": judge_runs,
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tasks": task_results,
        "cancelled": cancelled,
        "cancel_reason": cancel_reason,
        "completed_tasks": len(task_results),
        "total_tasks": total_tasks,
    }

    if cancelled:
        update_progress(
            "評価をキャンセルしました",
            current=st.session_state.progress_current,
            total=total_steps,
        )
    else:
        update_progress(
            "評価が完了しました",
            current=total_steps,
            total=total_steps,
        )
    return benchmark_result


def main():
    """メインアプリケーション"""
    st.title("🧪 LLM Benchmark")
    st.markdown("タスク固有ルーブリックに基づくLLM自動評価ツール")

    # セッション状態初期化
    initialize_session_state()

    # リソース解決
    resource_paths = resolve_resource_paths()
    if resource_paths["warnings"]:
        for warning in resource_paths["warnings"]:
            st.warning(warning)

    # タスク読み込み
    tasks = load_tasks(resource_paths["rubrics_dir"], resource_paths["prompts_dir"])

    # judgeシステムプロンプト読み込み
    system_prompt = load_judge_system_prompt(resource_paths["judge_system_prompt_path"])

    # モデル一覧の初期化
    if st.session_state.model_catalog is None:
        st.session_state.model_catalog = ModelCatalog.update()

    # サイドバー
    with st.sidebar:
        settings = render_sidebar(
            st.session_state.model_catalog,
            st.session_state.previous_selection,
        )

        if settings.get("save_secrets"):
            api_keys = settings.get("api_keys", {})
            if not any(api_keys.values()):
                st.error("APIキーが入力されていません")
            else:
                SecretsStore.save(api_keys)
                load_dotenv(override=True)
                st.session_state.model_catalog = ModelCatalog.update()
                st.success("APIキーを保存しました")
                st.rerun()

        if settings.get("clear_secrets"):
            clear_providers = settings.get("clear_providers", {})
            if not any(clear_providers.values()):
                st.error("削除するプロバイダを選択してください")
            else:
                SecretsStore.clear(clear_providers)
                load_dotenv(override=True)
                st.session_state.model_catalog = ModelCatalog.update()
                st.success("APIキーを削除しました")
                st.rerun()

        if st.session_state.model_refresh_requested:
            st.session_state.model_catalog = ModelCatalog.update()
            st.session_state.model_refresh_requested = False
            st.success("モデル一覧を更新しました")
            st.rerun()

        if settings.get("save_selection"):
            _save_current_selection()
            st.success("選択内容を保存しました")
            st.rerun()

        st.divider()

        # タスク選択
        st.subheader("タスク選択")
        task_options = {t["id"]: f"{t['id']} ({t['type']})" for t in tasks}

        if st.button("全選択"):
            st.session_state.selected_tasks = list(task_options.keys())

        if st.button("全解除"):
            st.session_state.selected_tasks = []

        saved_tasks = st.session_state.previous_selection.get("selected_tasks", [])
        default_tasks = (
            [task_id for task_id in saved_tasks if task_id in task_options]
            if saved_tasks
            else st.session_state.selected_tasks
        )

        st.multiselect(
            "評価するタスク",
            options=list(task_options.keys()),
            format_func=lambda x: task_options.get(x, x) or x,
            default=default_tasks,
            key="selected_tasks",
        )

        st.divider()

        # 過去結果読み込み
        st.subheader("過去の結果")
        result_files = ResultStorage.list_results()

        if result_files:
            result_options = {str(f): f.name for f in result_files[:10]}  # 最新10件
            selected_result = st.selectbox(
                "結果を選択",
                options=[""] + list(result_options.keys()),
                format_func=lambda x: (
                    "選択してください" if x == "" else result_options.get(x, x) or x
                ),
            )

            if selected_result and st.button("読み込み"):
                try:
                    data = ResultStorage.load(Path(selected_result))
                    st.session_state.results = data
                    st.success("結果を読み込みました")
                    st.rerun()
                except Exception as e:
                    st.error(f"読み込みエラー: {e}")
        else:
            st.info("保存済みの結果はありません")

    # メインコンテンツ
    if not tasks:
        st.warning(
            "⚠️ タスクファイルが見つかりません。rubrics/ と prompts/ ディレクトリ、または環境変数の指定を確認してください。"
        )
        return

    # 進捗表示（常時）
    if "progress_bar" not in st.session_state:
        st.session_state.progress_bar = st.progress(0.0)
    if "progress_text" not in st.session_state:
        st.session_state.progress_text = st.empty()

    update_progress(
        st.session_state.progress_detail,
        current=st.session_state.progress_current,
        total=st.session_state.progress_total,
    )

    # 実行ボタン
    if st.session_state.selected_tasks:
        st.info(f"選択されたタスク: {len(st.session_state.selected_tasks)}件")

        progress_container = st.empty()

        cancel_clicked = st.button(
            "🛑 キャンセル",
            disabled=not st.session_state.benchmark_running,
        )
        if cancel_clicked:
            st.session_state.cancel_requested = True

        if st.button(
            "🚀 評価を開始", type="primary", disabled=st.session_state.benchmark_running
        ):
            st.session_state.benchmark_running = True
            st.session_state.cancel_requested = False

            try:
                with st.spinner("評価を実行中..."):
                    # 非同期実行
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    result = loop.run_until_complete(
                        run_benchmark(
                            target_model=settings["target_model"],
                            selected_task_ids=st.session_state.selected_tasks,
                            judge_runs=settings["judge_runs"],
                            subject_temp=settings["subject_temp"],
                            judge_models=settings["judge_models"],
                            tasks=tasks,
                            system_prompt=system_prompt,
                        )
                    )

                    st.session_state.results = result

                    # 結果保存
                    saved_path = ResultStorage.save(result)
                    st.success(f"✅ 評価完了！結果を保存しました: {saved_path}")

            except Exception as e:
                st.error(f"❌ エラーが発生しました: {str(e)}")
                import traceback

                st.code(traceback.format_exc())
            finally:
                st.session_state.benchmark_running = False
                progress_container.empty()
    else:
        st.info("👈 サイドバーから評価するタスクを選択してください")

    # 進捗メッセージ表示
    if st.session_state.progress_message:
        st.info(st.session_state.progress_message)

    # 結果表示
    if st.session_state.results:
        results = st.session_state.results

        st.divider()
        st.header(f"📋 評価結果: {results['target_model']}")
        if results.get("cancelled"):
            st.warning(
                "🛑 この評価は途中で中断されました（完了タスク数: "
                f"{results.get('completed_tasks', 0)}/{results.get('total_tasks', 0)}）"
            )
        st.text(f"実行日時: {results['executed_at']}")
        st.text(f"judgeモデル: {results['judge_models']}")

        # タブで結果を表示
        result_tabs = st.tabs(["タスク別結果", "横断サマリー"])

        with result_tabs[0]:
            # タスク別結果
            for task_result in results["tasks"]:
                render_task_result_card(task_result)
                st.divider()

        with result_tabs[1]:
            # 横断サマリー
            render_summary_stats(results["tasks"])


if __name__ == "__main__":
    main()
