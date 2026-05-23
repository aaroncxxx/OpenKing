# 帝国架构 lite-v3

> 三维记忆 × 因果推理 × 跨Agent知识共享

## 简介

帝国架构 lite-v3 是一个多 Agent 协作框架，核心特色是**三维记忆系统**（Forms-Functions-Dynamics），在 v3.2 中进一步扩展了因果推理、知识共享、记忆蒸馏和主动检索能力。

## 架构概览

```
core/
├── memory3d.py        # 三维记忆系统（v3.2 核心）
├── memory.py          # 传统记忆模块
├── bus.py             # Agent 通信总线
├── taskqueue.py       # 任务队列
├── dag_shapley.py     # DAG + Shapley 值协作
├── security.py        # 安全模块
├── rbac.py            # 角色权限控制
├── protocols.py       # 通信协议
├── model_router.py    # 模型路由
├── multimodal.py      # 多模态处理
├── self_evolution.py  # 自我进化
├── plugins.py         # 插件系统
├── debug_tools.py     # 调试与监控工具（v3.2 DX）
└── ...

agents/                # Agent 实现
data/                  # 持久化数据
dashboard/
└── app.py             # Web 管理界面（v3.2 DX, Streamlit）
knowledge/             # 知识库
```

## 三维记忆系统 (memory3d.py)

### 核心概念

| 维度 | 层级 | 说明 |
|------|------|------|
| **形式层** | Token → Parameter → Latent | 从原始文本到向量表示 |
| **功能层** | Episodic / Semantic / Procedural | 情景 / 语义 / 程序记忆 |
| **动态层** | 形成 → 巩固 → 检索 → 遗忘 → 更新 | 记忆生命周期 |

### v3.2 新增模块

#### 1. 因果记忆图谱 (CausalMemoryGraph)

构建因果关系网络，支持正向推理和反向追溯。

```python
from core.memory3d import CausalMemoryGraph

cg = CausalMemoryGraph()

# 添加因果关系
cg.add_cause_effect("下雨", "地面湿", confidence=0.9)
cg.add_cause_effect("下雨", "交通拥堵", confidence=0.6)
cg.add_cause_effect("地面湿", "行人滑倒", confidence=0.4)

# 正向推理：原因 → 结果
cg.infer_effects("下雨")
# → [("地面湿", 0.9), ("交通拥堵", 0.6)]

# 反向追溯：结果 → 原因
cg.infer_causes("行人滑倒")
# → [("地面湿", 0.4)]

# 因果链可视化
print(cg.visualize_chain("下雨"))
# 🌳 因果链 (forward): 下雨
# ├── 地面湿 [90%]
# │   └── 行人滑倒 [36%]
# └── 交通拥堵 [60%]
```

#### 2. 帝国图书馆 (ImperialLibrary)

跨 Agent 知识共享中心，支持版本控制和访问控制。

```python
from core.memory3d import ImperialLibrary

lib = ImperialLibrary()

# 发布知识
entry = lib.publish_knowledge(
    agent_id="agent_alpha",
    content="Python GIL 限制了多线程性能",
    tags=["python", "performance"],
    category="technical",
)

# 搜索知识
results = lib.search_knowledge("Python 性能", top_k=5)

# 访问控制
lib.grant_access("agent_beta", entry.knowledge_id)
lib.revoke_access("agent_beta", entry.knowledge_id)

# 版本控制
lib.update_knowledge(entry.knowledge_id, "agent_alpha",
                     new_content="Python GIL 在 3.12+ 中有所改善")
lib.rollback_knowledge(entry.knowledge_id, target_version=1)

# 查看版本历史
history = lib.get_version_history(entry.knowledge_id)
```

**分类体系**：`general` / `technical` / `strategy` / `protocol` / `experience` / `pattern` / `warning` / `best_practice`

#### 3. 记忆蒸馏器 (MemoryDistiller)

从大量历史记忆中自动提取通用规律和模式。

```python
from core.memory3d import Memory3D, MemoryDistiller

memory = Memory3D("my_agent")
# ... 大量历史记忆 ...

distiller = MemoryDistiller(memory)

# 手动蒸馏
new_patterns = distiller.distill(min_evidence=3, min_confidence=0.3)

# 查看蒸馏结果
for d in distiller.get_distillates(category="frequency"):
    print(f"{d.pattern} [置信度: {d.confidence:.0%}, 证据: {d.evidence_count}]")

# 获取摘要（可注入 prompt）
summary = distiller.get_distillate_summary()

# 定期自动蒸馏
distiller.auto_distill_if_needed()
```

