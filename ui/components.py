"""UIコンポーネント"""

from typing import Any, Dict, List, Optional

import streamlit as st

from core.secrets_store import SecretsStore


def render_task_type_badge(task_type: str):
    """task_typeバッジを表示"""
    badge_emojis = {"fact": "🔵", "creative": "🟢", "speculative": "🟠"}
    emoji = badge_emojis.get(task_type, "⚪")
    st.markdown(f"**{emoji} {task_type.upper()}**")


def render_score_card(score_mean: float, score_std: float, label: str):
    """スコアカードを表示"""
    st.metric(label, f"{score_mean:.1f}±{score_std:.1f}")


def render_judge_family_result(result: Dict[str, Any]):
    """
    単一judgeモデルの結果を表示

    Args:
        result: judge結果辞書（runs + aggregated）
    """
    if result.get("aggregated") is None:
        st.warning("⚠️ 評価結果がありません")
        if "error" in result:
            st.error(f"エラー: {result['error']}")
        return

    agg = result["aggregated"]

    # Critical Fail警告
    if agg.get("critical_fail", False):
        st.error("🚨 Critical Failが検出されました")
        reasons = []
        for run in result.get("runs", []):
            if run.get("critical_fail") and run.get("critical_fail_reason"):
                reasons.append(run.get("critical_fail_reason"))
        if reasons:
            unique_reasons = list(dict.fromkeys(reasons))
            st.text("Critical Fail理由:")
            for reason in unique_reasons:
                st.write(f"- {reason}")

    # スコア表示（平均±標準偏差）
    col1, col2, col3 = st.columns(3)
    with col1:
        render_score_card(
            agg.get("logic_and_fact_mean", 0),
            agg.get("logic_and_fact_std", 0),
            "Logic & Fact",
        )
    with col2:
        render_score_card(
            agg.get("constraint_adherence_mean", 0),
            agg.get("constraint_adherence_std", 0),
            "Constraint",
        )
    with col3:
        render_score_card(
            agg.get("helpfulness_mean", 0), agg.get("helpfulness_std", 0), "Helpfulness"
        )

    # Total Scoreゲージ
    total_mean = agg.get("total_score_mean", 0)
    total_std = agg.get("total_score_std", 0)

    st.progress(min(total_mean / 100, 1.0))
    st.text(f"Total Score: {total_mean:.1f}±{total_std:.1f}")

    # Confidence分布
    conf_dist = agg.get("confidence_distribution", {})
    if conf_dist:
        st.write("**Confidence分布:**")
        conf_cols = st.columns(3)
        with conf_cols[0]:
            high_count = conf_dist.get("high", 0)
            st.markdown(
                f"🟢 **High: {high_count}**"
                if high_count > 0
                else f"⚪ High: {high_count}"
            )
        with conf_cols[1]:
            med_count = conf_dist.get("medium", 0)
            st.markdown(
                f"🟡 **Medium: {med_count}**"
                if med_count > 0
                else f"⚪ Medium: {med_count}"
            )
        with conf_cols[2]:
            low_count = conf_dist.get("low", 0)
            st.markdown(
                f"🔴 **Low: {low_count}**" if low_count > 0 else f"⚪ Low: {low_count}"
            )

    # Reasoning（アコーディオン）
    with st.expander("採点根拠（Reasoning）"):
        runs = result.get("runs", [])
        valid_runs = [r for r in runs if not r.get("skipped") and "error" not in r]

        for i, run in enumerate(valid_runs[:3]):  # 最大3件表示
            st.write(f"**Run {i + 1}**")
            reasoning = run.get("reasoning", {})
            if reasoning:
                for key, value in reasoning.items():
                    st.text(f"{key}: {value}")
            else:
                st.text("採点根拠なし")


