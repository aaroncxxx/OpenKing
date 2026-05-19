---
name: V2.5 CNY RMB A股 China A shares Stock
version: 2.5.0
description: >
  V2.5 A股多平台热搜分析 - 多平台热搜 + 北向资金增强 + 主力/游资/散户拆分 + 龙虎榜 + 恐慌贪婪指数 + 自选股管理 + 个股画像 + HTML报告 + 自动化推送
  关键词：A股, 大A, A-shares, China A, Onshore, 涨停, 跌停, 热搜, 北向资金, 板块轮动, 市场情绪, 龙虎榜, 主力资金, 个股画像
applyTo: "**"
---

# V2.5 A股多平台热搜分析

多平台热搜 + 资金深度分析 + 情绪指标 + 自选股管理，一站式掌握市场热点。

> **关于作者** — 米粉，A股老韭菜，美股老韭菜，期货老韭菜，币圈老韭菜，被割多了，现在只看不玩，用MIMO做个Skill大家娱乐围观A股行情，好用记得回来点星星。⭐

## 功能清单

### V2.2 新增
- ✅ 板块强度评分（涨幅+资金+热度综合，满分100）
- ✅ 多周期板块轮动（7/14/30天对比）
- ✅ 板块内部分化分析（龙头/跟风/掉队）
- ✅ 行业基本面关联（PE/PB）
- ✅ 概念板块细分（AI→AI芯片/大模型/算力租赁等）
- ✅ 个股多维画像（基本面+技术面+资金面+消息面）
- ✅ MACD/KDJ/RSI/均线技术指标
- ✅ 异常个股检测（成交量/换手率/振幅/连涨连跌）
- ✅ 热搜-涨跌关联分析
- ✅ 交互式 HTML 报告（Chart.js 图表）
- ✅ 本地数据归档（按日期）
- ✅ Webhook 自动推送（钉钉/企微/飞书）
- ✅ 定时任务管理

### V2.4 新增
- ✅ 多平台热搜覆盖（微博/东方财富股吧/雪球/抖音/知乎）
- ✅ 热搜情绪倾向分析（正面/负面/中性）
- ✅ 热搜关联事件提取
- ✅ 北向资金十大成交股
- ✅ 北向资金行业流向分布
- ✅ 北向资金持仓变动 Top10
- ✅ 主力/游资/散户资金流向拆分
- ✅ 大单/中单/小单成交占比
- ✅ 龙虎榜集成
- ✅ 恐慌贪婪指数（多维度综合）
- ✅ 两融余额变化
- ✅ 涨跌停家数历史分位
- ✅ 自选股批量导入导出（TXT/CSV）
- ✅ 自选股分组管理（短线/中线/行业）
- ✅ 自选股实时预警系统
- ✅ AKShare 适配层（版本兼容 + 降级机制）
- ✅ 代理池支持（解决限流）
- ✅ 黑名单过滤（过滤泛关键词）
- ✅ 多平台数据源状态显示

### V2.0 继承
- ✅ 微博实时热搜抓取 + A股关键词筛选
- ✅ 大盘指数（上证/深证/创业板）
- ✅ 涨停板 / 跌停板 TOP 列表
- ✅ 热门板块排行
- ✅ 热搜 vs 行情关联分析
- ✅ 北向资金实时数据（沪股通/深股通）
- ✅ 大盘5日趋势 + 迷你趋势图
- ✅ 行业/板块关键词库增强（60+板块）
- ✅ 本地快照缓存 + 历史数据对比
- ✅ `--json` 结构化输出
- ✅ `--brief` 精简模式
- ✅ `--trend` 趋势模式
- ✅ `--stock <代码>` 查询单只股票详情
- ✅ `--watchlist <自选股>` 自选股过滤
- ✅ `--md` Markdown 格式输出
- ✅ `--html` 交互式 HTML 报告（开发中）
- ✅ 市场情绪指标（涨跌比、涨跌家数）
- ✅ 板块轮动分析（近3天对比）
- ✅ 非交易日/盘前自动提示
- ✅ 并行数据抓取（ThreadPoolExecutor）

