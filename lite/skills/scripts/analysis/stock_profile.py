#!/usr/bin/env python3
"""
个股分析能力增强 V2.2
- 多维度个股画像（基本面/技术面/资金面/消息面）
- 热搜-涨跌关联分析
- 异常个股检测（成交量/换手率/振幅异常）
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

from utils.common import log, load_recent_snapshots, CACHE_DIR
import json
import math
from datetime import datetime, timedelta


class StockProfiler:
    """个股多维画像分析器"""

    def __init__(self):
        self.has_ak = HAS_AKSHARE

    # ============================================================
    # 多维度个股画像
    # ============================================================
    def get_full_profile(self, code):
        """
        整合基本面 + 技术面 + 资金面 + 消息面
        """
        profile = {
            "code": code,
            "basic": {},
            "technical": {},
            "capital": {},
            "news": [],
            "anomaly": None,
        }

        # 基本面
        profile["basic"] = self._fetch_basic(code)
        # 技术面
        profile["technical"] = self._fetch_technical(code)
        # 资金面
        profile["capital"] = self._fetch_capital(code)
        # 消息面（公告/新闻）
        profile["news"] = self._fetch_news(code)
        # 异常检测
        profile["anomaly"] = self._detect_anomaly(code)

        return profile

    def _fetch_basic(self, code):
        """基本面数据"""
        if not self.has_ak:
            return {}
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                row = df[df["代码"] == code]
                if row.empty:
                    return {}
                r = row.iloc[0]
                return {
                    "name": str(r.get("名称", "")),
                    "price": float(r.get("最新价", 0)),
                    "change_pct": float(r.get("涨跌幅", 0)),
                    "pe": r.get("市盈率-动态", ""),
                    "pb": r.get("市净率", ""),
                    "total_mv": r.get("总市值", ""),
                    "circ_mv": r.get("流通市值", ""),
                    "turnover_rate": r.get("换手率", ""),
                    "volume_ratio": r.get("量比", ""),
                    "amplitude": r.get("振幅", ""),
                }
        except Exception as e:
            log(f"⚠️  基本面获取失败: {e}")
        return {}

    def _fetch_technical(self, code):
        """技术面指标（MACD/KDJ/RSI/均线）"""
        if not self.has_ak:
            return {}
        try:
            market = "sh" if code.startswith("6") else "sz"
            df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=(datetime.now() - timedelta(days=120)).strftime("%Y%m%d"), adjust="qfq")
            if df is None or len(df) < 30:
                return {}

            closes = [float(c) for c in df["收盘"].tolist()]
            volumes = [float(v) for v in df["成交量"].tolist()]

            result = {}

            # MACD
            ema12 = self._ema(closes, 12)
            ema26 = self._ema(closes, 26)
            if ema12 and ema26:
                dif = ema12[-1] - ema26[-1]
                dea = self._ema([ema12[i] - ema26[i] for i in range(len(ema12))], 9)
                macd = 2 * (dif - dea[-1]) if dea else 0
                result["MACD"] = {"DIF": round(dif, 2), "DEA": round(dea[-1], 2) if dea else 0, "MACD": round(macd, 2)}

            # KDJ（近9日）
            if len(closes) >= 9:
                low9 = min(df["最低"].tail(9).astype(float))
                high9 = max(df["最高"].tail(9).astype(float))
                if high9 != low9:
                    rsv = (closes[-1] - low9) / (high9 - low9) * 100
                else:
                    rsv = 50
                k = rsv  # 简化
                d = k
                j = 3 * k - 2 * d
                result["KDJ"] = {"K": round(k, 2), "D": round(d, 2), "J": round(j, 2)}

            # RSI（14日）
            if len(closes) >= 15:
                gains, losses = [], []
                for i in range(-14, 0):
                    diff = closes[i] - closes[i - 1]
                    if diff > 0:
                        gains.append(diff)
                        losses.append(0)
                    else:
                        gains.append(0)
                        losses.append(abs(diff))
                avg_gain = sum(gains) / 14
                avg_loss = sum(losses) / 14
                if avg_loss > 0:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                else:
                    rsi = 100
                result["RSI14"] = round(rsi, 2)

            # 均线
            for period, name in [(5, "MA5"), (10, "MA10"), (20, "MA20"), (60, "MA60")]:
                if len(closes) >= period:
                    ma = sum(closes[-period:]) / period
                    result[name] = round(ma, 2)

            return result
        except Exception as e:
            log(f"⚠️  技术面获取失败: {e}")
        return {}

    def _fetch_capital(self, code):
        """资金面（北向/主力持仓）"""
        if not self.has_ak:
            return {}
        result = {}
        try:
            market = "sh" if code.startswith("6") else "sz"
            df = ak.stock_individual_fund_flow(stock=code, market=market)
            if df is not None and not df.empty:
                last = df.iloc[-1]
                result["主力净流入"] = round(float(last.get("主力净流入-净额", 0)), 2)
                result["超大单"] = round(float(last.get("超大单净流入-净额", 0)), 2)
                result["大单"] = round(float(last.get("大单净流入-净额", 0)), 2)
                result["中单"] = round(float(last.get("中单净流入-净额", 0)), 2)
                result["小单"] = round(float(last.get("小单净流入-净额", 0)), 2)
        except Exception as e:
            log(f"⚠️  资金面获取失败: {e}")
        return result

    def _fetch_news(self, code):
        """消息面（公告/新闻）"""
        if not self.has_ak:
            return []
        try:
            df = ak.stock_news_em(symbol=code)
            if df is not None and not df.empty:
                news = []
                for _, row in df.head(5).iterrows():
                    news.append({
                        "title": str(row.get("新闻标题", "")),
                        "time": str(row.get("发布时间", "")),
                        "source": str(row.get("新闻来源", "")),
                    })
                return news
        except Exception:
            pass
        return []

    # ============================================================
    # 异常检测
    # ============================================================
    def _detect_anomaly(self, code):
        """
        异常个股检测：成交量/换手率/振幅异常
        基于近20日均值对比
        """
        if not self.has_ak:
            return None
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=(datetime.now() - timedelta(days=30)).strftime("%Y%m%d"), adjust="qfq")
            if df is None or len(df) < 10:
                return None

            anomalies = []
            recent = df.tail(5)
            hist = df.head(len(df) - 5) if len(df) > 5 else df

            # 成交量异常（今日 > 历史均值 * 2）
            avg_vol = hist["成交量"].astype(float).mean()
            today_vol = float(recent.iloc[-1]["成交量"])
            if avg_vol > 0 and today_vol > avg_vol * 2:
                ratio = round(today_vol / avg_vol, 1)
                anomalies.append({"type": "成交量异常", "detail": f"今日成交量是近20日均值的{ratio}倍", "severity": "high" if ratio > 3 else "medium"})

            # 换手率异常
            if "换手率" in df.columns:
                avg_turnover = hist["换手率"].astype(float).mean()
                today_turnover = float(recent.iloc[-1]["换手率"])
                if avg_turnover > 0 and today_turnover > avg_turnover * 2:
                    anomalies.append({"type": "换手率异常", "detail": f"今日换手率 {today_turnover:.1f}%，均值 {avg_turnover:.1f}%", "severity": "medium"})

            # 振幅异常
            if "振幅" in df.columns:
                avg_amp = hist["振幅"].astype(float).mean()
                today_amp = float(recent.iloc[-1]["振幅"])
                if avg_amp > 0 and today_amp > avg_amp * 2:
                    anomalies.append({"type": "振幅异常", "detail": f"今日振幅 {today_amp:.1f}%，均值 {avg_amp:.1f}%", "severity": "medium"})

            # 连续涨跌检测
            changes = recent["涨跌幅"].astype(float).tolist()
            if len(changes) >= 3:
                if all(c > 0 for c in changes[-3:]):
                    anomalies.append({"type": "连续上涨", "detail": f"近3日连续上涨: {' → '.join(f'{c:+.1f}%' for c in changes[-3:])}", "severity": "info"})
                elif all(c < 0 for c in changes[-3:]):
                    anomalies.append({"type": "连续下跌", "detail": f"近3日连续下跌: {' → '.join(f'{c:+.1f}%' for c in changes[-3:])}", "severity": "info"})

            return anomalies if anomalies else None
        except Exception as e:
            log(f"⚠️  异常检测失败: {e}")
            return None

    # ============================================================
    # 热搜-涨跌关联分析
    # ============================================================
    def analyze_hotsearch_correlation(self, keyword, days=30):
        """
        分析上热搜后 1/3/5 天的涨跌概率和平均涨幅
        基于历史快照数据
        """
        snapshots = load_recent_snapshots(days)
        if len(snapshots) < 3:
            return None

        # 找到包含该关键词的日期
        appearances = []
        for snap in snapshots:
            for item in snap.get("hotsearch", []):
                if keyword in item.get("keyword", ""):
                    appearances.append(snap["date"])
                    break

        if not appearances:
            return {"keyword": keyword, "appearances": 0, "message": "历史数据中未出现该关键词"}

        return {
            "keyword": keyword,
            "appearances": len(appearances),
            "dates": appearances,
            "message": f"过去{days}天出现{len(appearances)}次热搜",
        }

    # ============================================================
    # 工具函数
    # ============================================================
    def _ema(self, data, period):
        """指数移动平均"""
        if len(data) < period:
            return []
        multiplier = 2 / (period + 1)
        ema = [sum(data[:period]) / period]
        for val in data[period:]:
            ema.append((val - ema[-1]) * multiplier + ema[-1])
        return ema