**蒸馏类型**：
- **频率模式** (frequency)：反复出现的主题/关键词
- **共现模式** (co_occurrence)：经常一起出现的概念对
- **标签聚类** (tag_cluster)：标签共现分析

#### 4. 主动记忆检索器 (ProactiveRetriever)

上下文变化时主动推送相关记忆，无需显式查询。

```python
from core.memory3d import Memory3D, ProactiveRetriever

memory = Memory3D("my_agent")
retriever = ProactiveRetriever(memory)

# 注册触发规则
retriever.register_trigger(
    keywords=["部署", "deploy", "上线"],
    callback=lambda memories: print(f"发现 {len(memories)} 条相关记忆"),
    description="部署相关上下文",
    priority=10,
    cooldown=300,  # 5分钟冷却
)

# 当上下文变化时自动触发
memories = retriever.on_context_change("准备部署新版本到生产环境")

# 增强版检索（标准 + 触发规则）
results = retriever.retrieve_proactive("数据库优化", top_k=5)

# 静默扫描（不触发检索）
matched_rules = retriever.keyword_scan("今晚部署上线")
```

## 完整使用示例

```python
from core.memory3d import (
    Memory3D, MemoryFunction,
    CausalMemoryGraph, ImperialLibrary,
    MemoryDistiller, ProactiveRetriever,
)

# 1. 初始化记忆系统
memory = Memory3D("captain")

# 2. 形成记忆
memory.form("今天的战斗任务很顺利", function=MemoryFunction.EPISODIC,
            importance=0.7, tags=["battle", "success"])
memory.form("敌方舰队偏好侧翼包抄", function=MemoryFunction.SEMANTIC,
            importance=0.9, tags=["enemy", "tactics"])

# 3. 因果推理
causal = CausalMemoryGraph()
causal.add_cause_effect("侧翼包抄", "防线被突破", 0.8)
causal.add_cause_effect("预备队不足", "防线被突破", 0.6)

# 4. 知识共享
library = ImperialLibrary()
library.publish_knowledge("captain", "敌方偏好侧翼包抄",
                          tags=["enemy", "tactics"], category="strategy")

# 5. 记忆蒸馏
distiller = MemoryDistiller(memory)
distiller.distill()

# 6. 主动检索
retriever = ProactiveRetriever(memory)
retriever.register_trigger(["敌方", "enemy", "战术"],
                           description="战术决策相关")

# 7. 生命周期管理
memory.lifecycle_tick()  # 巩固 + 遗忘
distiller.auto_distill_if_needed()  # 定期蒸馏
```

## 持久化

所有模块自动持久化到 `data/` 目录：

```
data/
├── memory3d/          # 记忆数据 (per agent)
├── causal/            # 因果图谱
├── library/           # 帝国图书馆
├── distill/           # 蒸馏结果 (per agent)
└── proactive/         # 触发规则 (per agent)
```

## 运行测试

```bash
cd lite-v3
python3 -m pytest tests/ -v
# 或
python3 -m unittest tests.test_memory3d_v32 -v
```

## CLI 命令

```bash
python3 main.py              # 交互模式
python3 main.py "指令"        # 单次执行
python3 main.py --auto "指令" # 自治模式
python3 main.py --status     # 帝国状态
python3 main.py --causal     # 因果图谱
python3 main.py --library    # 帝国图书馆
```

交互模式中可用的 v3.2 命令：
- `causal` — 查看因果图谱状态
- `causal add <因> <果> [置信度]` — 添加因果关系
- `causal infer <节点> [forward|backward]` — 因果推理
- `library` — 查看图书馆状态
- `library search <关键词>` — 搜索共享知识
- `library publish <内容> [--tags a,b] [--cat 分类]` — 发布知识
- `distill [agent_id]` — 执行记忆蒸馏
- `proactive` — 查看主动检索器状态

## 版本历史

| 版本 | 说明 |
|------|------|
| v3.0 | 三维记忆框架基础（形式/功能/动态） |
| v3.1 | 记忆巩固、衰退、共享记忆空间 |
| v3.2 | 因果推理、帝国图书馆、记忆蒸馏、主动检索 |
| **v3.2 DX** | **开发者体验全面提升：Web 管理界面 + 调试监控工具链** |

### v3.2 DX — 开发者体验提升

#### 完整 Web 管理界面 (`dashboard/app.py`)

Streamlit 大屏全面升级，12 个功能模块：