## When to Use

| Situation | Use this skill? |
|---|---|
| 用户说"A股分析" / "股市热搜" / "今天行情" | ✅ Yes |
| 用户问"今天有什么热门股票" | ✅ Yes |
| 用户想看多平台热搜 | ✅ Yes |
| 盘后复盘 / 盘中监控 | ✅ Yes |
| 用户问"北向资金今天流入多少" | ✅ Yes |
| 用户问"主力资金流向" | ✅ Yes |
| 用户问"龙虎榜" | ✅ Yes |
| 用户问"恐慌贪婪指数" | ✅ Yes |
| 用户问"大盘最近走势怎么样" | ✅ Yes |
| 用户问"688256最近怎么样" | ✅ Yes |
| 用户想看自选股的热搜情况 | ✅ Yes |
| 用户想导入导出自选股 | ✅ Yes |

## Usage

```bash
python3 "{baseDir}/scripts/analyzer.py" [options]
```

### Options

| Flag | Description |
|------|-------------|
| `--json` | JSON 格式输出 |
| `--brief` | 精简模式：仅热搜 + 涨停 |
| `--trend` | 趋势模式：含大盘5日走势 |
| `--md` | Markdown 格式输出 |
| `--html` | 交互式 HTML 报告（Chart.js 图表） |
| `--no-weibo` | 跳过热搜数据（只看行情） |
| `--no-market` | 跳过行情数据（只看热搜） |
| `--platforms <平台>` | 指定热搜平台（weibo,eastmoney,xueqiu,douyin,zhihu） |
| `--proxy <地址>` | 代理地址（解决限流） |
| `--stock <代码>` | 查询单只股票详情 + 资金流向 |
| `--profile <代码>` | 个股多维画像（基本面+技术+资金+消息+异常） |
| `--sector-detail <板块>` | 板块内部分析（龙头/跟风/掉队） |
| `--subdivisions <概念>` | 概念细分赛道（如 AI、新能源） |
| `--watchlist <股票>` | 自选股过滤（逗号分隔） |
| `--watchlist-file <路径>` | 从 TXT/CSV 导入自选股 |
| `--export-watchlist <路径>` | 导出自选股到 TXT |
| `--archive` | 归档本次报告到本地 |
| `--push` | 推送到已配置的 Webhook |
| `--schedule <配置>` | 添加定时任务（名称,时间,参数） |
| `--webhook <配置>` | 添加 Webhook（名称,URL,类型） |
| `--list-schedules` | 列出定时任务 |
| `--list-archives` | 列出归档文件 |
| `--version` | 显示版本号 |
| `-h, --help` | 显示帮助信息 |

### Examples

```bash
# 完整分析（所有平台热搜 + 行情 + 资金 + 情绪）
python3 "{baseDir}/scripts/analyzer.py"

# 只看微博热搜
python3 "{baseDir}/scripts/analyzer.py" --platforms weibo

# 只看雪球 + 东方财富
python3 "{baseDir}/scripts/analyzer.py" --platforms xueqiu,eastmoney

# 使用代理（解决微博限流）
python3 "{baseDir}/scripts/analyzer.py" --proxy http://127.0.0.1:7890

# 查询单只股票 + 资金流向
python3 "{baseDir}/scripts/analyzer.py" --stock 688256

# 自选股模式
python3 "{baseDir}/scripts/analyzer.py" --watchlist "寒武纪,中芯国际,贵州茅台"

# 从文件导入自选股
python3 "{baseDir}/scripts/analyzer.py" --watchlist-file my_stocks.txt

# 导出自选股
python3 "{baseDir}/scripts/analyzer.py" --export-watchlist backup.txt

# 精简模式
python3 "{baseDir}/scripts/analyzer.py" --brief

# 趋势 + Markdown
python3 "{baseDir}/scripts/analyzer.py" --trend --md

# JSON 输出
python3 "{baseDir}/scripts/analyzer.py" --json
```

## 输出格式

