#!/usr/bin/env python3
"""多平台热搜聚合 + A股关键词筛选 + 黑名单过滤"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.common import log
from .weibo import fetch_weibo_hot
from .eastmoney_guba import fetch_eastmoney_hot
from .xueqiu import fetch_xueqiu_hot
from .douyin import fetch_douyin_hot
from .zhihu import fetch_zhihu_hot

# ============================================================
# 关键词库
# ============================================================
SECTOR_KEYWORDS = [
    "AI", "人工智能", "芯片", "半导体", "算力", "光刻", "封装", "存储",
    "机器人", "具身智能", "自动驾驶", "智能驾驶", "车联网",
    "5G", "6G", "通信", "光纤", "光模块", "量子",
    "云计算", "大数据", "区块链", "元宇宙", "AR", "VR",
    "软件", "信创", "国产替代", "操作系统", "数据库",
    "新能源", "光伏", "风电", "储能", "锂电", "钠电", "氢能", "燃料电池",
    "充电桩", "特高压", "智能电网",
    "白酒", "食品", "医药", "医疗", "中药", "生物", "疫苗",
    "消费", "免税", "旅游", "酒店", "餐饮",
    "银行", "保险", "券商", "地产", "房地产", "基建", "水泥", "钢铁",
    "军工", "航空", "航天", "船舶", "汽车", "零部件",
    "有色", "稀土", "黄金", "铜", "铝", "煤炭", "石油",
    "农业", "种业", "养殖", "猪肉", "鸡肉",
    "传媒", "游戏", "影视", "短剧", "网红", "直播",
    "CPO", "光模块", "HBM", "先进封装", "固态电池",
    "低空经济", "卫星互联网", "脑机接口", "合成生物",
]

EXACT_KEYWORDS = [
    "A股", "大A", "股市", "股票", "涨停", "跌停", "牛市", "熊市",
    "基金", "证券", "券商", "上证", "深证", "创业板", "科创板",
    "涨停板", "跌停板", "打板", "龙头", "妖股",
    "利好", "利空", "暴跌", "暴涨", "反弹", "回调",
    "北向资金", "主力", "游资", "散户",
    "融资融券", "两融", "期权", "期货",
    "大盘", "行情", "板块", "概念", "题材",
    "IPO", "增发", "减持", "回购", "分红",
]

# 黑名单：过滤掉过于泛化的关键词
BLACKLIST_KEYWORDS = [
    "股市",  # 太泛
    "股票",  # 太泛
    "A股",   # 单独出现太泛，需要组合
]

# ============================================================
# 平台数据源注册
# ============================================================
PLATFORM_SOURCES = {
    "weibo": {"fetch": fetch_weibo_hot, "name": "微博", "priority": 1},
    "eastmoney": {"fetch": fetch_eastmoney_hot, "name": "东方财富股吧", "priority": 2},
    "xueqiu": {"fetch": fetch_xueqiu_hot, "name": "雪球", "priority": 3},
    "douyin": {"fetch": fetch_douyin_hot, "name": "抖音", "priority": 4},
    "zhihu": {"fetch": fetch_zhihu_hot, "name": "知乎", "priority": 5},
}


def fetch_all_hot_sources(platforms=None, proxy=None):
    """
    并行抓取多个平台热搜
    platforms: 指定平台列表，如 ["weibo", "xueqiu"]，None=全部
    proxy: 代理地址（目前仅微博支持）
    """
    if platforms is None:
        platforms = list(PLATFORM_SOURCES.keys())
    
    all_results = {}
    with ThreadPoolExecutor(max_workers=len(platforms)) as executor:
        futures = {}
        for pf in platforms:
            if pf not in PLATFORM_SOURCES:
                log(f"⚠️  未知平台: {pf}")
                continue
            source = PLATFORM_SOURCES[pf]
            if pf == "weibo" and proxy:
                futures[pf] = executor.submit(source["fetch"], proxy=proxy)
            else:
                futures[pf] = executor.submit(source["fetch"])
        
        for name, future in futures.items():
            try:
                result = future.result(timeout=30)
                all_results[name] = result
                log(f"  ✓ {PLATFORM_SOURCES[name]['name']}: {len(result)} 条")
            except Exception as e:
                log(f"  ✗ {PLATFORM_SOURCES[name]['name']}: {e}")
                all_results[name] = []
    
    return all_results


def filter_stock_keywords(hot_list, watchlist=None, blacklist=None, match_mode="both"):
    """
    A股关键词筛选
    match_mode: "exact"=精确, "fuzzy"=模糊, "both"=组合
    blacklist: 额外黑名单关键词列表
    """
    if blacklist is None:
        blacklist = BLACKLIST_KEYWORDS
    
    stock_related = []
    seen = set()
    
    for item in hot_list:
        kw = item["keyword"]
        if kw in seen:
            continue
        seen.add(kw)
        
        # 黑名单过滤
        skip = False
        for bl in blacklist:
            if bl == kw:
                skip = True
                break
        if skip:
            continue
        
        matched = False
        
        # 精确匹配
        if match_mode in ("exact", "both"):
            for ek in EXACT_KEYWORDS:
                if ek in kw:
                    item["match_reason"] = f"精确「{ek}」"
                    item["match_type"] = "exact"
                    stock_related.append(item)
                    matched = True
                    break
        
        # 模糊匹配（板块关键词）
        if not matched and match_mode in ("fuzzy", "both"):
            for sector in SECTOR_KEYWORDS:
                if sector in kw and len(kw) <= 20:
                    item["match_reason"] = f"板块「{sector}」"
                    item["match_type"] = "fuzzy"
                    stock_related.append(item)
                    matched = True
                    break
        
        # 次级模糊匹配
        if not matched and match_mode in ("fuzzy", "both"):
            if any(ch in kw for ch in ["股", "涨", "跌"]) and len(kw) <= 6:
                item["match_reason"] = "模糊匹配"
                item["match_type"] = "fuzzy"
                stock_related.append(item)
    
    # 自选股过滤
    if watchlist:
        stock_related = [i for i in stock_related if any(w in i["keyword"] for w in watchlist)]
    
    return stock_related


def merge_multi_platform_results(all_results):
    """合并多平台结果，按热度排序，标注来源"""
    merged = []
    for platform, items in all_results.items():
        for item in items:
            item["source_platform"] = item.get("platform_cn", platform)
            merged.append(item)
    
    # 去重（相同关键词合并，保留最高热度）
    dedup = {}
    for item in merged:
        kw = item["keyword"]
        if kw in dedup:
            if item.get("hot", 0) > dedup[kw].get("hot", 0):
                dedup[kw] = item
            # 记录多平台出现
            dedup[kw]["multi_platform"] = True
        else:
            dedup[kw] = item
    
    result = list(dedup.values())
    result.sort(key=lambda x: int(x.get("hot", 0)) if isinstance(x.get("hot"), (int, float, str)) and str(x.get("hot", 0)).isdigit() else 0, reverse=True)
    for i, item in enumerate(result):
        item["rank"] = i + 1
    return result
