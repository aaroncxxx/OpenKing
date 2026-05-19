# 📊 A股多平台热搜分析 v2.5

多平台热搜 + 资金深度分析 + 情绪指标 + 自选股管理 + 个股画像 + HTML报告，一站式掌握市场热点。

> **关于作者** — 米粉，A股老韭菜，美股老韭菜，期货老韭菜，币圈老韭菜，被割多了，现在只看不玩，用MIMO做个Skill大家娱乐围观A股行情，好用记得回来点星星。⭐
>
> Mi Fan 🍚 | Rekt veteran: A-shares, US stocks, futures, crypto 📉 | Now just watching 👀 | Built with MIMO for fun | Star if you like it ⭐

## ✨ 核心特性

### 🔍 多平台热搜
- 微博 / 东方财富股吧 / 雪球 / 抖音 / 知乎 — 5大平台并行抓取
- A股关键词智能筛选（精确匹配 + 模糊匹配 + 黑名单过滤）
- 热搜情绪分析（正面 🟢 / 负面 🔴 / 中性 ⚪）
- 热搜关联事件提取（AI芯片/新能源/政策利好/业绩公告等）
- 多平台热度合并排序，标注跨平台出现的热搜 📡

### 💰 资金深度分析
- 北向资金：总净流入 + 十大成交股 + 行业流向 + 持仓变动 Top10
- 主力拆分：主力 / 游资 / 散户资金流向
- 成交拆分：超大单 / 大单 / 中单 / 小单占比
- 龙虎榜：涨停板自动标注上榜股票，显示买卖席位

### 📈 市场情绪
- 恐慌贪婪指数（多维度：涨跌比/涨跌停/北向/大盘，0-100）
- 两融余额变化
- 涨跌停家数历史分位（30日）
- 涨跌家数统计 + 涨跌比

### 📊 板块分析
- 板块强度评分（涨幅+资金+热度综合，满分100）
- 多周期轮动对比（7/14/30天）
- 板块内部分化（龙头/跟风/掉队）
- 概念细分赛道（AI→AI芯片/大模型/算力租赁等9大概念）
- 行业基本面（PE/PB）

### 🏷️ 个股画像
- 多维画像：基本面 + 技术面 + 资金面 + 消息面
- 技术指标：MACD / KDJ / RSI / MA5/10/20/60
- 异常检测：成交量/换手率/振幅/连涨连跌
- 热搜-涨跌关联分析

### 📋 自选股管理
- 批量导入导出（TXT/CSV）
- 分组管理（短线/中线/行业）
- 实时预警（涨跌幅/换手率/热搜/资金异动）
- 每日简报自动生成

### 📤 输出与自动化
- 交互式 HTML 报告（Chart.js 图表，深色主题）
- Markdown / JSON / 纯文本输出
- Webhook 自动推送（钉钉/企微/飞书）
- 定时任务管理
- 本地数据归档（按日期）

## 🚀 快速使用

```bash
# 完整分析（所有平台热搜 + 行情 + 资金 + 情绪）
python3 scripts/analyzer.py

# 精简模式（仅热搜 + 涨停）
python3 scripts/analyzer.py --brief

# 指定平台
python3 scripts/analyzer.py --platforms weibo,xueqiu

# 个股查询 + 资金流向
python3 scripts/analyzer.py --stock 688256

# 个股多维画像
python3 scripts/analyzer.py --profile 688256

# 自选股模式
python3 scripts/analyzer.py --watchlist "寒武纪,中芯国际,贵州茅台"

# 板块内部分化
python3 scripts/analyzer.py --sector-detail "半导体"

# 概念细分
python3 scripts/analyzer.py --subdivisions AI

# HTML 交互报告
python3 scripts/analyzer.py --html

# Markdown 导出
python3 scripts/analyzer.py --md

# 归档报告
python3 scripts/analyzer.py --archive

# 使用代理（解决限流）
python3 scripts/analyzer.py --proxy http://127.0.0.1:7890
```