```
📊 A股热搜分析报告 v2.5
⏰ 2026-05-19 15:00
==================================================

📡 【数据源状态】
  微博: ✓ 50条  东方财富股吧: ✓ 30条  雪球: ✓ 25条

⚪ 【恐慌贪婪指数】
  指数: 52 — 中性

🟢 【市场情绪】
  上涨 2800 家 / 下跌 1800 家 / 平盘 400 家
  涨跌比 2800:1800  上涨占比 56.0%
  涨停 42 家 / 跌停 5 家

📈 【大盘概览】
  🟢 上证指数: 3288.41 (+0.52%)
  🔴 深证成指: 10245.67 (-0.09%)
  🔴 创业板指: 2045.12 (-0.27%)

🌊 【北向资金】
  🟢 净流入: 45.23亿

🏆 【北向十大成交股】
  🟢 贵州茅台(600519) 净买入 12.3亿

🏭 【北向行业流向 TOP10】
  🟢 电子: 8.5亿  🟢 医药: 5.2亿

💰 【主力资金】
  🔴 主力净流入: -32.15亿
  🟢 超大单: 15.23亿  🔴 大单: -47.38亿

🐉 【龙虎榜】
  🟢 寒武纪(688256) 净买 5.23亿  AI芯片

🔥 【A股热搜（多平台）】
  🟢#寒武纪涨停#  🔥17.5万  (板块「AI」) [微博] 📡
  ⚪#A股牛市来了#  🔥12.3万  (精确「A股」) [微博/雪球] 📡

🟢 【涨停板 TOP10】
  寒武纪(688256) +20.0%  AI芯片
```

## 数据源

| 源 | 说明 | 需要 API Key |
|----|------|-------------|
| 微博热搜 | 公开 API | ❌ |
| 东方财富股吧 | 公开 API | ❌ |
| 雪球 | 公开 API | ❌ |
| 抖音热搜 | 公开 API | ❌ |
| 知乎热榜 | 公开 API | ❌ |
| AKShare (东方财富) | A股行情 + 资金数据 | ❌ |

## 依赖

- Python 3.8+
- akshare (`pip3 install akshare`)

## 自定义配置

- 修改 `sources/multi_platform.py` 中的 `SECTOR_KEYWORDS` 可添加关注的板块
- 修改 `EXACT_KEYWORDS` 调整精确匹配规则
- 修改 `BLACKLIST_KEYWORDS` 调整黑名单过滤
- 快照缓存在 `scripts/.cache/` 目录
- 自选股配置在 `scripts/.cache/watchlist/watchlist.json`

## 版本历史

### v2.5.0 (2026-05-19) — 全面升级
- 🆕 多平台热搜（微博/东方财富股吧/雪球/抖音/知乎）+ 情绪分析 + 事件提取
- 🆕 北向资金增强（十大成交股/行业流向/持仓变动）+ 主力拆分 + 龙虎榜
- 🆕 恐慌贪婪指数 + 两融余额 + 涨跌停历史分位
- 🆕 自选股管理（分组/导入导出/预警/简报）
- 🆕 个股多维画像（`--profile`，基本面+技术面+资金面+消息面+异常检测）
- 🆕 板块强度评分 + 多周期轮动 + 内部分化 + 概念细分
- 🆕 交互式 HTML 报告（`--html`，Chart.js 图表）
- 🆕 定时任务 + Webhook 推送 + 本地归档
- 🆕 AKShare 适配层 + 代理支持
- 🔧 代码重构为模块化架构（sources/analysis/output/utils）

### v2.0.0 (2026-05-12)
- 🆕 `--stock` 单只股票查询
- 🆕 `--watchlist` 自选股模式
- 🆕 `--md` Markdown 格式导出
- 🆕 市场情绪指标
- 🆕 板块轮动分析
- 🆕 非交易日提示
- 🆕 ThreadPoolExecutor 并行数据抓取

### v1.1.0 (2026-05-01)
- 🌊 北向资金数据
- 📉 `--trend` 大盘5日趋势
- 🔍 关键词匹配增强

### v1.0.0 (2026-05-01)
- 🚀 首发
