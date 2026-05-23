# 帝国架构 (Empire Architecture)

> 多 Agent 协作框架 · 三维记忆 × 因果推理 × 自我进化

## 概述

帝国架构是一个企业级多 Agent 协作框架，以"丞相-百官"编排模式运行。核心特色包括三维记忆系统、因果推理图谱、Agent 自我进化、零信任安全体系。

**当前版本：v3.2 DX（开发者体验提升）**

## 核心能力

- **多 Agent 协作**：丞相编排 + 256 节点并行，DAG + Shapley 值贡献分配
- **三维记忆**：形式/功能/动态三层记忆架构，支持因果推理与知识蒸馏
- **自我进化**：Agent 自动评估、Prompt 优化、等级晋升降级
- **多模型路由**：MIMO / DeepSeek / GPT 等多模型智能路由
- **企业安全**：零信任引擎、RBAC 角色权限、敏感词检测、审计日志
- **插件系统**：支持 ClawHub 插件安装与管理

## 快速开始

```bash
# 交互模式
python3 main.py

# 单次执行
python3 main.py "写一篇关于AI的报告"

# 自治模式（多轮迭代）
python3 main.py --auto "分析市场趋势"

# Web 管理界面
streamlit run dashboard/app.py

# 系统健康检查
python -m core.debug_tools health
```

## 项目结构

```
lite-v3/
├── main.py              # CLI 入口
├── chancellor.py        # 丞相（核心编排器）
├── config.json          # 系统配置
├── core/
│   ├── memory3d.py      # 三维记忆系统
│   ├── memory.py        # 传统记忆
│   ├── bus.py           # 消息总线
│   ├── taskqueue.py     # 任务队列
│   ├── security.py      # 安全系统 + 零信任
│   ├── rbac.py          # RBAC 权限
│   ├── self_evolution.py # 自我进化
│   ├── evolution_plus.py # 闭环优化
│   ├── model_router.py  # 多模型路由
│   ├── debug_tools.py   # 调试与监控
│   └── ...
├── dashboard/
│   └── app.py           # Streamlit 管理界面
├── agents/              # Agent 实现
├── data/                # 持久化数据
├── knowledge/           # 知识库
└── tests/               # 测试
```

## v3.2 DX 功能

### Web 管理界面 (dashboard/app.py)

12 个功能模块：总览、实时任务、Agent 面板、消息总线可视化、Token 统计、记忆监控、安全审计、进化状态、检查点管理、模型路由、插件系统、任务执行。

### 调试工具 (core/debug_tools.py)

- **TaskDebugger**：任务追踪、性能分解、重放、对比
- **LogAnalyzer**：日志搜索、错误摘要、Agent 活动报告
- **SystemMonitor**：健康检查、资源监控、调试报告导出

## 三维记忆系统

| 维度 | 层级 | 说明 |
|------|------|------|
| 形式层 | Token → Parameter → Latent | 原始文本到向量 |
| 功能层 | Episodic / Semantic / Procedural | 情景/语义/程序记忆 |
| 动态层 | 形成→巩固→检索→遗忘→更新 | 记忆生命周期 |

## CLI 命令

```bash
python3 main.py              # 交互模式
python3 main.py "指令"        # 单次执行
python3 main.py --auto "指令" # 自治模式
python3 main.py --status     # 帝国状态
python3 main.py --causal     # 因果图谱
python3 main.py --library    # 帝国图书馆
```

## 调试 CLI

```bash
python -m core.debug_tools health           # 健康检查
python -m core.debug_tools errors [hours]   # 错误摘要
python -m core.debug_tools search <query>   # 日志搜索
python -m core.debug_tools agent <id>       # Agent 活动
python -m core.debug_tools export           # 导出报告
python -m core.debug_tools resources        # 资源使用
```
