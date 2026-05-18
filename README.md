# 🏛️ Empire Architecture v2.9

> 基于中国古代三公九卿制的 AI 多智能体协作系统
> AI Multi-Agent Collaboration System Inspired by Ancient Chinese Governance

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)
![Version](https://img.shields.io/badge/Version-2.9.5-orange)
![Agents](https://img.shields.io/badge/Agents-256-purple)

## ✨ Features / 功能

### 🏛️ 核心架构

- **三公九卿制** — 古代治理结构映射 AI Agent 架构
- **256 节点** — 三公/九卿/参谋/执行/翰林/监察/武将/郡守/钦差等 14 个编制
- **标签路由** — 按任务关键词自动筛选相关节点，减少 60%+ 无效调度
- **丞相协调** — 智能任务分解、并行编排、结果汇总

### ⚡ 性能与可靠性

- **模型分级** — 丞相/参谋用 pro 模型，执行/监察用 flash 模型，节省 token
- **任务队列** — 优先级队列 + 超时 90s + 自动重试 + 指数退避
- **熔断器** — 连续 5 次失败自动熔断，300s 后半开重试
- **SQLite WAL** — 并发读写不冲突
- **线程安全** — 256 节点并发 token 追踪

### 🧠 知识与记忆

- **知识层** — 本地 RAG + 腾讯云/飞书/Notion/WaytoAGI 等 8 个知识源
- **中文分词** — 正向最大匹配 + 量子/技术术语词典，检索精度提升
- **LRU 缓存** — 查询结果 5 分钟 TTL，命中率追踪
- **Agent 记忆** — 短期记忆（20 条滑动窗口）+ 长期记忆（持久化），越用越聪明
- **对话历史** — 最近 10 轮自动注入 LLM 上下文

### 🔒 安全与运维

- **事前安全检查** — 敏感关键词检测预警
- **锦衣卫审计** — 任务完成后安全审计
- **配置热加载** — 检测文件变更自动重载，无需重启
- **结构化日志** — RotatingFileHandler，10MB×5 轮转，按模块分文件
- **消息总线** — deque(maxlen=2000) 防 OOM，支持 Agent 间直接通信

### 🔮 量子计算思维模拟器 (v2.1)

- 叠加态 / 纠缠 / 时空复用 / 量子辩论 / 量子行走 / Bell 不等式
- GHZ 态 / W 态 / QComm 二进制协议
- 拉丁超立方抽样 + WebGL 3D 可视化

## 🚀 Quick Start / 快速开始

```bash
cd lite/
export MIMO_API_KEY=your_key
python3 main.py              # 交互模式
python3 main.py "你的指令"    # 单次执行
python3 main.py --status     # 查看帝国状态
python3 main.py --agents     # 查看所有节点
python3 main.py --tokens     # Token 消耗
python3 main.py --knowledge  # 知识层状态
python3 main.py --queue      # 任务队列
python3 main.py --bus        # 消息总线
python3 main.py --memory <id> # Agent 记忆
```

## 📦 帝国编制

```
皇帝: AARONCXXX         丞相: Mimo
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

## 🧪 实战案例

### 案例一：明天白天中国降雨量分析

```bash
python3 main.py "任务一：明天白天中国降雨量分析，出一份报告"
```

| 指标 | 结果 |
|------|------|
| 调度节点 | 探事检索、算师分析、翰林写手（3 节点） |
| 耗时 | 92.1s |
| Token 消耗 | 10,064 |
| 锦衣卫审计 | ✅ 通过 |

丞相汇总：华南广州 95% 暴雨 50-80mm ⚠️ → 东北哈尔滨 30% 零星小雨

### 案例二：全国后天天气预报

```bash
python3 main.py "任务：全国后天天气预报。覆盖全国主要城市和区域"
```

| 指标 | 结果 |
|------|------|
| 调度节点 | 蛛探爬取、探事检索、典库数据、算师分析、画师设计、翰林写手、校书审核（7 节点） |
| 耗时 | 246.6s（~4分钟） |
| Token 消耗 | 35,021 |
| 锦衣卫审计 | ✅ 通过 |

丞相汇总：北方冷空气+沙尘 / 南方强降雨核心区（湘赣闽粤桂）/ 西北华北无明显降水

## 🔮 量子模拟器

```bash
python3 skills/quantum_sim/quantum_cli.py demo        # 完整演示
python3 skills/quantum_sim/quantum_cli.py superposition # 叠加态
python3 skills/quantum_sim/quantum_cli.py entangle      # 纠缠
python3 skills/quantum_sim/quantum_cli.py timeslice     # 时空复用
python3 skills/quantum_sim/quantum_cli.py debate        # 量子辩论
python3 skills/quantum_sim/quantum_cli.py bell          # Bell不等式
```

## 📐 架构

```
皇帝 (AARONCXXX)
  │
  ▼
丞相 (Mimo) ── 标签路由 ── 模型分级
  │
  ├── 参谋团 (16) ── 战略/技术/情报/财务/...
  ├── 执行官 (24) ── 写作/编码/检索/分析/...
  ├── 翰林院 (12) ── 知识管理 + RAG 检索
  ├── 六部 (6) ── 行政执行
  ├── 九卿 (9) ── 核心行政
  ├── 监察 (12) ── 品质/合规/安全
  ├── 武将 (24) ── 军事执行
  ├── 郡守 (32) ── 地方治理
  └── 锦衣卫 ── 安全审计
         │
         ▼
    知识层 (8 源) ── 本地RAG / 腾讯云 / 飞书 / Notion / ...
```

## 🗂️ 版本历史

| 版本 | 说明 |
|------|------|
| v2.9 | 全面增强：标签路由/模型分级/任务队列/Agent记忆/中文分词/热加载 |
| v2.1.2 | QComm 二进制协议 + GHZ/W 多比特纠缠 |
| v2.1.1 | LHS 抽样 + 响应式 UI + WebGL 可视化 |
| v2.1 | 量子计算思维模拟器 |
| v2.0.1 | JSON 解析修复 + 知识层集成 + Token 计数修复 |
| v2.0 | 归一版：版本收敛 + 结构重组 |
| v1.x | 早期版本（24→537 节点演进） |

## 📝 Author / 作者

> Built with MIMO 🦋 | Ancient wisdom meets modern AI
>
> 皇帝: AARONCXXX | 丞相: MIMO

⭐ Star this repo if you find it useful!
