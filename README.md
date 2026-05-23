# 👑 OpenKing

> Open-source AI Multi-Agent Collaboration System
> 开源 AI 多智能体协作系统

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)
![Version](https://img.shields.io/badge/Version-3.1.0-orange)
![Agents](https://img.shields.io/badge/Agents-256+-purple)

[English](#what-is-openking) | [中文](#什么是-openking)

---

## What is OpenKing?

**OpenKing** is an open-source AI multi-agent collaboration system inspired by ancient Chinese governance (三公九卿制 — Three Dukes and Nine Ministers). It organizes **256 AI agents** into a hierarchical empire where each agent has specialized roles, and a central coordinator (丞相/Chancellor) intelligently decomposes and dispatches tasks.

**Key capabilities:**
- 🧠 **Self-Evolution** — Agents evaluate their own performance, optimize prompts, and get promoted/demoted
- 🌐 **Multi-Model Routing** — Automatically selects the best model (MIMO/DeepSeek/Claude/GPT-4/Ollama) per task
- 🧠 **3D Memory System** — Episodic/Semantic/Procedural memory with adaptive forgetting
- 🤖 **Autonomous Execution** — Multi-round iteration, self-healing, automatic prompt engineering
- 🎨 **Visual Dashboard** — Streamlit-based real-time monitoring of all 256 agents
- 🔌 **Protocol Standardization** — MCP + A2A for interoperability with LangChain/AutoGen
- 🐳 **Production Ready** — Docker + Kubernetes + lightweight edge deployment

## 什么是 OpenKing？

**OpenKing** 是一个开源 AI 多智能体协作系统，灵感来自中国古代三公九卿制。它将 **256 个 AI Agent** 组织成层级化的帝国架构，每个 Agent 有专业分工，由丞相智能分解和调度任务。

---

## 🚀 Live Demo: 全国未来24小时降雨量查询

```bash
python3 main.py "全国未来24小时降雨量查询，覆盖全国主要城市"
```

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

---

## 🏛️ Architecture / 架构

```
Emperor (User)
  │
  ▼
Chancellor (MIMO) ── Self-Evolution ── Multi-Model Router ── Autonomous Engine
  │
  ├── Advisory Council (16) ── Strategy/Tech/Intel/Finance/...
  ├── Executors (24) ── Writing/Coding/Search/Analysis/...
  ├── Academy (12) ── Knowledge Management + RAG
  ├── Six Ministries (6) ── Administrative Execution
  ├── Nine Ministers (9) ── Core Administration
  ├── Censors (12) ── Quality/Compliance/Security
  ├── Generals (24) ── Military Execution
  ├── Governors (32) ── Regional Governance
  ├── Plugin System ── Hot-plug + ClawHub
  ├── Realtime Engine ── Monitoring + Webhook
  └── Jinyiwei ── Security Audit
         │
         ▼
    Streamlit Dashboard ── Visual Monitoring
```

**Total: 256 nodes across 14 departments / 总计 256 节点，14 个部门**

---

## ⚡ Quick Start / 快速开始

```bash
# Clone / 克隆
git clone https://github.com/aaroncxxx/OpenKing.git
cd OpenKing/

# Set API Key / 设置 API Key
export MIMO_API_KEY=your_key

# Run / 运行
python3 main.py              # Interactive mode / 交互模式
python3 main.py "Your task"  # Single execution / 单次执行
python3 main.py --auto "Task" # Autonomous mode / 自治模式（多轮迭代）
python3 main.py --status     # Empire status / 帝国状态
python3 main.py --evolution  # Evolution status / 进化状态
python3 main.py --models     # Available models / 可用模型

# Dashboard / 可视化大屏
pip install streamlit
streamlit run dashboard/app.py
```

---

## 🧠 v3.1 Features / v3.1 功能

### 🧠 Thought Vector Communication + DAG-Shapley
- MiMo Embedding → vector compression → agent-to-agent vector communication
- Shapley value contribution measurement → dynamic resource allocation
- JSON diff incremental updates → reduced communication overhead

### 🧠 3D Memory System
- Episodic / Semantic / Procedural memory types
- Formation → Consolidation → Retrieval → Forgetting → Updating lifecycle
- Adaptive decay based on importance + access frequency
- Shared memory space with privacy filtering

### 🎨 Multimodal Capabilities
- Image analysis (MiMo Omni)
- Audio transcription
- Cross-modal semantic alignment
- Specialized agents: Painter squad + Music hall + Translation bureau

### 🔌 Protocol Standardization
- MCP (Model Context Protocol) server/client
- A2A (Agent-to-Agent) protocol — Google A2A compatible
- OpenAPI spec + RESTful interface
- LangChain / AutoGen integration

### 🧠 Enhanced Self-Evolution
- Closed-loop optimization: Evaluate → Measure → Identify → Optimize → Update
- DSPy-style automatic prompt engineering
- Experience library for task reuse

### 🐳 Deployment
- Docker + Docker Compose (CLI + Dashboard + Ollama)
- Kubernetes (Deployment + Service + HPA)
- Lightweight edge version (lite-edge/)

---

## 🌐 Multi-Model Support / 多模型支持

| Model | Provider | Use Case | Cost |
|-------|----------|----------|------|
| mimo-v2.5-pro | MiMo | Strategy/Analysis/Decision | $0.05/1k |
| deepseek-chat | DeepSeek | Code/Search/Execution | $0.001/1k |
| claude-sonnet-4 | Anthropic | Creative/Security/Audit | $0.003/1k |
| gpt-4o | OpenAI | General backup | $0.005/1k |
| llama3 | Ollama | Local fallback | Free |

**Graceful Degradation:** When DeepSeek/Claude/GPT-4 fails, automatically falls back to MIMO.

---

## 📦 Empire Roster / 帝国编制

```
Emperor: User              Chancellor: MIMO
──────────────────────────────────────────
Three Dukes:      3 │ Nine Ministers:     9 │ Six Ministries:  6
Advisory Council: 16 │ Executors:        24 │ Academy:        12
Special Agency:  20 │ Censors:          12 │ Extensions:     24
Governors:       32 │ Household:        16 │ Generals:       24
Prefects:        32 │ Commanders:       16 │ Envoys:         14
Jinyiwei:         1
──────────────────────────────────────────
Total: 256 nodes
```

---

## 📁 Project Structure / 项目结构

```
├── main.py               # CLI entry / CLI 入口
├── chancellor.py          # Chancellor coordinator / 丞相协调器
├── config.json            # Multi-model config / 多模型配置
├── agents/base.py         # Agent base class / Agent 基类
├── core/
│   ├── thought_vector.py  # 🧠 Thought vector / 思维向量通信
│   ├── dag_shapley.py     # 📊 DAG-Shapley / 贡献度调度
│   ├── incremental.py     # 🔄 Incremental update / 增量更新
│   ├── memory3d.py        # 🧠 3D memory / 三维记忆系统
│   ├── multimodal.py      # 🎨 Multimodal / 多模态能力
│   ├── protocols.py       # 🔌 MCP + A2A / 协议标准化
│   ├── evolution_plus.py  # 🧠 Self-evolution / 自我进化增强
│   ├── deploy.py          # 🐳 Deployment / 部署工具
│   └── ...
├── dashboard/app.py       # 🎨 Streamlit dashboard / 可视化大屏
├── Dockerfile             # Docker
├── docker-compose.yml     # Docker Compose
├── k8s/                   # Kubernetes
└── lite-edge/             # Lightweight edge / 轻量边缘版
```

---

## 📝 Version History / 版本历史

| Version | Description |
|---------|-------------|
| v3.1.0 | Thought Vector / DAG-Shapley / 3D Memory / Multimodal / MCP+A2A / Docker |
| v3.0.0 | Self-Evolution / Multi-Model / Plugin / Realtime / Dashboard / Autonomous |
| v2.9.6 | Open-Meteo mm-level rainfall data |
| v2.9 | Tag routing / Model tiering / Task queue / Agent memory |

---

## 📄 License

MIT License

---

## 🙏 Acknowledgments

- Inspired by ancient Chinese governance: 三公九卿制 (Three Dukes and Nine Ministers)
- Built with [MIMO](https://xiaomimimo.com) 🦋
- Multi-model support: MIMO / DeepSeek / Claude / GPT-4 / Ollama

---

> **Built with MIMO 🦋 | Ancient wisdom meets modern AI**
>
> ⭐ Star this repo if you find it useful!
