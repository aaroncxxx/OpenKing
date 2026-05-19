#!/usr/bin/env python3
"""
市场情绪指标模块 V2.4
- 恐慌贪婪指数
- 两融余额变化
- 涨跌停家数历史分位
- 涨跌比、涨跌家数
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import akshare as ak
    import warnings
    warnings.filterwarnings("ignore")
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False

from utils.common import log, CACHE_DIR, load_recent_snapshots
import json
from datetime import datetime


class SentimentAnalyzer:
    """市场情绪分析器"""
    
    def __init__(self):
        self.has_ak = HAS_AKSHARE
    
    def fetch_market_stats(self):
        """涨跌家数统计"""
        if not self.has_ak:
            return {}
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                total = len(df)
                up = len(df[df["涨跌幅"] > 0])
                down = len(df[df["涨跌幅"] < 0])
                flat = total - up - down
                return {
                    "total": total, "up": up, "down": down, "flat": flat,
                    "up_ratio": round(up / total * 100, 1) if total else 0,
                }
        except Exception:
            pass
        return {}
    
    def fetch_fear_greed_index(self):
        """
        恐慌贪婪指数（基于多维度综合计算）
        返回 0-100，0=极度恐慌，100=极度贪婪
        """
        if not self.has_ak:
            return {}
        
        scores = []
        details = {}
        
        # 1. 涨跌比
        try:
            stats = self.fetch_market_stats()
            if stats:
                ratio = stats.get("up_ratio", 50)
                score = min(100, max(0, ratio * 2))
                scores.append(score)
                details["涨跌比"] = {"value": f"{ratio}%", "score": round(score)}
        except Exception:
            pass
        
        # 2. 涨停/跌停比
        try:
            from datetime import datetime
            today = datetime.now().strftime("%Y%m%d")
            zt_df = ak.stock_zt_pool_em(date=today)
            dt_df = ak.stock_zt_pool_dtgc_em(date=today)
            zt_count = len(zt_df) if zt_df is not None else 0
            dt_count = len(dt_df) if dt_df is not None else 0
            if zt_count + dt_count > 0:
                zt_ratio = zt_count / (zt_count + dt_count) * 100
                scores.append(zt_ratio)
                details["涨跌停比"] = {"value": f"{zt_count}:{dt_count}", "score": round(zt_ratio)}
        except Exception:
            pass
        
        # 3. 北向资金方向
        try:
            df = ak.stock_hsgt_north_net_flow_in_em()
            if df is not None and not df.empty:
                last_val = float(df.iloc[-1].get("value", 0))
                score = min(100, max(0, 50 + last_val / 10))
                scores.append(score)
                details["北向资金"] = {"value": f"{last_val:.2f}亿", "score": round(score)}
        except Exception:
            pass
        
        # 4. 大盘涨跌
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            if df is not None and len(df) >= 2:
                close = float(df.iloc[-1]["close"])
                prev = float(df.iloc[-2]["close"])
                pct = (close - prev) / prev * 100
                score = min(100, max(0, 50 + pct * 10))
                scores.append(score)
                details["大盘涨跌"] = {"value": f"{pct:+.2f}%", "score": round(score)}
        except Exception:
            pass
        
        if not scores:
            return {"index": 50, "level": "中性", "emoji": "⚪", "details": {}}
        
        avg_score = sum(scores) / len(scores)
        if avg_score >= 80:
            level, emoji = "极度贪婪", "🔥"
        elif avg_score >= 60:
            level, emoji = "贪婪", "🟢"
        elif avg_score >= 40:
            level, emoji = "中性", "⚪"
        elif avg_score >= 20:
            level, emoji = "恐慌", "🔴"
        else:
            level, emoji = "极度恐慌", "💀"
        
        return {
            "index": round(avg_score),
            "level": level,
            "emoji": emoji,
            "details": details,
        }
    
    def fetch_margin_trading(self):
        """两融余额数据"""
        if not self.has_ak:
            return {}
        try:
            df = ak.stock_margin_sse(start_date="", end_date="")
            if df is not None and not df.empty:
                last = df.iloc[-1]
                prev = df.iloc[-2] if len(df) >= 2 else None
                balance = float(last.get("融资余额(元)", 0))
                change = 0
                if prev:
                    prev_balance = float(prev.get("融资余额(元)", 0))
                    change = balance - prev_balance
                return {
                    "融资余额": round(balance / 1e8, 2),
                    "融资余额变化": round(change / 1e8, 2),
                    "date": str(last.get("信用交易日期", "")),
                }
        except Exception as e:
            log(f"⚠️  两融数据获取失败: {e}")
        return {}
    
    def compute_limit_up_percentile(self, days=30):
        """
        涨停家数历史分位（过去N天）
        """
        snapshots = load_recent_snapshots(days)
        if len(snapshots) < 3:
            return None
        
        zt_counts = []
        for snap in snapshots:
            zt = len(snap.get("zt_dt", {}).get("涨停", []))
            zt_counts.append(zt)
        
        if not zt_counts:
            return None
        
        today_zt = zt_counts[-1]
        sorted_counts = sorted(zt_counts)
        rank = sorted(today_zt, key=lambda x: sorted_counts.index(x)) if today_zt in sorted_counts else len(sorted_counts)
        percentile = round(len([x for x in sorted_counts if x <= today_zt]) / len(sorted_counts) * 100)
        
        return {
            "today": today_zt,
            "percentile": percentile,
            "min": min(zt_counts),
            "max": max(zt_counts),
            "avg": round(sum(zt_counts) / len(zt_counts), 1),
            "days": len(zt_counts),
        }
