#!/usr/bin/env python3
"""
A股热搜分析 v2.4 — 主入口
多平台热搜 + 资金分析 + 情绪指标 + 自选股管理 + 龙虎榜
"""

import json
import sys
import os
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 确保能 import 子模块
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from utils.common import (
    VERSION, log, format_hot, format_yi,
    is_trading_day, get_last_trading_date,
    save_snapshot, load_recent_snapshots,
)
from sources.multi_platform import (
    fetch_all_hot_sources, filter_stock_keywords, merge_multi_platform_results,
    PLATFORM_SOURCES,
)
from sources.weibo import fetch_weibo_hot
from analysis.hotsearch import HotSearchAnalyzer
from analysis.capital import CapitalAnalyzer
from analysis.sentiment import SentimentAnalyzer
from analysis.watchlist import WatchlistManager
from utils.akshare_adapter import adapter as ak_adapter
from analysis.sector import SectorAnalyzer
from analysis.stock_profile import StockProfiler
from output.html_report import generate_html_report
from output.automation import AutomationManager

# AKShare 行情（通过适配器）
try:
    import akshare as ak
    import warnings
    warnings.filterwarnings("ignore")
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False


# ============================================================
# 行情数据（保留原逻辑 + 增强）
# ============================================================
def fetch_market_overview():
    if not HAS_AKSHARE:
        return []
    results = []
    for symbol, name in [("sh000001", "上证指数"), ("sz399001", "深证成指"), ("sz399006", "创业板指")]:
        try:
            df = ak.stock_zh_index_daily(symbol=symbol)
            if df is not None and len(df) >= 2:
                close = float(df.iloc[-1]["close"])
                prev = float(df.iloc[-2]["close"])
                pct = (close - prev) / prev * 100
                results.append({"name": name, "close": round(close, 2), "change_pct": round(pct, 2)})
        except Exception:
            continue
    return results


def fetch_market_trend(days=5):
    if not HAS_AKSHARE:
        return {}
    results = {}
    for symbol, name in [("sh000001", "上证指数"), ("sz399001", "深证成指"), ("sz399006", "创业板指")]:
        try:
            df = ak.stock_zh_index_daily(symbol=symbol)
            if df is not None and len(df) >= days:
                recent = df.tail(days)
                trend = [{"date": str(r.get("date", "")), "close": round(float(r["close"]), 2)} for _, r in recent.iterrows()]
                if len(trend) >= 2:
                    total = (trend[-1]["close"] - trend[0]["close"]) / trend[0]["close"] * 100
                    results[name] = {
                        "trend": trend,
                        "total_change_pct": round(total, 2),
                        "direction": "📈" if total > 0 else "📉" if total < 0 else "➡️",
                    }
        except Exception:
            continue
    return results


def fetch_zt_dt():
    if not HAS_AKSHARE:
        return {"涨停": [], "跌停": []}
    from datetime import datetime
    today = datetime.now().strftime("%Y%m%d")
    result = {"涨停": [], "跌停": []}
    try:
        zt_df = ak.stock_zt_pool_em(date=today)
        if zt_df is not None and not zt_df.empty:
            for _, row in zt_df.head(15).iterrows():
                result["涨停"].append({
                    "code": str(row.get("代码", "")),
                    "name": str(row.get("名称", "")),
                    "change_pct": float(row.get("涨跌幅", 0)),
                    "reason": str(row.get("涨停原因", "")),
                    "turnover": str(row.get("换手率", "")),
                })
    except Exception:
        pass
    try:
        dt_df = ak.stock_zt_pool_dtgc_em(date=today)
        if dt_df is not None and not dt_df.empty:
            for _, row in dt_df.head(15).iterrows():
                result["跌停"].append({
                    "code": str(row.get("代码", "")),
                    "name": str(row.get("名称", "")),
                    "change_pct": float(row.get("涨跌幅", 0)),
                })
    except Exception:
        pass
    return result


def fetch_hot_sectors():
    if not HAS_AKSHARE:
        return []
    try:
        df = ak.stock_board_industry_name_em()
        if df is not None and not df.empty:
            sectors = []
            for _, row in df.head(15).iterrows():
                try:
                    lc = float(row["领涨股票-涨跌幅"]) if "领涨股票-涨跌幅" in row.index else 0
                except (ValueError, TypeError):
                    lc = 0
                try:
                    uc = int(row["上涨家数"]) if "上涨家数" in row.index else 0
                except (ValueError, TypeError):
                    uc = 0
                try:
                    dc = int(row["下跌家数"]) if "下跌家数" in row.index else 0
                except (ValueError, TypeError):
                    dc = 0
                sectors.append({
                    "name": str(row.get("板块名称", "")),
                    "change_pct": float(row.get("涨跌幅", 0)),
                    "leader": str(row.get("领涨股票", "")),
                    "leader_change": lc,
                    "up_count": uc,
                    "down_count": dc,
                })
            return sectors
    except Exception as e:
        log(f"⚠️  板块数据获取失败: {e}")
    return []


