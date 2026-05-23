# 🏛️ Empire Architecture v3.0.0

> 基于中国古代三公九卿制的 AI 多智能体协作系统
> AI Multi-Agent Collaboration System Inspired by Ancient Chinese Governance

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)
![Version](https://img.shields.io/badge/Version-3.0.0-orange)
![Agents](https://img.shields.io/badge/Agents-256+-purple)

## ✨ v3.0 六大方向全面升级

### 🧠 方向一：自进化 — Agent 能自己学
- **自我评估**：每次任务后自动评分（质量/速度/协作效率）
- **技能进化**：Agent 根据历史任务自动优化 system prompt
- **淘汰与晋升**：低效 Agent 自动降级，高效 Agent 晋升（郡守→九卿）
- **丞相学习**：调度策略从固定规则 → 基于历史数据动态调整

### 🌐 方向二：多模型混战 — 不只 MIMO
- **模型路由 v2**：按任务类型选模型（代码→DeepSeek，分析→MIMO，创意→Claude）
- **统一接口**：MIMO / DeepSeek / Claude / GPT-4 / Ollama 全支持
- **成本优化**：实时追踪 token 花费，自动切换性价比最高的模型
- **本地模型兜底**：Ollama 接入，断网不瘫痪

### 🔌 方向三：插件生态 — 帝国可扩展
- **热插拔 Agent**：运行时动态增减节点，不用重启
- **技能市场**：从 ClawHub 一键安装新技能到帝国
- **自定义 Agent**：用户可以自己写 Python 类，注册进帝国
- **Agent SDK**：标准化接口，第三方也能开发帝国插件

### 📡 方向四：实时协作 — 帝国永不眠
- **持续监控模式**：帝国后台常驻，自动抓取新闻/行情/天气
- **事件驱动**：检测到异常自动触发任务
- **消息推送**：任务完成自动推送到 钉钉/飞书/企微 Webhook

### 🎨 方向五：可视化大屏 — 帝国看得见
- **Web Dashboard**：Streamlit 实时查看 256 节点状态、任务队列、token 消耗
- **自进化仪表盘**：Agent 评分、等级分布、进化进度
- **模型路由可视化**：各模型使用量、成本、调用次数
- **任务执行面板**：在 Dashboard 中直接下达指令

### 🤖 方向六：Agent 自治 — 丞相独立决策
- **多轮迭代**：任务结果不满意自动重做，直到达标
- **并行编排**：独立任务同时跑，依赖任务自动排序
- **异常自愈**：节点失败自动切换备用节点，不中断任务

## 🚀 Quick Start

```bash
cd lite-v3/
export MIMO_API_KEY=your_key
python3 main.py              # 交互模式
python3 main.py "你的指令"    # 单次执行
python3 main.py --auto "指令" # 自治模式（多轮迭代）
python3 main.py --status     # 帝国状态
python3 main.py --agents     # 节点列表
python3 main.py --tokens     # Token 消耗
python3 main.py --evolution  # 进化状态
python3 main.py --models     # 可用模型
python3 main.py --plugins    # 插件列表
python3 main.py --realtime   # 实时监控
```

## 🎨 可视化大屏

```bash
pip install streamlit
streamlit run dashboard/app.py
```

## 🌐 多模型配置

编辑 `config.json` 中的 `models` 部分：

```json
{
  "models": {
    "mimo": { "base_url": "...", "name": "mimo-v2.5-pro" },
    "deepseek": { "base_url": "...", "name": "deepseek-chat" },
    "claude": { "base_url": "...", "name": "claude-sonnet-4-20250514" },
    "gpt4": { "base_url": "...", "name": "gpt-4o" },
    "ollama": { "base_url": "http://localhost:11434/v1", "name": "llama3" }
  }
}
```

## 📐 架构

```
皇帝 (AARONCXXX)
  │
  ▼
丞相 (MIMO) ── 自进化引擎 ── 多模型路由 ── 自治引擎
  │
  ├── 参谋团 (16) ── 战略/技术/情报/财务/...
  ├── 执行官 (24) ── 写作/编码/检索/分析/...
  ├── 翰林院 (12) ── 知识管理 + RAG 检索
  ├── 六部 (6) ── 行政执行
  ├── 九卿 (9) ── 核心行政
  ├── 监察 (12) ── 品质/合规/安全
  ├── 武将 (24) ── 军事执行
  ├── 郡守 (32) ── 地方治理
  ├── 插件系统 ── 热插拔 + ClawHub
  ├── 实时引擎 ── 监控 + Webhook
  └── 锦衣卫 ── 安全审计
         │
         ▼
    Streamlit Dashboard ── 可视化大屏
```

## 📁 文件结构

```
lite-v3/
├── main.py               # CLI 入口
├── chancellor.py          # 丞相协调器 v3.0
├── config.json            # 配置（多模型 + 进化 + 插件）
├── agents/
│   └── base.py            # Agent 基类 v3.0
├── core/
│   ├── autonomous.py      # 🤖 自治引擎（多轮迭代 + 自愈）
│   ├── bus.py             # 消息总线
│   ├── config.py          # 配置加载（平滑升级）
│   ├── logger.py          # 结构化日志
│   ├── memory.py          # Agent 记忆
│   ├── model_router.py    # 🌐 多模型路由器
│   ├── plugins.py         # 🔌 插件系统
│   ├── realtime.py        # 📡 实时协作引擎
│   ├── security.py        # 安全系统
│   ├── self_evolution.py  # 🧠 自进化引擎
│   ├── taskqueue.py       # 任务队列
│   ├── tokens.py          # Token 追踪
│   └── weather.py         # 天气数据
├── dashboard/
│   └── app.py             # 🎨 Streamlit 可视化大屏
├── knowledge/             # 知识层
└── data/                  # 运行时数据
```

## 🔄 从 v2.x 升级

v3.0 **平滑兼容** v2.x 配置：
- `config.json` 中的 `agents` 部分无需修改
- 新增的 `models`、`evolution`、`plugins`、`realtime` 字段会自动用默认值填充
- 直接替换 `lite/` → `lite-v3/` 即可

## 📝 Author

> Built with MIMO 🦋 | Ancient wisdom meets modern AI
>
> 皇帝: AARONCXXX | 丞相: MIMO

⭐ Star this repo if you find it useful!