def render_task_result_card(task_result: Dict[str, Any]):
    """
    タスク別結果カードを表示

    Args:
        task_result: タスク結果辞書
    """
    with st.container():
        st.subheader(task_result.get("task_name", "Unknown Task"))

        # task_typeバッジ
        task_type = task_result.get("task_type", "unknown")
        render_task_type_badge(task_type)

        # 被験LLM回答（タブ外）
        with st.expander("📝 被験LLMの回答原文"):
            st.markdown(task_result.get("response", "*回答なし*"))

        # judgeモデルごとのタブ
        judge_results = task_result.get("judge_results", {})

        if judge_results:
            tab_names = list(judge_results.keys())
            tabs = st.tabs(tab_names)

            for tab, (family, result) in zip(tabs, judge_results.items()):
                with tab:
                    render_judge_family_result(result)
        else:
            st.info("judge結果がありません")


def render_summary_stats(tasks: List[Dict[str, Any]]):
    """
    横断サマリーを表示

    Args:
        tasks: タスク結果リスト
    """
    st.header("📊 横断サマリー")

    if not tasks:
        st.info("データがありません")
        return

    # judgeモデルごとの統計
    judge_stats = {}

    for task in tasks:
        judge_results = task.get("judge_results", {})
        for model_name, result in judge_results.items():
            if model_name not in judge_stats:
                judge_stats[model_name] = {
                    "scores": [],
                    "critical_fails": 0,
                    "low_confidence": 0,
                }

            agg = result.get("aggregated")
            if agg:
                judge_stats[model_name]["scores"].append(agg.get("total_score_mean", 0))
                if agg.get("critical_fail", False):
                    judge_stats[model_name]["critical_fails"] += 1
                conf_dist = agg.get("confidence_distribution", {})
                if conf_dist.get("low", 0) > 0:
                    judge_stats[model_name]["low_confidence"] += 1

    # judgeモデルごとの平均スコア
    if judge_stats:
        st.subheader("judgeモデル別平均スコア")
        cols = st.columns(len(judge_stats))

        for col, (model_name, stats) in zip(cols, judge_stats.items()):
            with col:
                scores = stats["scores"]
                if scores:
                    avg_score = sum(scores) / len(scores)
                    st.metric(model_name, f"{avg_score:.1f}", f"{len(scores)}タスク")

    # 警告リスト
    warnings = []
    for task in tasks:
        task_name = task.get("task_name", "Unknown")
        judge_results = task.get("judge_results", {})

        for model_name, result in judge_results.items():
            agg = result.get("aggregated")
            if agg:
                # 標準偏差 > 5
                if agg.get("total_score_std", 0) > 5:
                    warnings.append(
                        f"⚠️ {task_name} / {model_name}: スコア分散大 ({agg['total_score_std']:.1f})"
                    )

                # critical fail
                if agg.get("critical_fail", False):
                    warnings.append(f"🚨 {task_name} / {model_name}: Critical Fail検出")

                # low confidence
                conf_dist = agg.get("confidence_distribution", {})
                if conf_dist.get("low", 0) > 0:
                    warnings.append(
                        f"⚡ {task_name} / {model_name}: Low Confidenceあり"
                    )

    if warnings:
        st.subheader("⚠️ 要確認リスト")
        for warning in warnings:
            st.warning(warning)
    else:
        st.success("✅ 特に問題のあるタスクはありません")


