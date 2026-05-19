#!/usr/bin/env python3
"""微博热搜数据源"""

import json
import time
import urllib.request
from utils.common import log, http_get_json

PLATFORM_NAME = "微博"

def fetch_weibo_hot(retries=2, proxy=None):
    """抓取微博实时热搜"""
    url = "https://weibo.com/ajax/side/hotSearch"
    headers = {
        "Referer": "https://weibo.com",
    }
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://weibo.com",
            })
            if proxy:
                proxy_handler = urllib.request.ProxyHandler({"https": proxy, "http": proxy})
                opener = urllib.request.build_opener(proxy_handler)
            else:
                opener = urllib.request.build_opener()
            with opener.open(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            hot_list = data.get("data", {}).get("realtime", [])
            return [
                {
                    "rank": item.get("rank", 0),
                    "keyword": item.get("word", ""),
                    "hot": item.get("num", 0),
                    "category": item.get("category", ""),
                    "label": item.get("label_name", ""),
                    "platform": "weibo",
                    "platform_cn": "微博",
                }
                for item in hot_list[:50]
            ]
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
                continue
            log(f"⚠️  微博热搜获取失败: {e}")
            return []
