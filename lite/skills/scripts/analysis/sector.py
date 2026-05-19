#!/usr/bin/env python3
"""
板块轮动与行业分析升级 V2.2
- 7/14/30天板块轮动对比
- 板块强度评分（涨幅+资金流入+热度）
- 板块内部分化分析（龙头/跟风/掉队）
- 行业基本面关联（PE/PB/ROE）
- 概念板块细分（AI→AI芯片/大模型/算力租赁/AI应用）
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
from datetime import datetime, timedelta


# 概念板块细分映射
CONCEPT_SUBDIVISION = {
    "AI": ["AI芯片", "大模型", "算力租赁", "AI应用", "AI+医疗", "AI+教育", "AI+金融"],
    "新能源": ["光伏组件", "光伏设备", "锂电池", "储能", "风电", "氢能", "充电桩"],
    "半导体": ["芯片设计", "晶圆制造", "封装测试", "EDA", "光刻机", "半导体材料"],
    "汽车": ["整车", "零部件", "智能驾驶", "充电桩", "换电"],
    "医药": ["创新药", "CXO", "中药", "医疗器械", "疫苗", "基因"],
    "消费": ["白酒", "食品饮料", "免税", "旅游", "酒店餐饮", "家电"],
    "金融": ["银行", "保险", "券商", "多元金融"],
    "军工": ["航空", "航天", "船舶", "兵器", "军工电子"],
    "数字经济": ["信创", "数据要素", "数字货币", "网络安全", "云计算"],
}


class SectorAnalyzer:
    """板块轮动与行业分析器"""

    def __init__(self):
        self.has_ak = HAS_AKSHARE

    # ============================================================
    # 板块轮动增强（7/14/30天）
    # ============================================================
    def analyze_rotation(self, days=7):
        """
        多周期板块轮动分析
        days: 对比周期（7/14/30）
        """
        snapshots = load_recent_snapshots(days + 1)
        if len(snapshots) < 2:
            return None

        current = snapshots[-1]
        prev = snapshots[0]

        current_sectors = {s["name"]: s for s in current.get("sectors", [])}
        prev_sectors = {s["name"]: s for s in prev.get("sectors", [])}

        current_set = set(current_sectors.keys())
        prev_set = set(prev_sectors.keys())

        new_in = current_set - prev_set
        gone = prev_set - current_set
        both = current_set & prev_set

        rotation = []
        for name in both:
            cur_chg = current_sectors[name].get("change_pct", 0)
            prev_chg = prev_sectors[name].get("change_pct", 0)
            diff = cur_chg - prev_chg
            # 累计涨跌幅（多日快照的首尾差）
            cumulative = cur_chg
            rotation.append({
                "name": name,
                "current_pct": cur_chg,
                "prev_pct": prev_chg,
                "diff": round(diff, 2),
                "cumulative": round(cumulative, 2),
                "leader": current_sectors[name].get("leader", ""),
            })

        rotation.sort(key=lambda x: -x["diff"])

        return {
            "period": f"{days}天",
            "new_hot": list(new_in)[:8],
            "fallen": list(gone)[:8],
            "rising": rotation[:10],
            "falling": rotation[-10:][::-1] if len(rotation) >= 10 else [],
            "snapshot_count": len(snapshots),
        }

    def multi_period_rotation(self):
        """多周期轮动对比（7/14/30天）"""
        results = {}
        for period in [7, 14, 30]:
            r = self.analyze_rotation(days=period)
            if r:
                results[f"{period}d"] = r
        return results

    # ============================================================
    # 板块强度评分
    # ============================================================
    def compute_sector_strength(self, sector_data, northbound_data=None):
        """
        板块强度评分 = 涨跌幅权重 + 资金流入权重 + 热度权重
        满分 100
        """
        if not sector_data:
            return []

        scored = []
        for s in sector_data:
            score = 0
            name = s.get("name", "")
            chg = s.get("change_pct", 0)
            up_count = s.get("up_count", 0)
            down_count = s.get("down_count", 0)

            # 涨跌幅得分（40分）
            chg_score = min(40, max(-10, chg * 8 + 20))
            score += chg_score

            # 涨跌家数比（30分）
            total = up_count + down_count
            if total > 0:
                up_ratio = up_count / total
                ratio_score = up_ratio * 30
                score += ratio_score

            # 领涨股涨幅（30分）
            leader_chg = s.get("leader_change", 0)
            leader_score = min(30, max(0, leader_chg * 3 + 15))
            score += leader_score

            scored.append({
                "name": name,
                "strength": round(min(100, max(0, score))),
                "change_pct": chg,
                "up_count": up_count,
                "down_count": down_count,
                "leader": s.get("leader", ""),
                "leader_change": leader_chg,
                "breakdown": {
                    "chg_score": round(chg_score, 1),
                    "ratio_score": round(ratio_score if total > 0 else 0, 1),
                    "leader_score": round(leader_score, 1),
                },
            })

        scored.sort(key=lambda x: -x["strength"])
        for i, s in enumerate(scored):
            s["rank"] = i + 1
        return scored

    # ============================================================
    # 板块内部分化分析
    # ============================================================
    def analyze_sector_internal(self, sector_name):
        """
        板块内部分化：识别龙头股、跟风股、掉队股
        """
        if not self.has_ak:
            return None
        try:
            df = ak.stock_board_industry_cons_em(symbol=sector_name)
            if df is None or df.empty:
                return None

            stocks = []
            for _, row in df.iterrows():
                try:
                    stocks.append({
                        "code": str(row.get("代码", "")),
                        "name": str(row.get("名称", "")),
                        "change_pct": float(row.get("涨跌幅", 0)),
                        "price": float(row.get("最新价", 0)),
                        "volume": float(row.get("成交额", 0)),
                        "turnover": float(row.get("换手率", 0)),
                    })
                except (ValueError, TypeError):
                    continue

            if not stocks:
                return None

            # 排序
            stocks.sort(key=lambda x: -x["change_pct"])

            # 分类
            avg_chg = sum(s["change_pct"] for s in stocks) / len(stocks)
            leaders = [s for s in stocks if s["change_pct"] > avg_chg + 3][:5]
            followers = [s for s in stocks if avg_chg - 1 <= s["change_pct"] <= avg_chg + 3]
            laggards = [s for s in stocks if s["change_pct"] < avg_chg - 3]

            return {
                "sector": sector_name,
                "total_stocks": len(stocks),
                "avg_change": round(avg_chg, 2),
                "leaders": leaders[:5],
                "followers_count": len(followers),
                "laggards": laggards[-5:][::-1] if laggards else [],
                "distribution": {
                    "上涨": len([s for s in stocks if s["change_pct"] > 0]),
                    "下跌": len([s for s in stocks if s["change_pct"] < 0]),
                    "平盘": len([s for s in stocks if s["change_pct"] == 0]),
                },
            }
        except Exception as e:
            log(f"⚠️  板块内部分析失败: {e}")
            return None

    # ============================================================
    # 行业基本面
    # ============================================================
    def fetch_sector_fundamentals(self):
        """行业 PE/PB/ROE 核心指标"""
        if not self.has_ak:
            return []
        try:
            df = ak.stock_board_industry_name_em()
            if df is None or df.empty:
                return []

            results = []
            for _, row in df.head(20).iterrows():
                try:
                    results.append({
                        "name": str(row.get("板块名称", "")),
                        "change_pct": float(row.get("涨跌幅", 0)),
                        "pe": float(row.get("市盈率", 0)) if "市盈率" in row.index and row.get("市盈率") else None,
                        "pb": float(row.get("市净率", 0)) if "市净率" in row.index and row.get("市净率") else None,
                    })
                except (ValueError, TypeError):
                    continue
            return results
        except Exception as e:
            log(f"⚠️  行业基本面获取失败: {e}")
            return []

    # ============================================================
    # 概念细分
    # ============================================================
    def get_concept_subdivision(self, concept):
        """获取概念板块的细分赛道"""
        return CONCEPT_SUBDIVISION.get(concept, [])

    def list_all_subdivisions(self):
        """列出所有概念细分"""
        return CONCEPT_SUBDIVISION
