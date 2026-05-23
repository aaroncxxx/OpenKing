"""帝国架构 v3.0 - 可视化大屏（Streamlit）"""
import streamlit as st
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

st.set_page_config(
    page_title="🏛️ Empire Architecture v3.0",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────── 样式 ────────────────
st.markdown("""
<style>
    .stMetric {background: #1e1e2e; border-radius: 10px; padding: 15px;}
    .metric-card {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                  border-radius: 10px; padding: 20px; color: white; text-align: center;}
    .agent-card {background: #2d2d3f; border-radius: 8px; padding: 10px; margin: 5px 0;}
    .rank-badge {background: #ffd700; color: #000; border-radius: 4px; padding: 2px 8px; font-size: 12px;}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_chancellor():
    from chancellor import Chancellor
    return Chancellor()


def main():
    chancellor = load_chancellor()

    # ──────────────── 侧边栏 ────────────────
    with st.sidebar:
        st.title("🏛️ Empire v3.0")
        st.markdown(f"**皇帝**: AARONCXXX")
        st.markdown(f"**丞相**: MIMO")
        st.markdown("---")

        page = st.radio("导航", [
            "📊 总览",
            "👥 节点管理",
            "🧠 自进化",
            "🌐 模型路由",
            "📡 实时监控",
            "🔌 插件系统",
            "💰 成本分析",
            "💬 任务执行",
        ])

    # ──────────────── 总览 ────────────────
    if page == "📊 总览":
        st.title("📊 帝国总览")

        status = chancellor.get_status()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("节点总数", len(status["agents"]))
        with col2:
            st.metric("消息总数", status["message_history"])
        with col3:
            st.metric("任务完成", status["task_queue"]["completed"])
        with col4:
            st.metric("Token 今日", chancellor.tracker.get_total_today())

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("进化评估", status["evolution"]["total_evaluations"])
        with col2:
            st.metric("进化节点", status["evolution"]["agents_tracked"])
        with col3:
            rt = status["realtime"]
            st.metric("监控规则", rt["rules"])
        with col4:
            st.metric("插件", len(status["plugins"]))

        # 节点状态分布
        st.subheader("节点状态分布")
        agents = status["agents"]
        idle = sum(1 for a in agents.values() if a["status"] == "idle")
        busy = sum(1 for a in agents.values() if a["status"] == "busy")
        error = sum(1 for a in agents.values() if a["status"] == "error")

        col1, col2, col3 = st.columns(3)
        col1.metric("🟢 空闲", idle)
        col2.metric("🟡 忙碌", busy)
        col3.metric("🔴 错误", error)

        # Top Agent
        st.subheader("🏆 Top Agent（按评分）")
        ranked = sorted(agents.items(), key=lambda x: -x[1].get("performance_score", 0))
        for aid, info in ranked[:10]:
            score = info.get("performance_score", 1.0)
            bar = "█" * int(score * 20)
            st.text(f"{info['name']:8s} {bar} {score:.2f}  完成:{info['tasks_completed']}")

    # ──────────────── 节点管理 ────────────────
    elif page == "👥 节点管理":
        st.title("👥 节点管理")

        status = chancellor.get_status()
        agents = status["agents"]

        # 筛选
        col1, col2 = st.columns(2)
        with col1:
            tag_filter = st.text_input("按标签筛选")
        with col2:
            status_filter = st.selectbox("按状态筛选", ["全部", "idle", "busy", "error"])

        for aid, info in agents.items():
            if tag_filter and tag_filter not in ",".join(info.get("tags", [])):
                continue
            if status_filter != "全部" and info["status"] != status_filter:
                continue

            icon = {"idle": "🟢", "busy": "🟡", "error": "🔴"}.get(info["status"], "⚪")
            tags = ", ".join(info.get("tags", []))

            with st.expander(f"{icon} {info['name']} ({aid}) — {info['role']}"):
                col1, col2, col3 = st.columns(3)
                col1.metric("完成", info["tasks_completed"])
                col2.metric("失败", info.get("tasks_failed", 0))
                col3.metric("评分", f"{info.get('performance_score', 1.0):.2f}")

                st.text(f"标签: {tags}")
                st.text(f"平均响应: {info.get('avg_response_time', 0):.1f}s")

                # 记忆
                mem = chancellor.agents[aid].memory if aid in chancellor.agents else None
                if mem:
                    st.text(f"记忆: 短期 {len(mem.short_term)} | 长期 {len(mem.long_term)}")

    # ──────────────── 自进化 ────────────────
    elif page == "🧠 自进化":
        st.title("🧠 自进化系统")

        evo_status = chancellor.evolution.get_all_status()

        col1, col2, col3 = st.columns(3)
        col1.metric("评估总数", evo_status["total_evaluations"])
        col2.metric("跟踪节点", evo_status["agents_tracked"])
        col3.metric("进化 Prompt", evo_status["evolved_prompts"])

        # 等级分布
        st.subheader("🏅 等级分布")
        ranks = evo_status.get("ranks", {})
        if ranks:
            rank_count = {}
            for rank in ranks.values():
                rank_count[rank] = rank_count.get(rank, 0) + 1
            st.bar_chart(rank_count)
        else:
            st.info("暂无等级数据")

        # Agent 评分排行
        st.subheader("📊 Agent 评分排行")
        for aid in chancellor.agents:
            evo = chancellor.evolution.get_agent_evolution_status(aid)
            if evo.get("evaluations", 0) > 0:
                name = chancellor.agents[aid].state.name
                col1, col2, col3, col4 = st.columns(4)
                col1.text(name)
                col2.progress(evo["avg_quality"], text=f"质量 {evo['avg_quality']:.2f}")
                col3.progress(evo["avg_speed"], text=f"速度 {evo['avg_speed']:.2f}")
                rank = evo.get("rank", "郡守")
                col4.markdown(f"`{rank}`")

    # ──────────────── 模型路由 ────────────────
    elif page == "🌐 模型路由":
        st.title("🌐 多模型路由")

        from core.model_router import get_available_models
        models = get_available_models()

        for alias, cfg in models.items():
            with st.expander(f"🤖 {alias} — {cfg['name']}"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Provider", cfg.get("provider", "?"))
                col2.metric("Max Tokens", cfg.get("max_tokens", "?"))
                col3.metric("Cost/1k", f"${cfg.get('cost_per_1k_input', 0):.4f}")

        # 模型使用统计
        st.subheader("📊 模型使用统计")
        model_stats = chancellor.tracker.get_model_stats()
        if model_stats:
            for model, stats in model_stats.items():
                st.text(f"{model}: {stats['calls']}次 输入={stats['input']} 输出={stats['output']}")
        else:
            st.info("暂无使用数据")

    # ──────────────── 实时监控 ────────────────
    elif page == "📡 实时监控":
        st.title("📡 实时监控")

        rt = chancellor.realtime.get_status()

        col1, col2 = st.columns(2)
        col1.metric("状态", "🟢 运行中" if rt["running"] else "🔴 未启动")
        col2.metric("监控规则", rt["rules"])

        if rt.get("rules_detail"):
            for r in rt["rules_detail"]:
                icon = "🟢" if r["enabled"] else "🔴"
                st.text(f"{icon} {r['name']} — 间隔 {r['interval']}s")

        st.info("在 config.json 的 realtime 部分配置监控规则和 Webhook")

    # ──────────────── 插件系统 ────────────────
    elif page == "🔌 插件系统":
        st.title("🔌 插件系统")

        plugins = chancellor.plugins.discover_plugins()
        if plugins:
            for p in plugins:
                loaded = p["_id"] in chancellor.plugins.loaded_plugins
                icon = "✅" if loaded else "⬜"
                st.text(f"{icon} {p.get('name', p['_id'])} v{p.get('version', '?')}")
        else:
            st.info("暂无插件。将插件放入 plugins/ 目录即可发现。")

        st.markdown("---")
        st.subheader("从 ClawHub 安装")
        slug = st.text_input("插件 slug")
        if st.button("安装") and slug:
            with st.spinner(f"安装 {slug}..."):
                success = chancellor.install_plugin(slug)
                if success:
                    st.success(f"✅ {slug} 安装成功")
                else:
                    st.error(f"❌ {slug} 安装失败")

    # ──────────────── 成本分析 ────────────────
    elif page == "💰 成本分析":
        st.title("💰 成本分析")

        cost = chancellor.tracker.get_cost_summary()
        if cost:
            total_cost = sum(c["cost"] for c in cost.values())
            total_calls = sum(c["calls"] for c in cost.values())
            st.metric("今日总成本", f"${total_cost:.4f}")
            st.metric("总调用次数", total_calls)

            st.subheader("按模型")
            for model, stats in cost.items():
                col1, col2, col3 = st.columns(3)
                col1.text(model)
                col2.metric("调用", stats["calls"])
                col3.metric("成本", f"${stats['cost']:.4f}")
        else:
            st.info("暂无成本数据")

    # ──────────────── 任务执行 ────────────────
    elif page == "💬 任务执行":
        st.title("💬 任务执行")

        command = st.text_area("下达指令", height=100)
        autonomous = st.checkbox("🤖 自治模式（多轮迭代）")

        if st.button("⚡ 执行") and command:
            with st.spinner("丞相编排中..."):
                import asyncio
                result = asyncio.run(chancellor.receive_command(command, autonomous=autonomous))

            st.success(f"✅ 任务 {result['task_id']} 完成 ({result['elapsed_seconds']}s)")

            if autonomous:
                st.info(f"🔄 迭代 {result.get('iterations', 1)} 次 | 评分 {result.get('score', 0):.2f}")

            st.subheader("丞相汇总")
            st.markdown(result["results"].get("chancellor_summary", "无汇总"))

            st.subheader("各节点结果")
            for aid, content in result["results"].items():
                if aid == "chancellor_summary":
                    continue
                agent = chancellor.agents.get(aid)
                name = agent.state.name if agent else aid
                with st.expander(f"🔸 {name}"):
                    st.text(content[:1000])


if __name__ == "__main__":
    main()
