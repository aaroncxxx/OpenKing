#!/usr/bin/env python3
"""抖音热搜数据源"""

import json
import time
import urllib.request
from utils.common import log

PLATFORM_NAME = "抖音"

def fetch_douyin_hot(retries=2):
    """抓取抖音热搜榜（A股相关过滤）"""
    results = []
    url = "https://www.douyin.com/aweme/v1/web/hot/search/list/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.douyin.com/",
    }
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            items = data.get("data", {}).get("word_list", data.get("word_list", []))
            for i, item in enumerate(items[:50]):
                word = item.get("word", "")
                hot_value = item.get("hot_value", item.get("event_time", 0))
                if word:
                    results.append({
                        "rank": i + 1,
                        "keyword": word,
                        "hot": hot_value,
                        "platform": "douyin",
                        "platform_cn": "抖音",
                    })
            if results:
                break
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
                continue
            log(f"⚠️  抖音热搜获取失败: {e}")
    return results