def render_sidebar(
    model_catalog: Dict[str, Any],
    previous_selection: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    サイドバーの設定パネルをレンダリング

    Returns:
        設定値の辞書
    """
    st.sidebar.header("⚙️ 実行設定")

    st.sidebar.subheader("APIキー設定")
    existing_keys = SecretsStore.load_existing()
    api_keys: Dict[str, str] = {}
    clear_providers: Dict[str, bool] = {}
    provider_labels = {
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "gemini": "Gemini",
        "openrouter": "OpenRouter",
    }

    for provider, label in provider_labels.items():
        api_keys[provider] = st.sidebar.text_input(
            f"{label} API Key",
            type="password",
            value=existing_keys.get(provider, ""),
        )

    save_disabled = not any(api_keys.values())
    save_secrets = st.sidebar.button("APIキーを保存", disabled=save_disabled)

    st.sidebar.caption("削除するキーを選択")
    for provider, label in provider_labels.items():
        clear_providers[provider] = st.sidebar.checkbox(f"{label}を削除")
    clear_secrets = st.sidebar.button("APIキーを削除")

    model_catalog = model_catalog or {}
    previous_selection = previous_selection or {}
    model_options: List[str] = []
    providers = model_catalog.get("providers", {})
    missing_keys = model_catalog.get("missing_keys", [])
    errors = model_catalog.get("errors", {})
    updated_at = model_catalog.get("updated_at")

    if updated_at:
        st.sidebar.caption(f"モデル一覧更新: {updated_at}")

    if missing_keys:
        st.sidebar.warning("APIキー未設定: " + ", ".join(sorted(set(missing_keys))))

    if errors:
        for provider, message in errors.items():
            st.sidebar.error(f"{provider} 取得失敗: {message}")

    for provider in ("openai", "anthropic", "gemini", "openrouter"):
        models = providers.get(provider, {}).get("models", [])
        for model in models:
            if model not in model_options:
                model_options.append(model)

    st.sidebar.subheader("モデル選択")

    saved_target = previous_selection.get("target_model")
    saved_judges = previous_selection.get("judge_models", [])
    if model_options:
        target_index = 0
        if saved_target in model_options:
            target_index = model_options.index(saved_target)

        target_model = st.sidebar.selectbox(
            "評価対象モデル",
            options=model_options,
            index=target_index,
            help="models APIから取得した一覧から選択します",
            key="target_model",
        )

        judge_models = st.sidebar.multiselect(
            "judgeモデル（複数選択）",
            options=model_options,
            default=[m for m in saved_judges if m in model_options],
            help="最低1モデル。3未満は警告します。",
            key="judge_models",
        )
    else:
        st.sidebar.warning("モデル一覧が空です。APIキー設定後に再取得してください。")
        target_model = st.sidebar.text_input(
            "評価対象モデル",
            value="",
            key="target_model",
        )
        judge_models_text = st.sidebar.text_input(
            "judgeモデル（カンマ区切り）",
            value="",
            key="judge_models_text",
        )
        judge_models = [
            item.strip() for item in judge_models_text.split(",") if item.strip()
        ]

    judge_models = _dedupe_models(judge_models)

    if len(judge_models) < 1:
        st.sidebar.error("judgeモデルを1つ以上選択してください")
    elif len(judge_models) < 3:
        st.sidebar.warning("judgeモデルは3つ以上を推奨します")
    elif any("gemini-3" in model.lower() for model in judge_models):
        st.sidebar.info("gemini-3系のjudgeは仕様に合わせてtemperatureを1に調整します")

    judge_runs = st.sidebar.slider(
        "judge試行回数（各モデルに適用）",
        min_value=1,
        max_value=5,
        value=int(previous_selection.get("judge_runs", 1)),
        help="選択した各judgeモデルに対して、この回数だけ評価を行います",
        key="judge_runs",
    )

    # temperature設定
    subject_temp = st.sidebar.slider(
        "Temperature（被験LLM）",
        min_value=0.0,
        max_value=1.0,
        value=float(previous_selection.get("subject_temp", 0.6)),
        step=0.1,
        key="subject_temp",
    )

    st.sidebar.text("Temperature（judge）: 0.0（固定）")
    st.sidebar.caption("judge試行回数は各モデルに適用されます")

    if st.sidebar.button("モデル一覧を再取得"):
        st.session_state.model_refresh_requested = True

    save_selection = st.sidebar.button("現在の選択を保存")

    return {
        "target_model": target_model,
        "judge_models": judge_models,
        "judge_runs": judge_runs,
        "subject_temp": subject_temp,
        "api_keys": api_keys,
        "save_secrets": save_secrets,
        "clear_secrets": clear_secrets,
        "clear_providers": clear_providers,
        "save_selection": save_selection,
    }


def _dedupe_models(models: List[str]) -> List[str]:
    seen = set()
    deduped = []
    for model in models:
        if model not in seen:
            seen.add(model)
            deduped.append(model)
    return deduped


def render_progress(current: int, total: int, message: str):
    """進捗表示"""
    progress_text = f"進捗: {current}/{total} - {message}"
    st.info(progress_text)
