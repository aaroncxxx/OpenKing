#!/usr/bin/env python3
"""
热搜深度分析模块
- 热搜热度趋势（1h/3h/24h涨幅）
- 情绪倾向分析（正面/负面/中性）
- 关联事件提取
- 热搜历史回溯
"""

import json
import os
import re
from datetime import datetime, timedelta
from collections import Counter
from utils.common import log, CACHE_DIR

# 情绪词典
POSITIVE_WORDS = [
    "涨停", "暴涨", "利好", "反弹", "突破", "新高", "大涨", "飙升",
    "牛市", "翻倍", "增持", "回购", "分红", "增长", "盈利", "超预期",
    "领涨", "强势", "龙头", "爆发", "起飞", "狂飙",
]

NEGATIVE_WORDS = [
    "跌停", "暴跌", "利空", "崩盘", "破位", "新低", "大跌", "闪崩",
    "熊市", "腰斩", "减持", "爆雷", "亏损", "退市", "ST", "违规",
    "领跌", "弱势", "跳水", "割肉", "套牢", "踩踏",
]

# 事件关键词映射
EVENT_PATTERNS = {
    "AI芯片": ["AI", "芯片", "GPU", "算力", "英伟达", "寒武纪"],
    "新能源": ["光伏", "锂电", "储能", "新能源", "比亚迪"],
    "政策利好": ["政策", "国务院", "发改委", "央行", "降息", "降准"],
    "业绩公告": ["财报", "业绩", "年报", "季报", "中报", "净利润"],
    "IPO/融资": ["IPO", "上市", "融资", "增发", "配股"],
    "行业整合": ["并购", "重组", "收购", "合并"],
    "国际贸易": ["关税", "制裁", "出口", "进口", "贸易战"],
    "宏观经济": ["GDP", "CPI", "PMI", "社融", "M2"],
}


class HotSearchAnalyzer:
    """热搜深度分析器"""
    
    def __init__(self, cache_dir=None):
        self.cache_dir = cache_dir or CACHE_DIR
    
    def analyze_sentiment(self, keyword):
        """分析单条热搜的情绪倾向"""
        pos_count = sum(1 for w in POSITIVE_WORDS if w in keyword)
        neg_count = sum(1 for w in NEGATIVE_WORDS if w in keyword)
        if pos_count > neg_count:
            return "positive", "🟢"
        elif neg_count > pos_count:
            return "negative", "🔴"
        return "neutral", "⚪"
    
    def extract_events(self, keyword):
        """提取热搜关联事件"""
        events = []
        for event_name, patterns in EVENT_PATTERNS.items():
            if any(p in keyword for p in patterns):
                events.append(event_name)
        return events if events else ["其他"]
    
    def get_hot_trend(self, keyword, hours_list=None):
        """
        计算热搜热度趋势（从历史快照中提取）
        hours_list: [1, 3, 24] 小时
        """
        if hours_list is None:
            hours_list = [1, 3, 24]
        
        # 从缓存中加载历史热搜数据
        snapshots = self._load_hot_snapshots()
        if not snapshots:
            return None
        
        trend = {}
        for hours in hours_list:
            target_time = datetime.now() - timedelta(hours=hours)
            closest = self._find_closest_snapshot(snapshots, target_time)
            if closest:
                hot_val = self._find_keyword_hot(closest, keyword)
                trend[f"{hours}h"] = hot_val
        
        # 当前值
        if snapshots:
            current = snapshots[-1]
            current_hot = self._find_keyword_hot(current, keyword)
            trend["current"] = current_hot
            
            # 计算涨幅
            for hours in hours_list:
                key = f"{hours}h"
                if key in trend and trend[key] and trend[key] > 0:
                    change = (current_hot - trend[key]) / trend[key] * 100
                    trend[f"{key}_change"] = round(change, 1)
        
        return trend
    
    def get_stock_hot_history(self, keyword, days=7):
        """
        查询单只股票/关键词过去N天的热搜次数、热度峰值
        """
        history = {
            "keyword": keyword,
            "days": days,
            "total_mentions": 0,
            "peak_hot": 0,
            "peak_date": "",
            "daily_data": [],
        }
        
        today = datetime.now()
        for i in range(days):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            path = os.path.join(self.cache_dir, f"{date}.json")
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        snap = json.load(f)
                    hot_items = snap.get("hotsearch", [])
                    found = False
                    for item in hot_items:
                        if keyword in item.get("keyword", ""):
                            hot = item.get("hot", 0)
                            history["total_mentions"] += 1
                            if hot > history["peak_hot"]:
                                history["peak_hot"] = hot
                                history["peak_date"] = date
                            history["daily_data"].append({
                                "date": date,
                                "hot": hot,
                                "rank": item.get("rank", 0),
                            })
                            found = True
                            break
                    if not found:
                        history["daily_data"].append({"date": date, "hot": 0, "rank": 0})
                except Exception:
                    history["daily_data"].append({"date": date, "hot": 0, "rank": 0})
            else:
                history["daily_data"].append({"date": date, "hot": 0, "rank": 0})
        
        return history
    
    def batch_sentiment_analysis(self, hot_list):
        """批量情绪分析"""
        results = {"positive": [], "negative": [], "neutral": []}
        for item in hot_list:
            sentiment, emoji = self.analyze_sentiment(item["keyword"])
            item["sentiment"] = sentiment
            item["sentiment_emoji"] = emoji
            item["events"] = self.extract_events(item["keyword"])
            results[sentiment].append(item)
        return results
    
    def _load_hot_snapshots(self):
        """加载历史热搜快照"""
        snapshots = []
        if not os.path.exists(self.cache_dir):
            return snapshots
        for fname in sorted(os.listdir(self.cache_dir)):
            if fname.endswith(".json"):
                path = os.path.join(self.cache_dir, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "hotsearch" in data:
                        snapshots.append(data)
                except Exception:
                    pass
        return snapshots
    
    def _find_closest_snapshot(self, snapshots, target_time):
        """找到最接近目标时间的快照"""
        closest = None
        min_diff = float("inf")
        for snap in snapshots:
            try:
                snap_time = datetime.strptime(snap["date"], "%Y-%m-%d")
                diff = abs((snap_time - target_time).total_seconds())
                if diff < min_diff:
                    min_diff = diff
                    closest = snap
            except Exception:
                pass
        return closest
    
    def _find_keyword_hot(self, snapshot, keyword):
        """在快照中查找关键词的热度值"""
        for item in snapshot.get("hotsearch", []):
            if keyword in item.get("keyword", ""):
                return item.get("hot", 0)
        return 0