## 📋 全部参数

| 参数 | 说明 |
|------|------|
| `--json` | JSON 格式输出 |
| `--brief` | 精简模式 |
| `--trend` | 趋势模式（含大盘5日走势） |
| `--md` | Markdown 格式输出 |
| `--html` | 交互式 HTML 报告 |
| `--no-weibo` | 跳过热搜数据 |
| `--no-market` | 跳过行情数据 |
| `--platforms <平台>` | 指定热搜平台 |
| `--proxy <地址>` | 代理地址 |
| `--stock <代码>` | 查询单只股票 |
| `--profile <代码>` | 个股多维画像 |
| `--sector-detail <板块>` | 板块内部分析 |
| `--subdivisions <概念>` | 概念细分查询 |
| `--watchlist <股票>` | 自选股过滤 |
| `--watchlist-file <路径>` | 从文件导入自选股 |
| `--export-watchlist <路径>` | 导出自选股 |
| `--archive` | 归档本次报告 |
| `--push` | 推送到 Webhook |
| `--schedule <配置>` | 添加定时任务 |
| `--webhook <配置>` | 添加 Webhook |
| `--list-schedules` | 列出定时任务 |
| `--list-archives` | 列出归档文件 |

## 📦 依赖

- Python 3.8+
- `pip3 install akshare`（行情/资金数据，可选）

## 📁 文件结构

```
scripts/
├── analyzer.py              # 主入口
├── sources/                 # 数据源（5个平台）
│   ├── weibo.py             # 微博热搜
│   ├── eastmoney_guba.py    # 东方财富股吧
│   ├── xueqiu.py            # 雪球
│   ├── douyin.py            # 抖音
│   ├── zhihu.py             # 知乎
│   └── multi_platform.py    # 聚合 + 筛选
├── analysis/                # 分析模块
│   ├── hotsearch.py         # 热搜深度分析
│   ├── capital.py           # 资金分析
│   ├── sentiment.py         # 市场情绪
│   ├── watchlist.py         # 自选股管理
│   ├── sector.py            # 板块分析
│   └── stock_profile.py     # 个股画像
├── output/                  # 输出模块
│   ├── html_report.py       # HTML 报告
│   └── automation.py        # 自动化
└── utils/                   # 工具
    ├── common.py            # 通用函数
    └── akshare_adapter.py   # AKShare 适配层
```

## 📚 数据源

| 源 | 说明 | API Key |
|----|------|---------|
| 微博热搜 | 公开 API | ❌ |
| 东方财富股吧 | 公开 API | ❌ |
| 雪球 | 公开 API | ❌ |
| 抖音热搜 | 公开 API | ❌ |
| 知乎热榜 | 公开 API | ❌ |
| AKShare | A股行情 + 资金 | ❌ |

## 📝 版本历史

### v2.5.0 (2026-05-19) — 全面升级
- 🆕 多平台热搜（5大平台）+ 情绪分析 + 事件提取
- 🆕 北向资金增强 + 主力拆分 + 龙虎榜
- 🆕 恐慌贪婪指数 + 两融 + 涨跌停分位
- 🆕 自选股管理（分组/导入导出/预警/简报）
- 🆕 个股多维画像（基本面+技术+资金+消息+异常检测）
- 🆕 板块强度评分 + 多周期轮动 + 内部分化 + 概念细分
- 🆕 交互式 HTML 报告
- 🆕 定时任务 + Webhook 推送 + 本地归档
- 🆕 AKShare 适配层 + 代理支持
- 🔧 代码重构为模块化架构

### v2.0.0 (2026-05-12)
- 个股查询、自选股、Markdown导出、市场情绪、板块轮动

### v1.1.0 (2026-05-01)
- 北向资金、5日趋势、关键词增强、快照缓存

### v1.0.0 (2026-05-01)
- 首发
