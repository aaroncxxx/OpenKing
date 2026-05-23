"""帝国架构 v3.2 - 完整 Web 管理界面（Streamlit）

功能模块：
- 实时任务进度 | Agent 状态面板 | 消息总线可视化
- Token 消耗统计 | 记忆系统监控 | 安全审计面板
- 进化状态 | 检查点管理
"""
import streamlit as st
import json
import os
import sys
import time
import glob
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

st.set_page_config(
    page_title="🏛️ Empire Architecture v3.2",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────── 全局样式 ────────────────
st.markdown("""
<style>
    .stMetric {background: #1e1e2e; border-radius: 10px; padding: 15px;}
    .metric-card {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                  border-radius: 10px; padding: 20px; color: white; text-align: center;}
    .agent-card {background: #2d2d3f; border-radius: 8px; padding: 10px; margin: 5px 0;}
    .rank-badge {background: #ffd700; color: #000; border-radius: 4px; padding: 2px 8px; font-size: 12px;}
    .msg-flow {border-left: 3px solid #667eea; padding: 4px 12px; margin: 2px 0;
               font-family: monospace; font-size: 13px; background: #1a1a2e; border-radius: 0 6px 6px 0;}
    .msg-cmd {border-left-color: #f39c12;}
    .msg-result {border-left-color: #27ae60;}
    .msg-event {border-left-color: #3498db;}
    .msg-broadcast {border-left-color: #e74c3c;}
    .checkpoint-card {background: #1e1e2e; border: 1px solid #333; border-radius: 8px; padding: 12px; margin: 4px 0;}
    .audit-entry {font-family: monospace; font-size: 12px; padding: 3px 8px; border-bottom: 1px solid #222;}
    .health-ok {color: #27ae60; font-weight: bold;}
    .health-warn {color: #f39c12; font-weight: bold;}
    .health-err {color: #e74c3c; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# ──────────────── 数据目录 ────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
LOG_DIR = os.path.join(DATA_DIR, "logs")
MEMORY_DIR = os.path.join(DATA_DIR, "memory")
EVOLUTION_DIR = os.path.join(DATA_DIR, "evolution")
CHECKPOINT_DIR = os.path.join(DATA_DIR, "checkpoints")
TOKEN_DB = os.path.join(DATA_DIR, "tokens.db")


# ──────────────── 工具函数 ────────────────
def _safe_json_load(path: str, default=None):
    """安全加载 JSON 文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def _read_log_lines(log_name: str, max_lines: int = 200) -> list[str]:
    """读取日志文件尾部"""
    path = os.path.join(LOG_DIR, f"{log_name}.log")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return lines[-max_lines:]
    except Exception:
        return []


def _get_token_db_connection():
    """获取 Token 数据库连接"""
    if not os.path.exists(TOKEN_DB):
        return None
    try:
        conn = sqlite3.connect(TOKEN_DB)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


def _time_ago(ts: float) -> str:
    """时间差可读化"""
    diff = time.time() - ts
    if diff < 60:
        return f"{diff:.0f}s ago"
    elif diff < 3600:
        return f"{diff / 60:.0f}m ago"
    elif diff < 86400:
        return f"{diff / 3600:.1f}h ago"
    else:
        return f"{diff / 86400:.1f}d ago"


# ──────────────── 缓存加载 ────────────────
@st.cache_resource
def load_chancellor():
    from chancellor import Chancellor
    return Chancellor()


def get_chancellor():
    """延迟加载 chancellor，失败返回 None"""
    try:
        return load_chancellor()
    except Exception:
        return None


# ══════════════════════════════════════════════
#  侧边栏导航
# ══════════════════════════════════════════════
def sidebar():
    with st.sidebar:
        st.title("🏛️ Empire v3.2")
        st.caption(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        chancellor = get_chancellor()
        if chancellor:
            st.markdown(f"**皇帝**: AARONCXXX  \n**丞相**: MIMO")
        else:
            st.warning("丞相离线")

        st.markdown("---")

        page = st.radio("📡 导航", [
            "📊 总览",
            "⚡ 实时任务",
            "👥 Agent 面板",
            "💬 消息总线",
            "💰 Token 统计",
            "🧠 记忆系统",
            "🔒 安全审计",
            "🧬 进化状态",
            "📸 检查点管理",
            "🌐 模型路由",
            "🔌 插件系统",
            "💬 任务执行",
        ], label_visibility="collapsed")

        st.markdown("---")
        st.caption("帝国架构 v3.2 · 开发者体验提升")

    return page


# ══════════════════════════════════════════════
#  📊 总览
# ══════════════════════════════════════════════
def page_overview():
    st.title("📊 帝国总览")

    chancellor = get_chancellor()
    if not chancellor:
        st.error("丞相系统未就绪")
        _show_static_overview()
        return

    status = chancellor.get_status()

    # 核心指标
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
    agents = status["agents"]
    idle = sum(1 for a in agents.values() if a["status"] == "idle")
    busy = sum(1 for a in agents.values() if a["status"] == "busy")
    error = sum(1 for a in agents.values() if a["status"] == "error")

    st.subheader("节点状态分布")
    c1, c2, c3 = st.columns(3)
    c1.metric("🟢 空闲", idle)
    c2.metric("🟡 忙碌", busy)
    c3.metric("🔴 错误", error)

    # Top Agent
    st.subheader("🏆 Top Agent（按评分）")
    ranked = sorted(agents.items(), key=lambda x: -x[1].get("performance_score", 0))
    for aid, info in ranked[:10]:
        score = info.get("performance_score", 1.0)
        bar = "█" * int(score * 20)
        st.text(f"{info['name']:12s} {bar} {score:.2f}  完成:{info['tasks_completed']}")


def _show_static_overview():
    """离线模式静态总览"""
    st.info("以静态模式展示数据文件")

    # 统计日志文件
    log_files = glob.glob(os.path.join(LOG_DIR, "*.log"))
    col1, col2, col3 = st.columns(3)
    col1.metric("日志文件", len(log_files))

    # 统计记忆文件
    mem_files = glob.glob(os.path.join(MEMORY_DIR, "*.json"))
    col2.metric("Agent 记忆", len(mem_files))

    # 统计进化数据
    evo_data = _safe_json_load(os.path.join(EVOLUTION_DIR, "evaluations.json"), [])
    col3.metric("进化评估", len(evo_data))


# ══════════════════════════════════════════════
#  ⚡ 实时任务
# ══════════════════════════════════════════════
def page_realtime_tasks():
    st.title("⚡ 实时任务进度")

    chancellor = get_chancellor()
    if not chancellor:
        st.warning("丞相离线，展示静态数据")
        _show_static_tasks()
        return

    tq = chancellor.task_queue
    status = chancellor.get_status()
    tq_status = status["task_queue"]

    # 任务概览
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("等待中", tq_status.get("pending", 0))
    col2.metric("执行中", tq_status.get("running", 0))
    col3.metric("已完成", tq_status.get("completed", 0))
    col4.metric("失败", tq_status.get("failed", 0))

    st.markdown("---")

    # 执行中的任务 — 实时进度
    st.subheader("🔄 当前执行中")
    running_tasks = [t for t in tq.tasks.values() if t.status.value == "running"]
    if running_tasks:
        for task in running_tasks:
            elapsed = time.time() - task.started_at if task.started_at else 0
            progress = min(elapsed / 120.0, 0.95)  # 假设 120s 上限，进度条不封顶

            with st.container():
                c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                c1.markdown(f"**{task.task_id}** → `{task.agent_id}`")
                c2.metric("耗时", f"{elapsed:.1f}s")
                c3.metric("优先级", f"P{task.priority}")
                c4.metric("重试", task.retries)
                st.progress(progress, text=f"执行中... {elapsed:.0f}s")
                st.caption(f"Prompt: {task.prompt[:120]}...")
                st.markdown("---")
    else:
        st.success("✅ 没有正在执行的任务")

    # 最近完成的任务
    st.subheader("📋 最近完成")
    completed = sorted(
        [t for t in tq.tasks.values() if t.status.value == "completed"],
        key=lambda x: -x.completed_at
    )[:20]
    if completed:
        for task in completed:
            duration = (task.completed_at - task.started_at) if task.started_at else 0
            icon = "✅" if not task.error else "⚠️"
            with st.expander(f"{icon} {task.task_id} — {task.agent_id} ({duration:.1f}s)"):
                st.text(f"Prompt: {task.prompt[:200]}")
                if task.result:
                    st.text_area("结果", task.result[:500], height=100, key=f"res_{task.task_id}")
                if task.error:
                    st.error(task.error[:200])
    else:
        st.info("暂无已完成任务")

    # 失败的任务
    st.subheader("❌ 失败任务")
    failed = sorted(
        [t for t in tq.tasks.values() if t.status.value == "failed"],
        key=lambda x: -x.completed_at
    )[:10]
    if failed:
        for task in failed:
            st.error(f"**{task.task_id}** → `{task.agent_id}`: {task.error[:150]}")
    else:
        st.success("✅ 无失败任务")


def _show_static_tasks():
    """离线模式查看任务日志"""
    lines = _read_log_lines("taskqueue", 100)
    if lines:
        for line in lines[-30:]:
            st.text(line.rstrip())
    else:
        st.info("无任务日志")


# ══════════════════════════════════════════════
#  👥 Agent 面板
# ══════════════════════════════════════════════
def page_agent_panel():
    st.title("👥 Agent 状态面板")

    chancellor = get_chancellor()
    if not chancellor:
        st.error("丞相离线")
        return

    status = chancellor.get_status()
    agents = status["agents"]

    # 筛选栏
    col1, col2, col3 = st.columns(3)
    with col1:
        tag_filter = st.text_input("🏷️ 按标签筛选")
    with col2:
        status_filter = st.selectbox("📡 按状态筛选", ["全部", "idle", "busy", "error"])
    with col3:
        sort_by = st.selectbox("📊 排序", ["评分↓", "完成数↓", "名称↑"])

    # 排序
    items = list(agents.items())
    if sort_by == "评分↓":
        items.sort(key=lambda x: -x[1].get("performance_score", 0))
    elif sort_by == "完成数↓":
        items.sort(key=lambda x: -x[1].get("tasks_completed", 0))
    else:
        items.sort(key=lambda x: x[1].get("name", ""))

    for aid, info in items:
        # 筛选
        if tag_filter and tag_filter not in ",".join(info.get("tags", [])):
            continue
        if status_filter != "全部" and info["status"] != status_filter:
            continue

        icon = {"idle": "🟢", "busy": "🟡", "error": "🔴"}.get(info["status"], "⚪")
        score = info.get("performance_score", 1.0)
        rank = "N/A"

        # 获取进化信息
        try:
            evo = chancellor.evolution.get_agent_evolution_status(aid)
            rank = evo.get("rank", "N/A")
        except Exception:
            pass

        tags = ", ".join(info.get("tags", []))

        with st.expander(f"{icon} {info['name']} ({aid}) — {info['role']} | 评分 {score:.2f} | 等级 {rank}"):
            # 核心指标
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("完成", info["tasks_completed"])
            c2.metric("失败", info.get("tasks_failed", 0))
            c3.metric("评分", f"{score:.2f}")
            c4.metric("等级", rank)

            c1, c2, c3 = st.columns(3)
            c1.metric("平均响应", f"{info.get('avg_response_time', 0):.1f}s")
            c2.metric("状态", info["status"])
            c3.metric("标签", tags if tags else "无")

            # 记忆统计
            agent_obj = chancellor.agents.get(aid)
            if agent_obj and hasattr(agent_obj, "memory"):
                mem = agent_obj.memory
                mc1, mc2 = st.columns(2)
                mc1.metric("短期记忆", len(mem.short_term))
                mc2.metric("长期记忆", len(mem.long_term))

                # 最近记忆
                recent = mem.recall_recent(3)
                if recent:
                    st.markdown("**最近记忆:**")
                    for r in recent:
                        st.caption(f"• {r[:100]}")

            # 进化历史
            try:
                evo_data = chancellor.evolution.get_agent_evolution_status(aid)
                if evo_data.get("evaluations", 0) > 0:
                    st.markdown("**进化指标:**")
                    ec1, ec2, ec3 = st.columns(3)
                    ec1.progress(evo_data.get("avg_quality", 0), text=f"质量 {evo_data.get('avg_quality', 0):.2f}")
                    ec2.progress(evo_data.get("avg_speed", 0), text=f"速度 {evo_data.get('avg_speed', 0):.2f}")
                    ec3.metric("评估次数", evo_data.get("evaluations", 0))
            except Exception:
                pass


# ══════════════════════════════════════════════
#  💬 消息总线可视化
# ══════════════════════════════════════════════
def page_message_bus():
    st.title("💬 消息总线可视化")

    chancellor = get_chancellor()
    if not chancellor:
        st.error("丞相离线")
        _show_static_messages()
        return

    bus = chancellor.bus

    # 统计
    col1, col2 = st.columns(2)
    col1.metric("总发送", bus._stats.get("sent", 0))
    col2.metric("总接收", bus._stats.get("received", 0))

    # 消息类型筛选
    msg_type_filter = st.selectbox("消息类型", ["全部", "command", "result", "query", "response", "event", "broadcast", "direct"])

    # 消息流
    st.subheader("📡 实时消息流")

    history = list(bus.history)
    if msg_type_filter != "全部":
        history = [m for m in history if m.msg_type.value == msg_type_filter]

    # 显示最近 50 条
    for msg in history[-50:]:
        type_class = {
            "command": "msg-cmd", "result": "msg-result",
            "event": "msg-event", "broadcast": "msg-broadcast",
        }.get(msg.msg_type.value, "")

        type_icon = {
            "command": "📤", "result": "📥", "query": "❓",
            "response": "💬", "event": "⚡", "broadcast": "📢",
            "direct": "➡️",
        }.get(msg.msg_type.value, "📨")

        ts = datetime.fromtimestamp(msg.timestamp).strftime("%H:%M:%S")
        content_preview = msg.content[:80].replace("\n", " ")

        st.markdown(
            f'<div class="msg-flow {type_class}">'
            f'{type_icon} <code>{ts}</code> '
            f'<b>{msg.sender}</b> → <b>{msg.receiver}</b> '
            f'[{msg.msg_type.value}] {content_preview}</div>',
            unsafe_allow_html=True,
        )

    if not history:
        st.info("暂无消息记录")

    # Agent 通信矩阵
    st.subheader("🔗 Agent 通信矩阵")
    if history:
        matrix = defaultdict(lambda: defaultdict(int))
        for msg in history:
            matrix[msg.sender][msg.receiver] += 1

        # 简化矩阵展示
        all_agents = sorted(set(list(matrix.keys()) + [r for targets in matrix.values() for r in targets]))
        if all_agents:
            import pandas as pd
            df_data = []
            for sender in all_agents:
                row = {"发送方": sender}
                for receiver in all_agents:
                    row[receiver] = matrix[sender].get(receiver, 0)
                df_data.append(row)
            df = pd.DataFrame(df_data).set_index("发送方")
            st.dataframe(df, use_container_width=True)


def _show_static_messages():
    """离线消息展示"""
    lines = _read_log_lines("chancellor", 50)
    if lines:
        for line in lines[-30:]:
            st.text(line.rstrip())
    else:
        st.info("无消息日志")


# ══════════════════════════════════════════════
#  💰 Token 统计
# ══════════════════════════════════════════════
def page_token_stats():
    st.title("💰 Token 消耗统计")

    chancellor = get_chancellor()

    # 从 SQLite 读取数据
    conn = _get_token_db_connection()
    if not conn:
        st.warning("Token 数据库不存在或无法访问")
        if chancellor:
            _show_tracker_stats(chancellor)
        return

    # 时间范围选择
    time_range = st.selectbox("时间范围", ["今天", "最近 7 天", "最近 30 天", "全部"])
    now = time.time()
    if time_range == "今天":
        since = now - 86400
    elif time_range == "最近 7 天":
        since = now - 7 * 86400
    elif time_range == "最近 30 天":
        since = now - 30 * 86400
    else:
        since = 0

    try:
        # 总量统计
        row = conn.execute(
            "SELECT COUNT(*) as cnt, SUM(input_tokens) as inp, SUM(output_tokens) as outp, SUM(cost) as cost "
            "FROM token_usage WHERE timestamp >= ?", (since,)
        ).fetchone()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("调用次数", row["cnt"] or 0)
        col2.metric("输入 Token", f"{(row['inp'] or 0):,}")
        col3.metric("输出 Token", f"{(row['outp'] or 0):,}")
        col4.metric("总成本", f"${(row['cost'] or 0):.4f}")

        # 按模型统计
        st.subheader("📊 按模型")
        model_rows = conn.execute(
            "SELECT model, COUNT(*) as cnt, SUM(input_tokens) as inp, SUM(output_tokens) as outp, SUM(cost) as cost "
            "FROM token_usage WHERE timestamp >= ? GROUP BY model ORDER BY cost DESC", (since,)
        ).fetchall()

        if model_rows:
            import pandas as pd
            df = pd.DataFrame([dict(r) for r in model_rows])
            df.columns = ["模型", "调用次数", "输入Token", "输出Token", "成本"]
            st.dataframe(df, use_container_width=True)

            # 饼图
            if df["成本"].sum() > 0:
                st.subheader("💸 成本分布")
                chart_data = df.set_index("模型")["成本"]
                st.bar_chart(chart_data)

        # 按 Agent 统计
        st.subheader("📊 按 Agent")
        agent_rows = conn.execute(
            "SELECT agent_id, COUNT(*) as cnt, SUM(input_tokens) as inp, SUM(output_tokens) as outp, SUM(cost) as cost "
            "FROM token_usage WHERE timestamp >= ? GROUP BY agent_id ORDER BY cost DESC", (since,)
        ).fetchall()

        if agent_rows:
            import pandas as pd
            df = pd.DataFrame([dict(r) for r in agent_rows])
            df.columns = ["Agent", "调用次数", "输入Token", "输出Token", "成本"]
            st.dataframe(df, use_container_width=True)

        # 按时间分布（每天）
        st.subheader("📈 每日趋势")
        daily_rows = conn.execute(
            "SELECT date(timestamp, 'unixepoch', 'localtime') as day, "
            "COUNT(*) as cnt, SUM(cost) as cost "
            "FROM token_usage WHERE timestamp >= ? GROUP BY day ORDER BY day", (since,)
        ).fetchall()

        if daily_rows:
            import pandas as pd
            df = pd.DataFrame([dict(r) for r in daily_rows])
            df.columns = ["日期", "调用次数", "成本"]
            st.line_chart(df.set_index("日期"))

    except Exception as e:
        st.error(f"数据库查询失败: {e}")
    finally:
        conn.close()

    # 回退到 tracker
    if chancellor:
        _show_tracker_stats(chancellor)


def _show_tracker_stats(chancellor):
    """从 tracker 对象展示统计"""
    st.subheader("📊 Tracker 实时统计")
    model_stats = chancellor.tracker.get_model_stats()
    if model_stats:
        for model, stats in model_stats.items():
            st.text(f"{model}: {stats['calls']}次 输入={stats['input']} 输出={stats['output']}")
    else:
        st.info("暂无使用数据")


# ══════════════════════════════════════════════
#  🧠 记忆系统
# ══════════════════════════════════════════════
def page_memory_system():
    st.title("🧠 记忆系统监控")

    chancellor = get_chancellor()

    # 记忆文件统计
    mem_files = glob.glob(os.path.join(MEMORY_DIR, "*.json"))
    col1, col2, col3 = st.columns(3)
    col1.metric("Agent 记忆文件", len(mem_files))

    total_long_term = 0
    total_short_term = 0

    # 记忆详情
    st.subheader("📦 Agent 记忆分布")
    for mf in mem_files:
        agent_id = os.path.basename(mf).replace(".json", "")
        data = _safe_json_load(mf, {})
        lt = data.get("long_term", [])
        total_long_term += len(lt)

        # 重要性分布
        importance_dist = Counter()
        for entry in lt:
            imp = entry.get("importance", 0)
            if imp >= 0.8:
                importance_dist["高(≥0.8)"] += 1
            elif imp >= 0.6:
                importance_dist["中(0.6-0.8)"] += 1
            else:
                importance_dist["低(<0.6)"] += 1

        with st.expander(f"🧠 {agent_id} — 长期记忆 {len(lt)} 条"):
            if lt:
                # 最近 5 条
                st.markdown("**最近记忆:**")
                for entry in lt[-5:]:
                    imp = entry.get("importance", 0)
                    imp_icon = "🔴" if imp >= 0.8 else "🟡" if imp >= 0.6 else "🟢"
                    ts = datetime.fromtimestamp(entry.get("time", 0)).strftime("%m-%d %H:%M")
                    st.caption(f"{imp_icon} [{ts}] {entry.get('text', '')[:120]}")

                # 重要性分布
                if importance_dist:
                    st.markdown("**重要性分布:**")
                    for level, count in importance_dist.items():
                        st.text(f"  {level}: {count}")

                # 标签统计
                all_tags = []
                for entry in lt:
                    all_tags.extend(entry.get("tags", []))
                if all_tags:
                    tag_counts = Counter(all_tags)
                    st.markdown(f"**热门标签:** {', '.join(f'{t}({c})' for t, c in tag_counts.most_common(10))}")
            else:
                st.info("无长期记忆")

    col2.metric("总长期记忆", total_long_term)

    # 因果图（从记忆条目推断）
    st.subheader("🔗 因果关系图")
    all_entries = []
    for mf in mem_files:
        data = _safe_json_load(mf, {})
        for entry in data.get("long_term", []):
            if entry.get("task_id"):
                all_entries.append(entry)

    if all_entries:
        # 按 task_id 分组展示因果链
        task_groups = defaultdict(list)
        for entry in all_entries:
            task_groups[entry["task_id"]].append(entry)

        st.caption(f"共 {len(task_groups)} 个任务因果链")
        for tid, entries in list(task_groups.items())[:10]:
            with st.expander(f"🔗 Task {tid} ({len(entries)} 记忆)"):
                for e in sorted(entries, key=lambda x: x.get("time", 0)):
                    ts = datetime.fromtimestamp(e.get("time", 0)).strftime("%H:%M:%S")
                    st.text(f"[{ts}] {e.get('text', '')[:150]}")
    else:
        st.info("暂无因果关系数据")

    # 蒸馏知识
    st.subheader("⚗️ 蒸馏知识")
    if chancellor:
        try:
            # 从进化系统获取经验
            evo = chancellor.evolution
            if hasattr(evo, "evolved_prompts") and evo.evolved_prompts:
                for agent_id, prompt in evo.evolved_prompts.items():
                    with st.expander(f"⚗️ {agent_id} 蒸馏 Prompt"):
                        st.code(prompt[:500])
            else:
                st.info("暂无蒸馏知识")
        except Exception:
            st.info("蒸馏知识不可用")
    else:
        evo_prompts = _safe_json_load(os.path.join(EVOLUTION_DIR, "evolved_prompts.json"), {})
        if evo_prompts:
            for agent_id, prompt in evo_prompts.items():
                with st.expander(f"⚗️ {agent_id}"):
                    st.code(str(prompt)[:500])
        else:
            st.info("暂无蒸馏知识")


# ══════════════════════════════════════════════
#  🔒 安全审计
# ══════════════════════════════════════════════
def page_security_audit():
    st.title("🔒 安全审计面板")

    chancellor = get_chancellor()

    # 安全系统状态
    if chancellor:
        sec_status = chancellor.security.get_status()
        col1, col2, col3 = st.columns(3)
        col1.metric("敏感词违规", sec_status.get("total_violations", 0))
        col2.metric("零信任状态", "已启用" if hasattr(chancellor, "zero_trust") else "未启用")
        col3.metric("RBAC 状态", "已启用" if hasattr(chancellor, "rbac") else "未启用")
    else:
        st.info("丞相离线，安全模块不可用")

    # 审计日志
    st.subheader("📜 审计日志")
    audit_lines = _read_log_lines("security", 100)
    if audit_lines:
        # 搜索过滤
        search = st.text_input("🔍 搜索审计日志")
        level_filter = st.selectbox("日志级别", ["全部", "WARNING", "ERROR", "CRITICAL"], key="audit_level")

        filtered = audit_lines
        if search:
            filtered = [l for l in filtered if search.lower() in l.lower()]
        if level_filter != "全部":
            filtered = [l for l in filtered if level_filter in l]

        for line in filtered[-50:]:
            if "ERROR" in line or "CRITICAL" in line:
                st.error(line.rstrip())
            elif "WARNING" in line:
                st.warning(line.rstrip())
            else:
                st.text(line.rstrip())
    else:
        st.info("无安全审计日志")

    # 零信任事件
    st.subheader("🛡️ 零信任事件")
    zt_lines = _read_log_lines("rbac", 50)
    if zt_lines:
        for line in zt_lines[-20:]:
            st.markdown(f'<div class="audit-entry">{line.rstrip()}</div>', unsafe_allow_html=True)
    else:
        st.info("无零信任事件记录")

    # RBAC 状态
    st.subheader("🔑 RBAC 角色分布")
    if chancellor and hasattr(chancellor, "rbac"):
        try:
            # 尝试获取 RBAC 信息
            agents = chancellor.get_status()["agents"]
            role_dist = Counter()
            for aid, info in agents.items():
                role_dist[info.get("role", "unknown")] += 1

            if role_dist:
                import pandas as pd
                df = pd.DataFrame(list(role_dist.items()), columns=["角色", "数量"])
                st.bar_chart(df.set_index("角色"))
        except Exception:
            st.info("RBAC 信息不可用")
    else:
        st.info("RBAC 模块未加载")

    # 敏感词违规详情
    st.subheader("⚠️ 敏感词违规记录")
    if chancellor and chancellor.security.violations:
        for v in chancellor.security.violations[-20:]:
            st.warning(f"触发词: {v.get('triggers', [])} | 内容: {v.get('text', '')[:100]}")
    else:
        st.success("✅ 无敏感词违规记录")


# ══════════════════════════════════════════════
#  🧬 进化状态
# ══════════════════════════════════════════════
def page_evolution():
    st.title("🧬 进化状态")

    chancellor = get_chancellor()
    if not chancellor:
        st.error("丞相离线")
        _show_static_evolution()
        return

    evo = chancellor.evolution

    # 概览
    evo_status = evo.get_all_status()
    col1, col2, col3 = st.columns(3)
    col1.metric("评估总数", evo_status["total_evaluations"])
    col2.metric("跟踪节点", evo_status["agents_tracked"])
    col3.metric("进化 Prompt", evo_status["evolved_prompts"])

    # 等级分布
    st.subheader("🏅 等级分布")
    ranks = evo_status.get("ranks", {})
    if ranks:
        rank_count = Counter(ranks.values())
        import pandas as pd
        df = pd.DataFrame(list(rank_count.items()), columns=["等级", "人数"])
        st.bar_chart(df.set_index("等级"))

        # 等级详情
        rank_order = ["皇帝", "亲王", "郡王", "国公", "郡公", "侯", "伯", "子", "男", "郡守", "县令", "亭长"]
        for rank in rank_order:
            agents_in_rank = [aid for aid, r in ranks.items() if r == rank]
            if agents_in_rank:
                st.markdown(f"**{rank}** ({len(agents_in_rank)}): {', '.join(agents_in_rank)}")
    else:
        st.info("暂无等级数据")

    # Agent 进化评分排行
    st.subheader("📊 Agent 进化评分")
    evo_data = []
    for aid in chancellor.agents:
        evo_info = evo.get_agent_evolution_status(aid)
        if evo_info.get("evaluations", 0) > 0:
            name = chancellor.agents[aid].state.name
            evo_data.append({
                "Agent": name,
                "ID": aid,
                "质量": evo_info.get("avg_quality", 0),
                "速度": evo_info.get("avg_speed", 0),
                "等级": evo_info.get("rank", "N/A"),
                "评估次数": evo_info.get("evaluations", 0),
            })

    if evo_data:
        import pandas as pd
        df = pd.DataFrame(evo_data)
        st.dataframe(df, use_container_width=True)

        # 进化进度条
        for item in evo_data:
            with st.expander(f"🧬 {item['Agent']} — {item['等级']}"):
                c1, c2, c3 = st.columns(3)
                c1.progress(item["质量"], text=f"质量 {item['质量']:.2f}")
                c2.progress(item["速度"], text=f"速度 {item['速度']:.2f}")
                c3.metric("评估次数", item["评估次数"])

    # 晋降级历史（从日志提取）
    st.subheader("📜 晋降级历史")
    evo_lines = _read_log_lines("evolution", 100)
    rank_changes = [l for l in evo_lines if "晋升" in l or "降级" in l or "promote" in l.lower() or "demote" in l.lower()]
    if rank_changes:
        for line in rank_changes[-20:]:
            if "晋升" in line or "promote" in line.lower():
                st.success(line.rstrip())
            else:
                st.warning(line.rstrip())
    else:
        st.info("暂无晋降级记录")

    # 闭环优化
    st.subheader("🔄 瓶颈分析")
    if hasattr(evo, "optimizer") and evo.optimizer:
        bottlenecks = evo.optimizer.bottlenecks
        if bottlenecks:
            for b in bottlenecks:
                severity = b.get("severity", 0)
                icon = "🔴" if severity > 0.7 else "🟡" if severity > 0.4 else "🟢"
                st.warning(f"{icon} **{b['type']}** — Agent `{b['agent_id']}`: {b['recommendation']}")
        else:
            st.success("✅ 未检测到瓶颈")
    else:
        st.info("瓶颈分析不可用")


def _show_static_evolution():
    """离线进化数据"""
    evals = _safe_json_load(os.path.join(EVOLUTION_DIR, "evaluations.json"), [])
    ranks = _safe_json_load(os.path.join(EVOLUTION_DIR, "ranks.json"), {})
    prompts = _safe_json_load(os.path.join(EVOLUTION_DIR, "evolved_prompts.json"), {})

    col1, col2, col3 = st.columns(3)
    col1.metric("评估记录", len(evals))
    col2.metric("等级记录", len(ranks))
    col3.metric("蒸馏 Prompt", len(prompts))

    if ranks:
        st.subheader("🏅 等级分布")
        rank_count = Counter(ranks.values())
        st.bar_chart(dict(rank_count))


# ══════════════════════════════════════════════
#  📸 检查点管理
# ══════════════════════════════════════════════
def page_checkpoints():
    st.title("📸 检查点管理")

    os.makedirs(CHECKPOINT_DIR, exist_ok=True)

    # 检查点列表
    checkpoint_files = sorted(glob.glob(os.path.join(CHECKPOINT_DIR, "*.json")), key=os.path.getmtime, reverse=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("检查点数量", len(checkpoint_files))
    total_size = sum(os.path.getsize(f) for f in checkpoint_files)
    col2.metric("总大小", f"{total_size / 1024:.1f} KB")
    if checkpoint_files:
        col3.metric("最新", datetime.fromtimestamp(os.path.getmtime(checkpoint_files[0])).strftime("%m-%d %H:%M"))

    st.markdown("---")

    # 筛选
    filter_text = st.text_input("🔍 按名称筛选检查点")

    for ckpt_path in checkpoint_files:
        name = os.path.basename(ckpt_path).replace(".json", "")
        if filter_text and filter_text.lower() not in name.lower():
            continue

        mtime = datetime.fromtimestamp(os.path.getmtime(ckpt_path)).strftime("%Y-%m-%d %H:%M:%S")
        size_kb = os.path.getsize(ckpt_path) / 1024

        with st.expander(f"📸 {name} ({size_kb:.1f} KB) — {mtime}"):
            data = _safe_json_load(ckpt_path, {})

            # 元数据
            if "metadata" in data:
                meta = data["metadata"]
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("任务", meta.get("task_id", "N/A"))
                mc2.metric("Agent", meta.get("agent_id", "N/A"))
                mc3.metric("版本", meta.get("version", "N/A"))

            # 内容预览
            st.json(data, expanded=False)

            # 操作按钮
            bc1, bc2 = st.columns(2)
            with bc1:
                if st.button(f"📥 恢复", key=f"restore_{name}"):
                    st.info(f"恢复检查点 {name} — 功能需要丞相在线")
            with bc2:
                if st.button(f"🗑️ 删除", key=f"delete_{name}"):
                    try:
                        os.remove(ckpt_path)
                        st.success(f"✅ 已删除 {name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"删除失败: {e}")

    if not checkpoint_files:
        st.info("暂无检查点。任务执行时自动创建。")

    # 手动创建检查点
    st.markdown("---")
    st.subheader("➕ 手动创建检查点")
    ckpt_name = st.text_input("检查点名称", value=f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    ckpt_note = st.text_input("备注")
    if st.button("创建检查点"):
        ckpt_data = {
            "metadata": {
                "name": ckpt_name,
                "note": ckpt_note,
                "created_at": time.time(),
                "type": "manual",
            },
            "state": {
                "chancellor_status": "snapshot",
                "timestamp": datetime.now().isoformat(),
            },
        }
        ckpt_path = os.path.join(CHECKPOINT_DIR, f"{ckpt_name}.json")
        with open(ckpt_path, "w", encoding="utf-8") as f:
            json.dump(ckpt_data, f, ensure_ascii=False, indent=2)
        st.success(f"✅ 检查点 {ckpt_name} 已创建")
        st.rerun()

    # 清理
    st.markdown("---")
    st.subheader("🧹 清理检查点")
    max_age_days = st.slider("保留天数", 1, 90, 30)
    if st.button("清理过期检查点"):
        cutoff = time.time() - max_age_days * 86400
        removed = 0
        for ckpt_path in checkpoint_files:
            if os.path.getmtime(ckpt_path) < cutoff:
                os.remove(ckpt_path)
                removed += 1
        if removed:
            st.success(f"✅ 清理了 {removed} 个过期检查点")
            st.rerun()
        else:
            st.info("无需清理")


# ══════════════════════════════════════════════
#  🌐 模型路由
# ══════════════════════════════════════════════
def page_model_router():
    st.title("🌐 多模型路由")

    try:
        from core.model_router import get_available_models
        models = get_available_models()
    except Exception:
        models = {}

    if models:
        for alias, cfg in models.items():
            with st.expander(f"🤖 {alias} — {cfg.get('name', '?')}"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Provider", cfg.get("provider", "?"))
                c2.metric("Max Tokens", cfg.get("max_tokens", "?"))
                c3.metric("Cost/1k", f"${cfg.get('cost_per_1k_input', 0):.4f}")
    else:
        st.info("模型配置不可用")

    # 模型使用统计
    st.subheader("📊 模型使用统计")
    chancellor = get_chancellor()
    if chancellor:
        model_stats = chancellor.tracker.get_model_stats()
        if model_stats:
            for model, stats in model_stats.items():
                st.text(f"{model}: {stats['calls']}次 输入={stats['input']} 输出={stats['output']}")
        else:
            st.info("暂无使用数据")
    else:
        st.info("丞相离线")


# ══════════════════════════════════════════════
#  🔌 插件系统
# ══════════════════════════════════════════════
def page_plugins():
    st.title("🔌 插件系统")

    chancellor = get_chancellor()
    if not chancellor:
        st.error("丞相离线")
        return

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


# ══════════════════════════════════════════════
#  💬 任务执行
# ══════════════════════════════════════════════
def page_task_execution():
    st.title("💬 任务执行")

    chancellor = get_chancellor()
    if not chancellor:
        st.error("丞相离线，无法执行任务")
        return

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


# ══════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════
def main():
    page = sidebar()

    page_map = {
        "📊 总览": page_overview,
        "⚡ 实时任务": page_realtime_tasks,
        "👥 Agent 面板": page_agent_panel,
        "💬 消息总线": page_message_bus,
        "💰 Token 统计": page_token_stats,
        "🧠 记忆系统": page_memory_system,
        "🔒 安全审计": page_security_audit,
        "🧬 进化状态": page_evolution,
        "📸 检查点管理": page_checkpoints,
        "🌐 模型路由": page_model_router,
        "🔌 插件系统": page_plugins,
        "💬 任务执行": page_task_execution,
    }

    handler = page_map.get(page, page_overview)
    handler()


if __name__ == "__main__":
    main()