| 模块 | 功能 |
|------|------|
| 📊 总览 | 核心指标、节点状态分布、Top Agent 排行 |
| ⚡ 实时任务 | 执行中任务进度条、耗时追踪、完成/失败列表 |
| 👥 Agent 面板 | 状态筛选排序、评分等级、记忆统计、进化指标 |
| 💬 消息总线 | 实时消息流可视化、类型筛选、Agent 通信矩阵 |
| 💰 Token 统计 | SQLite 按模型/Agent/时间统计、成本图表、每日趋势 |
| 🧠 记忆系统 | 各 Agent 记忆量、重要性分布、因果图、蒸馏知识 |
| 🔒 安全审计 | 审计日志搜索、敏感词违规、零信任事件、RBAC 状态 |
| 🧬 进化状态 | 等级分布、评分排行、晋降级历史、瓶颈分析 |
| 📸 检查点管理 | 查看/恢复/删除/创建检查点、过期清理 |
| 🌐 模型路由 | 模型配置与使用统计 |
| 🔌 插件系统 | 插件发现与安装 |
| 💬 任务执行 | 指令下达与结果展示 |

```bash
streamlit run dashboard/app.py
```

#### 调试与监控工具 (`core/debug_tools.py`)

三大调试类，支持 CLI 直接调用：

```python
from core.debug_tools import TaskDebugger, LogAnalyzer, SystemMonitor

# 任务调试
td = TaskDebugger()
td.trace_task("task_id")                    # 全链路追踪
td.get_performance_breakdown("task_id")     # 性能分解
td.replay_task("task_id", dry_run=True)     # 重放执行
td.compare_runs("task_1", "task_2")         # 对比两次执行

# 日志分析
la = LogAnalyzer()
la.search_logs("error", level="ERROR")      # 日志搜索
la.get_error_summary(hours=24)              # 错误摘要
la.get_agent_activity("agent_id")           # Agent 活动报告

# 系统监控
sm = SystemMonitor()
sm.get_system_health()                      # 健康检查
sm.get_resource_usage()                     # 资源使用
sm.export_debug_report()                    # 导出调试报告
```

CLI 快捷命令：

```bash
python -m core.debug_tools health           # 系统健康检查
python -m core.debug_tools errors 24        # 错误摘要
python -m core.debug_tools search "keyword" # 日志搜索
python -m core.debug_tools agent <id>       # Agent 活动
python -m core.debug_tools export           # 导出报告
python -m core.debug_tools resources        # 资源使用
```

### v3.2 集成架构

```
Chancellor (v3.2)
├── causal_graph: CausalMemoryGraph     # 全局因果图谱，所有 Agent 共享
├── library: ImperialLibrary             # 全局知识库，所有 Agent 共享
└── agents/
    └── Agent (v3.2)
        ├── memory3d: Memory3D           # 三维记忆（替代 AgentMemory）
        ├── distiller: MemoryDistiller   # 每 Agent 独立蒸馏器
        ├── retriever: ProactiveRetriever # 每 Agent 独立主动检索
        ├── causal: CausalMemoryGraph    # 引用全局因果图谱
        └── library: ImperialLibrary     # 引用全局图书馆
```

**数据流**：
- Agent `call_llm()` 时自动注入：三维记忆 + 主动检索结果 + 因果推理 + 图书馆知识
- 任务完成后自动从结果中提取因果关系
- `lifecycle_tick()` 定期巩固记忆 + 自动蒸馏
- `Agent` 使用 `_Memory3DCompat` 兼容层，旧代码无需修改

## v3.2 API 速查

| 类 | 方法 | 说明 |
|----|------|------|
| `CausalMemoryGraph` | `add_cause_effect(cause, effect, conf)` | 添加因果关系 |
| | `infer_effects(cause)` | 正向推理 |
| | `infer_causes(effect)` | 反向追溯 |
| | `visualize_chain(start)` | 文本可视化 |
| `ImperialLibrary` | `publish_knowledge(agent, content, tags)` | 发布知识 |
| | `search_knowledge(query, top_k)` | 搜索知识 |
| | `grant_access / revoke_access` | 访问控制 |
| | `update_knowledge / rollback_knowledge` | 版本管理 |
| `MemoryDistiller` | `distill()` | 蒸馏记忆 |
| | `get_distillate_summary()` | 获取摘要 |
| | `auto_distill_if_needed()` | 自动蒸馏 |
| `ProactiveRetriever` | `register_trigger(keywords, cb)` | 注册触发 |
| | `on_context_change(context)` | 上下文触发 |
| | `retrieve_proactive(query)` | 增强检索 |
