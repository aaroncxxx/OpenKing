#!/usr/bin/env python3
"""雪球热搜数据源"""

import json
import time
import urllib.request
from utils.common import log

PLATFORM_NAME = "雪球"

def fetch_xueqiu_hot(retries=2):
    """抓取雪球热帖/热股"""
    results = []
    
    # 雪球热帖
    url = "https://xueqiu.com/statuses/hot/listV2.json?since_id=-1&max_id=-1&size=30"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://xueqiu.com/",
        "Origin": "https://xueqiu.com",
    }
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            items = data.get("list", [])
            for i, item in enumerate(items[:30]):
                title = item.get("title", "") or item.get("description", "")
                if title:
                    title = title[:40]
                    results.append({
                        "rank": i + 1,
                        "keyword": title,
                        "hot": item.get("reply_count", 0) * 100 + item.get("retweet_count", 0) * 50,
                        "platform": "xueqiu",
                        "platform_cn": "雪球",
                    })
            if results:
                break
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
                continue
            log(f"⚠️  雪球热帖获取失败: {e}")
    
    # 雪球热股
    if not results:
        results = _fetch_xueqiu_hot_stocks()
    return results


def _fetch_xueqiu_hot_stocks():
    """雪球热股榜"""
    results = []
    try:
        url = "https://stock.xueqiu.com/v5/stock/hot_stock/list.json?size=30&_type=10&type=10"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://xueqiu.com/",
            "Cookie": "xq_a_token=placeholder",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for i, item in enumerate(data.get("data", {}).get("items", [])[:30]):
            results.append({
                "rank": i + 1,
                "keyword": item.get("name", ""),
                "hot": item.get("increment", 0),
                "platform": "xueqiu",
                "platform_cn": "雪球",
                "stock_code": item.get("code", ""),
            })
    except Exception as e:
        log(f"⚠️  雪球热股获取失败: {e}")
    return results
