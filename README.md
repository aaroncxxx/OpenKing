# 🏛️ Empire Architecture v3.2.0

> 基于中国古代三公九卿制的 AI 多智能体协作系统
> AI Multi-Agent Collaboration System Inspired by Ancient Chinese Governance

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)
![Version](https://img.shields.io/badge/Version-3.2.0-orange)
![Agents](https://img.shields.io/badge/Agents-256+-purple)

## ✨ 这是什么？

一个 **256 节点 AI 多智能体协作系统**，用古代三公九卿制组织架构，让 AI Agent 像帝国官员一样各司其职、协同完成复杂任务。

**核心能力：**
- 🧠 **自进化** — Agent 自我评估、技能进化、晋升降级
- 🌐 **多模型** — MIMO / DeepSeek / Claude / GPT-4 / Ollama 自动路由
- 🧠 **三维记忆** — 情景/语义/程序记忆，自适应衰退
- 🤖 **自治** — 多轮迭代、异常自愈、自动 Prompt 优化
- 🎨 **可视化大屏** — Streamlit Dashboard 实时监控
- 🔌 **协议标准化** — MCP + A2A，对接 LangChain/AutoGen

## 🚀 实战案例：全国未来24小时降雨量查询

```bash
cd lite-v3/
python3 main.py "任务一：全国未来24小时降雨量查询，覆盖全国主要城市"
```

**执行结果：**

| 指标 | 结果 |
|------|------|
| 耗时 | 130.2s |
| Token 消耗 | 12,095 |
| 调度节点 | 5 个（谋略参谋、技术参谋、情报参谋、翰林写手、探事检索） |
| 锦衣卫审计 | ✅ 通过 |
| 模型路由 | 参谋→MIMO Pro，执行→DeepSeek（自动 fallback） |

**丞相汇总（自动生成）：**

> **态势：南湿北晴**
>
> | 区域 | 城市 | 降雨概率 | 雨量 |
> |------|------|---------|------|
> | 已降雨 | 南昌 82%、武汉 72%、上海 64% | 高 | 1-2.5mm |
> | 极高概率 | 杭州 76%、成都 70%、长沙 64% | 极高 | 随时转雨 |
> | 晴好区 | 北京、天津、济南、青岛 | 无 | 利于行动 |
>
> **行动建议：** 优先将敏感活动安排至华北晴好区；对长江中下游及西南高概率区启动应急预案。

**v3.0 新功能运行情况：**
- ✅ 多模型路由：参谋→MIMO，执行→DeepSeek（401 自动 fallback 到 MIMO）
- ✅ 自进化评估：5 个 Agent 均已评分（质量/速度/协作）
- ✅ 256 节点全部就绪
- ⚠️ 知识层：待挂载（可选）

## 📦 快速开始

```bash
# 克隆
git clone https://github.com/aaroncxxx/empire-architecture.git
cd empire-architecture/lite-v3/

# 设置 API Key
export MIMO_API_KEY=your_key

# 运行
python3 main.py              # 交互模式
python3 main.py "你的指令"    # 单次执行
python3 main.py --auto "指令" # 自治模式（多轮迭代）
python3 main.py --status     # 帝国状态
python3 main.py --evolution  # 进化状态
python3 main.py --models     # 可用模型

# 可视化大屏
pip install streamlit
streamlit run dashboard/app.py
```

## 🏛️ 帝国编制

```
皇帝: AARONCXXX         丞相: MIMO
──────────────────────────────────────
三公:       3  │ 九卿:        9  │ 六部:     6
参谋团:    16  │ 执行官:     24  │ 翰林院:  12
特殊机构:   20  │ 监察御史:   12  │ 扩展:    24
州牧:      32  │ 内廷侍从:   16  │ 武将营:  24
郡守:      32  │ 都督区:     16  │ 钦差:    14
锦衣卫:     1
──────────────────────────────────────
总计: 256 节点
```

## 🧠 v3.1 六大方向

| 方向 | 模块 | 功能 |
|------|------|------|
| 🧠 思维向量通信 | `core/thought_vector.py` | MiMo Embedding + 向量压缩 + 语义检索 |
| 📊 DAG-Shapley | `core/dag_shapley.py` | Shapley 值贡献测量 + 动态资源分配 |
| 🧠 三维记忆 | `core/memory3d.py` | 情景/语义/程序 × 形成/巩固/检索/遗忘 |
| 🎨 多模态 | `core/multimodal.py` | 图像分析 + 音频转录 + 跨模态对齐 |
| 🔌 协议标准化 | `core/protocols.py` | MCP + A2A + OpenAPI |
| 🐳 部署 | `Dockerfile` + `k8s/` | Docker + K8s + 轻量边缘版 |

## 📁 文件结构

```
lite-v3/
├── main.py               # CLI 入口
├── chancellor.py          # 丞相协调器
├── config.json            # 多模型配置
├── agents/base.py         # Agent 基类（优雅降级）
├── core/
│   ├── thought_vector.py  # 思维向量通信
│   ├── dag_shapley.py     # DAG-Shapley 调度
│   ├── incremental.py     # 增量更新
│   ├── memory3d.py        # 三维记忆系统
│   ├── multimodal.py      # 多模态能力
│   ├── protocols.py       # MCP + A2A 协议
│   ├── evolution_plus.py  # 自我进化增强
│   ├── deploy.py          # 部署工具
│   ├── model_router.py    # 多模型路由器
│   ├── self_evolution.py  # 自进化引擎
│   ├── autonomous.py      # 自治引擎
│   ├── plugins.py         # 插件系统
│   ├── realtime.py        # 实时监控
│   └── ...
├── dashboard/app.py       # Streamlit 可视化大屏
├── Dockerfile             # Docker 部署
├── docker-compose.yml     # Docker Compose
├── k8s/                   # Kubernetes 清单
└── lite-edge/             # 轻量边缘版
```

## 🌐 多模型支持

| 模型 | Provider | 用途 | 成本 |
|------|----------|------|------|
| mimo-v2.5-pro | MiMo | 参谋/决策/分析 | $0.05/1k |
| deepseek-chat | DeepSeek | 代码/检索/执行 | $0.001/1k |
| claude-sonnet-4 | Anthropic | 创意/安全/审计 | $0.003/1k |
| gpt-4o | OpenAI | 通用备用 | $0.005/1k |
| llama3 | Ollama | 本地兜底 | 免费 |

**优雅降级**：DeepSeek/Claude/GPT-4 调用失败时，自动 fallback 到 MIMO。

## 📝 版本历史

| 版本 | 说明 |
|------|------|
| v3.1.0 | 六大方向深度升级：思维向量/DAG-Shapley/三维记忆/多模态/MCP+A2A/经验库/Docker |
| v3.0.0 | 六方向全面升级：自进化/多模型/插件/实时/大屏/自治 |
| v2.9.6 | Open-Meteo 毫米级降雨量 |
| v2.9 | 标签路由/模型分级/任务队列/Agent记忆 |

## 📝 Author

> Built with MIMO 🦋 | Ancient wisdom meets modern AI
>
> 皇帝: AARONCXXX | 丞相: MIMO

⭐ Star this repo if you find it useful!