def fetch_single_stock(code):
    """查询单只股票详情"""
    if not HAS_AKSHARE:
        return None
    try:
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            row = df[df["代码"] == code]
            if row.empty:
                return None
            r = row.iloc[0]
            return {
                "code": str(r.get("代码", "")),
                "name": str(r.get("名称", "")),
                "price": float(r.get("最新价", 0)),
                "change_pct": float(r.get("涨跌幅", 0)),
                "change_amt": float(r.get("涨跌额", 0)),
                "volume": float(r.get("成交量", 0)),
                "turnover": float(r.get("成交额", 0)),
                "high": float(r.get("最高", 0)),
                "low": float(r.get("最低", 0)),
                "open": float(r.get("今开", 0)),
                "prev_close": float(r.get("昨收", 0)),
                "pe": r.get("市盈率-动态", ""),
                "total_mv": r.get("总市值", ""),
                "circ_mv": r.get("流通市值", ""),
                "turnover_rate": r.get("换手率", ""),
            }
    except Exception as e:
        log(f"⚠️  个股查询失败: {e}")
    return None


def analyze_sector_rotation():
    """板块轮动分析（近3天对比）"""
    snapshots = load_recent_snapshots(3)
    if len(snapshots) < 2:
        return None
    try:
        today_sectors = {s["name"]: s["change_pct"] for s in snapshots[-1].get("sectors", [])}
        prev_sectors = {s["name"]: s["change_pct"] for s in snapshots[-2].get("sectors", [])}
        today_set = set(today_sectors.keys())
        prev_set = set(prev_sectors.keys())
        new_in = today_set - prev_set
        gone = prev_set - today_set
        both = today_set & prev_set
        hot_rotation = []
        for name in both:
            diff = today_sectors[name] - prev_sectors.get(name, 0)
            if abs(diff) > 1:
                hot_rotation.append({"name": name, "today": today_sectors[name], "change": round(diff, 2)})
        hot_rotation.sort(key=lambda x: -x["change"])
        return {
            "new": list(new_in)[:5],
            "gone": list(gone)[:5],
            "hot": hot_rotation[:5],
        }
    except Exception:
        return None


def analyze_correlation(stock_hot, zt_dt, sectors):
    """关联分析"""
    analysis = {"hot_stock_mentions": [], "hot_and_zt": [], "hot_sectors": [], "insights": []}
    stock_names = [i["keyword"].replace("#", "") for i in stock_hot if 2 <= len(i["keyword"].replace("#", "")) <= 8]
    analysis["hot_stock_mentions"] = stock_names[:10]
    zt_names = [i["name"] for i in zt_dt.get("涨停", [])]
    overlap = [n for n in stock_names if n in zt_names]
    if overlap:
        analysis["hot_and_zt"] = overlap
        analysis["insights"].append(f"🔥 同时出现在热搜和涨停板: {', '.join(overlap)}")
    if zt_dt.get("涨停"):
        reasons = {}
        for item in zt_dt["涨停"]:
            r = item.get("reason", "").strip()
            if r:
                reasons[r] = reasons.get(r, 0) + 1
        for r, c in sorted(reasons.items(), key=lambda x: -x[1])[:3]:
            analysis["insights"].append(f"📈 涨停原因「{r}」: {c} 只")
    return analysis


