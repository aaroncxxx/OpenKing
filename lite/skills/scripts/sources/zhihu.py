#!/usr/bin/env python3
"""知乎热榜数据源"""

import json
import time
import urllib.request
from utils.common import log

PLATFORM_NAME = "知乎"

def fetch_zhihu_hot(retries=2):
    """抓取知乎热榜"""
    results = []
    url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.zhihu.com/hot",
    }
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            items = data.get("data", [])
            for i, item in enumerate(items[:50]):
                target = item.get("target", {})
                title = target.get("title", "")
                excerpt = target.get("excerpt", "")
                detail_text = item.get("detail_text", "0")
                # 解析热度值
                hot = 0
                if "万" in detail_text:
                    try:
                        hot = int(float(detail_text.replace("万", "").strip()) * 10000)
                    except ValueError:
                        hot = 0
                else:
                    try:
                        hot = int(detail_text)
                    except ValueError:
                        hot = 0
                if title:
                    results.append({
                        "rank": i + 1,
                        "keyword": title,
                        "hot": hot,
                        "platform": "zhihu",
                        "platform_cn": "知乎",
                        "excerpt": excerpt[:100] if excerpt else "",
                    })
            if results:
                break
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
                continue
            log(f"⚠️  知乎热榜获取失败: {e}")
    return results
