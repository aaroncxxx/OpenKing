---
name: empire-architecture
description: 帝国架构 — 基于中国古代三公九卿制的 AI 多智能体协作系统。256节点、标签路由、模型分级、任务队列、Agent记忆、量子计算思维模拟器。
metadata:
  openclaw:
    version: 2.9.5
    author: aaroncxxx
    tags: [multi-agent, quantum, ai, collaboration, empire]
---

# 帝国架构 Empire Architecture v2.9

基于中国古代三公九卿制的 AI 多智能体协作系统

## 概述

帝国架构是一个多智能体协作系统，采用三公九卿制组织架构，将复杂任务分解为多个专业 Agent 协同完成。

v2.9 全面增强：标签路由、模型分级、任务队列、Agent记忆、中文分词、配置热加载、结构化日志。

### 核心架构

- **中枢**：丞相 — 总协调，任务分解与调度，标签路由筛选
- **三公**：丞相/太尉/御史大夫 — 最高决策层
- **九卿**：太常/光禄勋/卫尉/太仆/廷尉/大鸿胪/宗正/大司农/少府 — 核心行政
- **参谋团**：16 位 — 战略/技术/情报/财务/文化/军事/外交/法务/后勤/人才/数据/安全/研究/媒体/商务/创新
- **执行官**：24 位 — 写作/编码/检索/分析/翻译/设计/审核/摘要/规划/测试/部署/监控/...
- **翰林院**：12 位博士 — 知识管理 + RAG 检索
- **六部**：吏/户/礼/兵/刑/工 — 行政执行
- **监察御史**：12 位 — 廉政/效能/品质/合规/财务/安全/数据/服务/流程/技术/风险/汇报
- **武将营**：24 位 — 军事执行
- **郡守**：32 位 — 地方治理
- **都督区**：16 位 — 军政一体
- **钦差**：14 位 — 皇帝特派
- **锦衣卫** — 安全审计 + 事前审批

### v2.9 新增

- **标签路由**：Agent 带标签，丞相按关键词筛选节点，prompt 减少 60%+
- **模型分级**：丞相/参谋→pro，执行/监察→flash，节省 token
- **任务队列**：优先级 + 超时 90s + 自动重试 2 次 + 指数退避
- **熔断器**：连续 5 次失败自动熔断 300s
- **Agent 记忆**：短期 20 条 + 长期持久化，高重要性自动存入
- **对话历史**：最近 10 轮注入 LLM 上下文
- **中文分词**：正向最大匹配 + 术语词典
- **LRU 缓存**：检索结果 5 分钟 TTL
- **配置热加载**：mtime 检测自动重载
- **结构化日志**：RotatingFileHandler 10MB×5
- **事前安全检查**：敏感关键词预警
- **消息总线增强**：deque(maxlen=2000)，Agent 间直接通信

## 快速开始

```bash
cd lite/
export MIMO_API_KEY="your-api-key"
export MIMO_API_ENDPOINT="your-endpoint"

python3 main.py              # 交互模式
python3 main.py "你的指令"    # 单次执行
python3 main.py --status     # 帝国状态
python3 main.py --agents     # 节点列表
python3 main.py --tokens     # Token 消耗
python3 main.py --knowledge  # 知识层
python3 main.py --queue      # 任务队列
python3 main.py --bus        # 消息总线
python3 main.py --memory <id> # Agent 记忆
```

## 配置

编辑 `lite/config.json` 配置帝国节点：

```json
{
  "llm": {
    "model": "mimo-v2.5-pro",
    "timeout_seconds": 60
  },
  "agents": {
    "chancellor": { "id": "chancellor", "name": "丞相", "tags": ["核心"] },
    "advisors": [{ "id": "...", "name": "...", "tags": ["参谋"] }],
    ...
  }
}
```

## 知识层

支持 8 个知识源：
- 本地 RAG（local_rag）— 默认启用，中文分词 + LRU 缓存
- 腾讯云知识引擎（tencent_cloud）
- 飞书知识库（feishu）
- Notion（notion_kb）
- WaytoAGI（waytoagi）
- DataWhale（datawhale）
- ModelScope（modelscope）
- LiblibAI（liblibai）