# ============================================================
# 报告生成（V2.4 增强）
# ============================================================
def render_text(data, args):
    lines = []
    lines.append("📊 A股热搜分析报告 v2.5")
    lines.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if not is_trading_day():
        lines.append(f"🏖️  今日非交易日，数据为最近交易日 ({get_last_trading_date()})")
    lines.append("=" * 50)

    # 平台数据源状态
    if data.get("platform_status"):
        lines.append(f"\n📡 【数据源状态】")
        lines.append("-" * 40)
        for pf, count in data["platform_status"].items():
            status = f"✓ {count}条" if count > 0 else "✗ 失败"
            lines.append(f"  {pf}: {status}")

    # 恐慌贪婪指数
    fg = data.get("fear_greed", {})
    if fg:
        lines.append(f"\n{fg.get('emoji', '⚪')} 【恐慌贪婪指数】")
        lines.append("-" * 40)
        lines.append(f"  指数: {fg.get('index', 50)} — {fg.get('level', '中性')}")
        for detail_name, detail_val in fg.get("details", {}).items():
            lines.append(f"  · {detail_name}: {detail_val['value']} (得分 {detail_val['score']})")

    # 市场情绪
    stats = data.get("stats", {})
    if stats:
        total = stats.get("total", 0)
        up = stats.get("up", 0)
        down = stats.get("down", 0)
        flat = stats.get("flat", 0)
        emoji = "🟢" if up > down else "🔴" if down > up else "⚪"
        lines.append(f"\n{emoji} 【市场情绪】")
        lines.append("-" * 40)
        lines.append(f"  上涨 {up} 家 / 下跌 {down} 家 / 平盘 {flat} 家（共 {total} 家）")
        lines.append(f"  涨跌比 {up}:{down}  上涨占比 {stats.get('up_ratio', 0)}%")
        zt_count = len(data.get("zt_dt", {}).get("涨停", []))
        dt_count = len(data.get("zt_dt", {}).get("跌停", []))
        if zt_count or dt_count:
            lines.append(f"  涨停 {zt_count} 家 / 跌停 {dt_count} 家")

    # 涨停分位
    lp = data.get("limit_percentile")
    if lp:
        lines.append(f"  涨停家数 {lp['days']}日分位: {lp['percentile']}%（均值 {lp['avg']}，区间 {lp['min']}-{lp['max']}）")

    # 大盘
    if data.get("market"):
        lines.append(f"\n📈 【大盘概览】")
        lines.append("-" * 40)
        for idx in data["market"]:
            emoji = "🟢" if idx["change_pct"] > 0 else "🔴" if idx["change_pct"] < 0 else "⚪"
            lines.append(f"  {emoji} {idx['name']}: {idx['close']} ({idx['change_pct']:+.2f}%)")

    # 北向资金（V2.4 增强）
    nb = data.get("northbound", {})
    if nb:
        lines.append(f"\n🌊 【北向资金】")
        lines.append("-" * 40)
        net = nb.get("合计", {}).get("net", 0)
        emoji = "🟢" if net > 0 else "🔴"
        lines.append(f"  {emoji} 净流入: {format_yi(net)}")
        if nb.get("沪股通", {}).get("net"):
            lines.append(f"  沪股通净买入: {format_yi(nb['沪股通']['net'])}")
        if nb.get("深股通", {}).get("net"):
            lines.append(f"  深股通净买入: {format_yi(nb['深股通']['net'])}")

    # 北向十大成交股
    nb_top10 = data.get("northbound_top10", [])
    if nb_top10:
        lines.append(f"\n🏆 【北向十大成交股】")
        lines.append("-" * 40)
        for s in nb_top10[:10]:
            emoji = "🟢" if s["net_buy"] > 0 else "🔴"
            lines.append(f"  {emoji} {s['name']}({s['code']}) 净买入 {format_yi(s['net_buy'])}")

    # 北向行业流向
    nb_industry = data.get("northbound_industry", [])
    if nb_industry:
        lines.append(f"\n🏭 【北向行业流向 TOP10】")
        lines.append("-" * 40)
        for ind in nb_industry[:10]:
            emoji = "🟢" if ind["net_buy"] > 0 else "🔴"
            lines.append(f"  {emoji} {ind['industry']}: {format_yi(ind['net_buy'])}")

    # 主力资金
    mf = data.get("main_force", {})
    if mf:
        lines.append(f"\n💰 【主力资金】")
        lines.append("-" * 40)
        if "主力净流入" in mf:
            emoji = "🟢" if mf["主力净流入"] > 0 else "🔴"
            lines.append(f"  {emoji} 主力净流入: {format_yi(mf['主力净流入'])}")
        for key in ["超大单", "大单", "中单", "小单"]:
            if key in mf:
                emoji = "🟢" if mf[key] > 0 else "🔴"
                lines.append(f"  {emoji} {key}: {format_yi(mf[key])}")

    # 龙虎榜
    dt_list = data.get("dragon_tiger", [])
    if dt_list:
        lines.append(f"\n🐉 【龙虎榜】")
        lines.append("-" * 40)
        for item in dt_list[:10]:
            emoji = "🟢" if item["net_buy"] > 0 else "🔴"
            lines.append(f"  {emoji} {item['name']}({item['code']}) 净买 {format_yi(item['net_buy'])}  {item.get('reason', '')}")

    # 两融数据
    margin = data.get("margin", {})
    if margin:
        lines.append(f"\n📊 【两融余额】")
        lines.append("-" * 40)
        lines.append(f"  融资余额: {format_yi(margin.get('融资余额', 0))}")
        chg = margin.get("融资余额变化", 0)
        emoji = "🟢" if chg > 0 else "🔴" if chg < 0 else "⚪"
        lines.append(f"  {emoji} 变化: {format_yi(chg)}")

    # 板块强度评分
    sector_strength = data.get("sector_strength", [])
    if sector_strength:
        lines.append(f"\n💪 【板块强度评分 TOP10】")
        lines.append("-" * 40)
        for s in sector_strength[:10]:
            bar = "█" * (s["strength"] // 10) + "░" * (10 - s["strength"] // 10)
            emoji = "🟢" if s["change_pct"] > 0 else "🔴"
            lines.append(f"  {emoji} {s['name']}: {bar} {s['strength']}分  {s['change_pct']:+.2f}%")

    # 多周期轮动
    multi_rot = data.get("multi_rotation", {})
    if multi_rot:
        lines.append(f"\n🔄 【多周期板块轮动】")
        lines.append("-" * 40)
        for period, rot in multi_rot.items():
            if rot:
                lines.append(f"  📅 {rot['period']}轮动:")
                if rot.get("rising"):
                    top3 = ", ".join(f"{r['name']}({r['diff']:+.1f}%)" for r in rot["rising"][:3])
                    lines.append(f"    🔺 上升: {top3}")
                if rot.get("falling"):
                    bot3 = ", ".join(f"{r['name']}({r['diff']:+.1f}%)" for r in rot["falling"][:3])
                    lines.append(f"    🔻 下降: {bot3}")

    # 行业基本面
    fundamentals = data.get("sector_fundamentals", [])
    if fundamentals:
        lines.append(f"\n📐 【行业估值 TOP10】")
        lines.append("-" * 40)
        for f in fundamentals[:10]:
            pe_str = f"PE {f['pe']:.1f}" if f.get("pe") else "PE N/A"
            pb_str = f"PB {f['pb']:.1f}" if f.get("pb") else "PB N/A"
            emoji = "🟢" if f["change_pct"] > 0 else "🔴"
            lines.append(f"  {emoji} {f['name']}: {f['change_pct']:+.2f}%  {pe_str}  {pb_str}")

    # 趋势
    if data.get("trend"):
        lines.append(f"\n📉 【近5日趋势】")
        lines.append("-" * 40)
        for name, info in data["trend"].items():
            lines.append(f"  {info['direction']} {name}: {info['total_change_pct']:+.2f}% (5日)")
            if info.get("trend"):
                prices = " → ".join(str(t["close"]) for t in info["trend"])
                lines.append(f"    {prices}")

    # 板块轮动
    rotation = data.get("rotation")
    if rotation:
        lines.append(f"\n🔄 【板块轮动】")
        lines.append("-" * 40)
        if rotation.get("new"):
            lines.append(f"  🆕 新入热门: {', '.join(rotation['new'])}")
        if rotation.get("gone"):
            lines.append(f"  📤 退出热门: {', '.join(rotation['gone'])}")
        if rotation.get("hot"):
            for h in rotation["hot"]:
                arrow = "🔺" if h["change"] > 0 else "🔻"
                lines.append(f"  {arrow} {h['name']}: 今日 {h['today']:+.2f}% (变化 {h['change']:+.2f}%)")

    # 多平台热搜（V2.4 增强）
    if data.get("stock_hot"):
        lines.append(f"\n🔥 【A股热搜（多平台）】")
        lines.append("-" * 40)
        for item in data["stock_hot"][:15]:
            hot_str = format_hot(item.get("hot", 0))
            reason = item.get("match_reason", "")
            platform = item.get("platform_cn", item.get("source_platform", ""))
            sentiment = item.get("sentiment_emoji", "")
            multi = " 📡" if item.get("multi_platform") else ""
            lines.append(f"  {sentiment}#{item['keyword']}#  🔥{hot_str}  ({reason}) [{platform}]{multi}")

    # 涨停
    zt_dt = data.get("zt_dt", {})
    if zt_dt.get("涨停"):
        lines.append(f"\n🟢 【涨停板 TOP10】")
        lines.append("-" * 40)
        for item in zt_dt["涨停"][:10]:
            lines.append(f"  {item['name']}({item['code']}) {item['change_pct']:+.1f}%  {item.get('reason', '')}")

    if zt_dt.get("跌停"):
        lines.append(f"\n🔴 【跌停板 TOP5】")
        lines.append("-" * 40)
        for item in zt_dt["跌停"][:5]:
            lines.append(f"  {item['name']}({item['code']}) {item['change_pct']:+.1f}%")

    # 板块
    if data.get("sectors"):
        lines.append(f"\n📊 【热门板块 TOP10】")
        lines.append("-" * 40)
        for s in data["sectors"][:10]:
            emoji = "🟢" if s["change_pct"] > 0 else "🔴"
            lines.append(f"  {emoji} {s['name']}: {s['change_pct']:+.2f}%  领涨: {s.get('leader', '')}")

    # 自选股预警
    alerts = data.get("triggered_alerts", [])
    if alerts:
        lines.append(f"\n🚨 【自选股预警】")
        lines.append("-" * 40)
        for a in alerts:
            lines.append(f"  ⚠️  {a['code']} {a['type']} 触发阈值 {a['threshold']}")

    # 关联分析
    corr = data.get("correlation", {})
    if corr.get("insights"):
        lines.append(f"\n🔗 【热搜 vs 行情 关联分析】")
        lines.append("-" * 40)
        for insight in corr["insights"]:
            lines.append(f"  {insight}")

    # 历史对比
    snapshots = load_recent_snapshots(5)
    if len(snapshots) > 1:
        lines.append(f"\n📅 【历史数据对比】")
        lines.append("-" * 40)
        for snap in reversed(snapshots):
            zt_c = len(snap.get("zt_dt", {}).get("涨停", []))
            dt_c = len(snap.get("zt_dt", {}).get("跌停", []))
            sec_c = len(snap.get("sectors", []))
            nb_net = snap.get("northbound", {}).get("合计", {}).get("net", 0)
            nb_str = format_yi(nb_net) if nb_net else "N/A"
            lines.append(f"  📌 {snap['date']}: 涨停{zt_c}家 / 跌停{dt_c}家 / 板块{sec_c}个  北向: {nb_str}")

    # AKShare 统计
    ak_stats = ak_adapter.stats()
    if ak_stats["total_calls"] > 0:
        lines.append(f"\n⚙️  【系统状态】")
        lines.append("-" * 40)
        lines.append(f"  AKShare 调用: {ak_stats['total_calls']}次，成功率 {ak_stats['success_rate']}%")

    lines.append("")
    return "\n".join(lines)


def render_markdown(data, args):
    """Markdown 格式输出"""
    lines = []
    lines.append("# 📊 A股热搜分析报告 v2.5")
    lines.append(f"> ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if not is_trading_day():
        lines.append(f"> 🏖️  今日非交易日，数据为最近交易日 ({get_last_trading_date()})")
    lines.append("")

    # 恐慌贪婪指数
    fg = data.get("fear_greed", {})
    if fg:
        lines.append(f"## {fg.get('emoji', '⚪')} 恐慌贪婪指数: {fg.get('index', 50)} — {fg.get('level', '中性')}")
        lines.append("")

    stats = data.get("stats", {})
    if stats:
        lines.append("## 市场情绪")
        lines.append(f"| 上涨 | 下跌 | 平盘 | 涨跌比 |")
        lines.append(f"|------|------|------|--------|")
        lines.append(f"| {stats.get('up', 0)} | {stats.get('down', 0)} | {stats.get('flat', 0)} | {stats.get('up', 0)}:{stats.get('down', 0)} |")
        lines.append("")

    if data.get("market"):
        lines.append("## 大盘概览")
        lines.append("| 指数 | 收盘 | 涨跌幅 |")
        lines.append("|------|------|--------|")
        for idx in data["market"]:
            emoji = "🟢" if idx["change_pct"] > 0 else "🔴" if idx["change_pct"] < 0 else "⚪"
            lines.append(f"| {emoji} {idx['name']} | {idx['close']} | {idx['change_pct']:+.2f}% |")
        lines.append("")

    # 北向资金增强
    nb = data.get("northbound", {})
    if nb:
        lines.append("## 🌊 北向资金")
        net = nb.get("合计", {}).get("net", 0)
        lines.append(f"净流入: **{format_yi(net)}**")
        lines.append("")
    
    nb_top10 = data.get("northbound_top10", [])
    if nb_top10:
        lines.append("### 北向十大成交股")
        lines.append("| 股票 | 代码 | 净买入 |")
        lines.append("|------|------|--------|")
        for s in nb_top10[:10]:
            lines.append(f"| {s['name']} | {s['code']} | {format_yi(s['net_buy'])} |")
        lines.append("")

    # 主力资金
    mf = data.get("main_force", {})
    if mf:
        lines.append("## 💰 主力资金")
        for key in ["主力净流入", "超大单", "大单", "中单", "小单"]:
            if key in mf:
                lines.append(f"- {key}: {format_yi(mf[key])}")
        lines.append("")

    # 龙虎榜
    dt_list = data.get("dragon_tiger", [])
    if dt_list:
        lines.append("## 🐉 龙虎榜")
        for item in dt_list[:10]:
            lines.append(f"- {item['name']}({item['code']}) 净买 {format_yi(item['net_buy'])} {item.get('reason', '')}")
        lines.append("")

    if data.get("stock_hot"):
        lines.append("## 🔥 A股热搜（多平台）")
        for item in data["stock_hot"][:15]:
            platform = item.get("platform_cn", item.get("source_platform", ""))
            lines.append(f"- **#{item['keyword']}#** 🔥{format_hot(item.get('hot', 0))} ({item.get('match_reason', '')}) [{platform}]")
        lines.append("")

    zt_dt = data.get("zt_dt", {})
    if zt_dt.get("涨停"):
        lines.append("## 🟢 涨停板 TOP10")
        for item in zt_dt["涨停"][:10]:
            lines.append(f"- {item['name']}({item['code']}) {item['change_pct']:+.1f}% {item.get('reason', '')}")
        lines.append("")

    corr = data.get("correlation", {})
    if corr.get("insights"):
        lines.append("## 🔗 关联分析")
        for insight in corr["insights"]:
            lines.append(f"- {insight}")
        lines.append("")

    lines.append(f"\n---\n*Generated by A股分析 v{VERSION}*")
    return "\n".join(lines)


# ============================================================
# 主函数
# ============================================================
def collect_data(args):
    """并行收集所有数据"""
    data = {}
    watchlist = args.watchlist.split(",") if args.watchlist else None

    # V2.4: 多平台热搜
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        
        # 多平台热搜
        if not args.no_weibo:
            if args.platforms:
                platforms = args.platforms.split(",")
            else:
                platforms = None
            futures["multi_hot"] = executor.submit(fetch_all_hot_sources, platforms=platforms, proxy=args.proxy)
        
        # 行情数据
        if not args.no_market:
            futures["market"] = executor.submit(fetch_market_overview)
            futures["trend"] = executor.submit(fetch_market_trend)
            futures["zt_dt"] = executor.submit(fetch_zt_dt)
            futures["sectors"] = executor.submit(fetch_hot_sectors)
            futures["stats"] = executor.submit(SentimentAnalyzer().fetch_market_stats)
            
            # V2.4: 增强资金数据
            cap = CapitalAnalyzer()
            futures["northbound"] = executor.submit(cap.fetch_northbound_flow)
            futures["northbound_top10"] = executor.submit(cap.fetch_northbound_top10)
            futures["northbound_industry"] = executor.submit(cap.fetch_northbound_industry_flow)
            futures["main_force"] = executor.submit(cap.fetch_main_force_flow)
            futures["dragon_tiger"] = executor.submit(cap.fetch_dragon_tiger)
            
            # V2.4: 情绪指标
            sent = SentimentAnalyzer()
            futures["fear_greed"] = executor.submit(sent.fetch_fear_greed_index)
            futures["margin"] = executor.submit(sent.fetch_margin_trading)

            # V2.2: 板块强度评分 & 行业基本面
            sec_analyzer = SectorAnalyzer()
            futures["sector_strength"] = executor.submit(lambda: sec_analyzer.compute_sector_strength(data.get("sectors", []) or []))
            futures["sector_fundamentals"] = executor.submit(sec_analyzer.fetch_sector_fundamentals)
            futures["multi_rotation"] = executor.submit(sec_analyzer.multi_period_rotation)

        for name, future in futures.items():
            try:
                data[name] = future.result(timeout=30)
            except Exception as e:
                log(f"⚠️  {name} 数据获取超时: {e}")
                data[name] = {} if name != "multi_hot" else {}

    # 处理多平台热搜结果
    multi_hot = data.pop("multi_hot", {})
    if isinstance(multi_hot, dict):
        data["platform_status"] = {PLATFORM_SOURCES.get(k, {}).get("name", k): len(v) for k, v in multi_hot.items()}
        merged = merge_multi_platform_results(multi_hot)
        data["stock_hot"] = filter_stock_keywords(merged, watchlist=watchlist)
    else:
        data["stock_hot"] = []
        data["platform_status"] = {}

    # 关联分析
    if data.get("stock_hot") and data.get("zt_dt"):
        data["correlation"] = analyze_correlation(data["stock_hot"], data["zt_dt"], data.get("sectors", []))
    else:
        data["correlation"] = {}

    # 板块轮动
    if not args.no_market:
        data["rotation"] = analyze_sector_rotation()
        data["limit_percentile"] = SentimentAnalyzer().compute_limit_up_percentile()

    # 自选股预警
    if args.watchlist:
        wm = WatchlistManager()
        # 简化：用当前行情数据检查预警
        # data["triggered_alerts"] = wm.check_alerts(...)
        data["triggered_alerts"] = []

    # 保存快照
    if not args.no_market:
        save_snapshot(data)

    return data


def main():
    parser = argparse.ArgumentParser(
        description="A股热搜分析 v2.4 — 多平台热搜 + 资金分析 + 情绪指标",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # 输出格式
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--brief", action="store_true", help="精简模式：仅热搜 + 涨停")
    parser.add_argument("--trend", action="store_true", help="趋势模式：含大盘5日走势")
    parser.add_argument("--md", action="store_true", help="Markdown 格式输出")
    parser.add_argument("--html", action="store_true", help="交互式 HTML 报告")
    
    # 数据控制
    parser.add_argument("--no-weibo", action="store_true", help="跳过热搜数据")
    parser.add_argument("--no-market", action="store_true", help="跳过行情数据")
    parser.add_argument("--platforms", type=str, help="指定热搜平台（逗号分隔：weibo,eastmoney,xueqiu,douyin,zhihu）")
    parser.add_argument("--proxy", type=str, help="代理地址（用于微博等平台）")
    
    # 个股 & 自选股
    parser.add_argument("--stock", type=str, help="查询单只股票（代码）")
    parser.add_argument("--profile", type=str, help="个股多维画像（代码）")
    parser.add_argument("--watchlist", type=str, help="自选股过滤（逗号分隔）")
    parser.add_argument("--watchlist-file", type=str, help="从文件导入自选股")
    parser.add_argument("--export-watchlist", type=str, help="导出自选股到文件")

    # V2.2: 自动化
    parser.add_argument("--archive", action="store_true", help="归档本次报告")
    parser.add_argument("--push", action="store_true", help="推送到已配置的 Webhook")
    parser.add_argument("--schedule", type=str, help="添加定时任务（格式: 名称,时间,参数）")
    parser.add_argument("--list-schedules", action="store_true", help="列出自定义定时任务")
    parser.add_argument("--webhook", type=str, help="添加 Webhook（格式: 名称,URL,类型）")
    parser.add_argument("--list-archives", type=str, nargs="?", const="all", help="列出归档文件")

    # V2.2: 板块分析
    parser.add_argument("--sector-detail", type=str, help="板块内部分析（板块名称）")
    parser.add_argument("--subdivisions", type=str, help="概念细分查询（如 AI）")
    
    # 版本
    parser.add_argument("--version", action="version", version=f"A股分析 v{VERSION}")
    args = parser.parse_args()

    # 单股查询
    if args.stock:
        info = fetch_single_stock(args.stock)
        if info:
            if args.json:
                # V2.4: 增加资金流向
                cap = CapitalAnalyzer()
                fund = cap.fetch_single_stock_fund_flow(args.stock)
                info["fund_flow"] = fund
                print(json.dumps(info, ensure_ascii=False, indent=2))
            else:
                emoji = "🟢" if info["change_pct"] > 0 else "🔴" if info["change_pct"] < 0 else "⚪"
                print(f"\n{emoji} {info['name']} ({info['code']})")
                print(f"  最新价: {info['price']}  涨跌: {info['change_pct']:+.2f}% ({info['change_amt']:+.2f})")
                print(f"  今开: {info['open']}  最高: {info['high']}  最低: {info['low']}  昨收: {info['prev_close']}")
                print(f"  成交量: {info['volume']:.0f}  成交额: {info['turnover']:.0f}  换手率: {info.get('turnover_rate', 'N/A')}")
                if info.get("pe"):
                    print(f"  市盈率: {info['pe']}")
                # V2.4: 显示资金流向
                fund = CapitalAnalyzer().fetch_single_stock_fund_flow(args.stock)
                if fund:
                    print(f"  💰 主力净流入: {format_yi(fund.get('主力净流入', 0))}")
                    print(f"     超大单: {format_yi(fund.get('超大单净流入', 0))}  大单: {format_yi(fund.get('大单净流入', 0))}")
                    print(f"     中单: {format_yi(fund.get('中单净流入', 0))}  小单: {format_yi(fund.get('小单净流入', 0))}")
        else:
            print(f"❌ 未找到股票 {args.stock}")
        return

    # 自选股文件操作
    wm = WatchlistManager()
    if args.watchlist_file:
        if args.watchlist_file.endswith(".csv"):
            count = wm.import_from_csv(args.watchlist_file)
        else:
            count = wm.import_from_txt(args.watchlist_file)
        print(f"✅ 导入 {count} 只自选股")
        return
    if args.export_watchlist:
        count = wm.export_to_txt(args.export_watchlist)
        print(f"✅ 导出 {count} 只自选股到 {args.export_watchlist}")
        return

    # V2.2: 个股多维画像
    if args.profile:
        profiler = StockProfiler()
        profile = profiler.get_full_profile(args.profile)
        if args.json:
            print(json.dumps(profile, ensure_ascii=False, indent=2, default=str))
        else:
            b = profile.get("basic", {})
            emoji = "🟢" if b.get("change_pct", 0) > 0 else "🔴" if b.get("change_pct", 0) < 0 else "⚪"
            print(f"\n{emoji} 【{b.get('name', '')} ({args.profile}) 个股画像】")
            print("-" * 50)
            print(f"  最新价: {b.get('price', 0)}  涨跌: {b.get('change_pct', 0):+.2f}%  PE: {b.get('pe', 'N/A')}  PB: {b.get('pb', 'N/A')}")
            print(f"  总市值: {b.get('total_mv', 'N/A')}  流通市值: {b.get('circ_mv', 'N/A')}  换手率: {b.get('turnover_rate', 'N/A')}")
            tech = profile.get("technical", {})
            if tech:
                print(f"\n  📐 技术指标:")
                for k, v in tech.items():
                    if isinstance(v, dict):
                        print(f"    {k}: {v}")
                    else:
                        print(f"    {k}: {v}")
            cap = profile.get("capital", {})
            if cap:
                print(f"\n  💰 资金面:")
                for k, v in cap.items():
                    print(f"    {k}: {format_yi(v)}")
            anomaly = profile.get("anomaly")
            if anomaly:
                print(f"\n  ⚠️  异常检测:")
                for a in anomaly:
                    print(f"    [{a['severity']}] {a['type']}: {a['detail']}")
            news = profile.get("news", [])
            if news:
                print(f"\n  📰 最新消息:")
                for n in news[:5]:
                    print(f"    · {n['title']} ({n.get('source', '')})")
        return

    # V2.2: 板块内部分析
    if args.sector_detail:
        sec = SectorAnalyzer()
        result = sec.analyze_sector_internal(args.sector_detail)
        if result:
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"\n📊 【{args.sector_detail} 板块内部分析】")
                print("-" * 50)
                print(f"  总股票数: {result['total_stocks']}  平均涨跌: {result['avg_change']:+.2f}%")
                dist = result.get("distribution", {})
                print(f"  上涨: {dist.get('上涨', 0)}  下跌: {dist.get('下跌', 0)}  平盘: {dist.get('平盘', 0)}")
                if result.get("leaders"):
                    print(f"\n  🏆 龙头股:")
                    for s in result["leaders"]:
                        print(f"    {s['name']}({s['code']}) {s['change_pct']:+.2f}%  成交额 {s['volume']:.0f}")
                if result.get("laggards"):
                    print(f"\n  📉 掉队股:")
                    for s in result["laggards"]:
                        print(f"    {s['name']}({s['code']}) {s['change_pct']:+.2f}%")
        else:
            print(f"❌ 未找到板块 {args.sector_detail}")
        return

    # V2.2: 概念细分
    if args.subdivisions:
        sec = SectorAnalyzer()
        if args.subdivisions == "all":
            subs = sec.list_all_subdivisions()
            for concept, tracks in subs.items():
                print(f"  {concept}: {', '.join(tracks)}")
        else:
            tracks = sec.get_concept_subdivision(args.subdivisions)
            if tracks:
                print(f"  {args.subdivisions} 细分赛道: {', '.join(tracks)}")
            else:
                print(f"  未找到 {args.subdivisions} 的细分数据")
        return

    # V2.2: 定时任务管理
    am = AutomationManager()
    if args.schedule:
        parts = args.schedule.split(",")
        if len(parts) >= 2:
            sch = am.add_schedule(parts[0].strip(), parts[1].strip(), parts[2].strip() if len(parts) > 2 else "")
            print(f"✅ 定时任务已添加: {sch['name']} @ {sch['time']}")
        else:
            print("❌ 格式: 名称,时间,参数（如 '盘后简报,15:30,--brief'）")
        return
    if args.list_schedules:
        schedules = am.list_schedules()
        if schedules:
            print("📋 定时任务:")
            for s in schedules:
                status = "✅" if s.get("enabled") else "⏸️"
                print(f"  {status} {s['name']} @ {s['time']}  参数: {s.get('args', '')}")
        else:
            print("  暂无定时任务")
        return
    if args.webhook:
        parts = args.webhook.split(",")
        if len(parts) >= 2:
            wh = am.add_webhook(parts[0].strip(), parts[1].strip(), parts[2].strip() if len(parts) > 2 else "custom")
            print(f"✅ Webhook 已添加: {wh['name']} ({wh['type']})")
        else:
            print("❌ 格式: 名称,URL,类型（如 '钉钉群,https://oapi.dingtalk.com/...,dingtalk'）")
        return
    if args.list_archives:
        archives = am.list_archives(None if args.list_archives == "all" else args.list_archives)
        if archives:
            print("📁 归档文件:")
            for f in archives[:20]:
                print(f"  {f}")
        else:
            print("  暂无归档")
        return

    data = collect_data(args)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    elif args.html:
        html = generate_html_report(data)
        html_path = os.path.join(os.path.dirname(SCRIPT_DIR), ".cache", f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.html")
        os.makedirs(os.path.dirname(html_path), exist_ok=True)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ HTML 报告已生成: {html_path}")
    elif args.md:
        print(render_markdown(data, args))
    elif args.brief:
        brief_data = {"stock_hot": data.get("stock_hot", []), "zt_dt": data.get("zt_dt", {})}
        print(render_text(brief_data, args))
    else:
        print(render_text(data, args))

    # V2.2: 归档
    if args.archive:
        am = AutomationManager()
        report_text = render_text(data, args)
        path = am.archive_report(report_text, data)
        print(f"📁 报告已归档: {path}")

    # V2.2: 推送
    if args.push:
        am = AutomationManager()
        report_text = render_text(data, args)
        results = am.push_report(report_text)
        for r in results:
            status = "✅" if r["success"] else "❌"
            print(f"  {status} 推送到 {r['name']}")


if __name__ == "__main__":
    main()