## 实战案例

### 案例一：明天白天中国降雨量分析

```bash
cd lite/
python3 main.py "任务一：明天白天中国降雨量分析，出一份报告"
```

**调度节点：** 探事检索、算师分析、翰林写手（3 节点）

| 指标 | 结果 |
|------|------|
| 耗时 | 92.1s |
| Token 消耗 | 10,064 |
| 锦衣卫审计 | ✅ 通过 |

**丞相汇总结果：**

| 区域 | 城市 | 降雨概率 | 预计降水量 | 主要时段 |
|:---|:---|:---|:---|:---|
| 华南 | 广州 | **95%** | 50-80mm | 全天，午后最强 |
| 华东 | 上海 | **85%** | 25-40mm | 夜间至明晨 |
| 华中 | 武汉 | **80%** | 30-50mm | 傍晚开始 |
| 华北 | 北京 | 70% | 10-20mm | 午后至夜间 |
| 西南 | 成都 | 60% | 15-25mm | 凌晨至上午 |
| 西北 | 西安 | 45% | 5-15mm | 傍晚前后 |
| 东北 | 哈尔滨 | 30% | 3-8mm | 午后零星 |

### 案例二：全国后天天气预报

```bash
cd lite/
python3 main.py "任务：全国后天天气预报。覆盖全国主要城市和区域"
```

**调度节点：** 蛛探爬取、探事检索、典库数据、算师分析、画师设计、翰林写手、校书审核（7 节点）

| 指标 | 结果 |
|------|------|
| 耗时 | 246.6s（~4分钟） |
| Token 消耗 | 35,021 |
| 锦衣卫审计 | ✅ 通过 |

**丞相汇总要点：**
- 北方：冷空气 + 大风沙尘（内蒙古、河北）
- 南方：强降雨核心区（湖南、江西、福建、广东、广西）
- 西北/华北干旱区：无明显降水

## 量子计算思维模拟器 (v2.1)

```bash
python3 skills/quantum_sim/quantum_cli.py demo          # 完整演示
python3 skills/quantum_sim/quantum_cli.py superposition  # 叠加态
python3 skills/quantum_sim/quantum_cli.py entangle       # 纠缠
python3 skills/quantum_sim/quantum_cli.py timeslice      # 时空复用
python3 skills/quantum_sim/quantum_cli.py debate         # 量子辩论
python3 skills/quantum_sim/quantum_cli.py bell           # Bell不等式
```

## 安全机制

- 事前安全检查：敏感关键词检测
- 锦衣卫审计：任务完成后安全审计
- 违规三级分类 + 投票制
- 熔断器：连续失败自动隔离

## 文件结构

```
├── README.md
├── CHANGELOG.md
├── SKILL.md
├── docs/
└── lite/
    ├── main.py           # CLI 入口
    ├── chancellor.py     # 丞相协调器
    ├── config.json       # 256 节点配置
    ├── agents/base.py    # Agent 基类（记忆+模型路由）
    ├── core/
    │   ├── bus.py        # 消息总线（maxlen+Agent间通信）
    │   ├── tokens.py     # Token 追踪（WAL+线程安全）
    │   ├── security.py   # 安全系统（事前检查）
    │   ├── taskqueue.py  # 任务队列（重试+熔断）
    │   ├── model_router.py # 模型路由器
    │   ├── memory.py     # Agent 记忆系统
    │   ├── config.py     # 配置（热加载）
    │   └── logger.py     # 结构化日志
    ├── knowledge/        # 知识层（8源）
    ├── skills/quantum_sim/ # 量子模拟器
    └── data/             # 运行时数据
        ├── knowledge/    # 向量库
        ├── logs/         # 日志文件
        ├── memory/       # Agent 长期记忆
        └── tokens.db     # Token 数据库
```

## 链接

- GitLab: https://gitlab.scnet.cn:9002/space/aaroncxxx/Empire-Architecture
