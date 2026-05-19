#!/usr/bin/env python3
"""东方财富股吧热搜数据源"""

import json
import time
import re
import urllib.request
from utils.common import log

PLATFORM_NAME = "东方财富股吧"

def fetch_eastmoney_hot(retries=2):
    """抓取东方财富股吧热门话题"""
    results = []
    # 东方财富股吧热帖 API
    url = "https://guba.eastmoney.com/interface/GetData.aspx?param=ps-1_p-1_tp-popular&path=guba/qa"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://guba.eastmoney.com/",
    }
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                text = resp.read().decode("utf-8")
            # 尝试解析 JSON
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                # 可能是 JSONP 格式
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    data = json.loads(match.group())
                else:
                    raise ValueError("无法解析响应")
            
            items = data.get("re", data.get("data", []))
            if isinstance(items, list):
                for i, item in enumerate(items[:30]):
                    title = item.get("post_title", item.get("title", ""))
                    if title:
                        # 清理 HTML 标签
                        title = re.sub(r'<[^>]+>', '', title).strip()
                        results.append({
                            "rank": i + 1,
                            "keyword": title[:30],
                            "hot": item.get("post_click_count", item.get("readCount", 0)),
                            "platform": "eastmoney",
                            "platform_cn": "东方财富股吧",
                            "stock_code": item.get("stock_code", ""),
                            "stock_name": item.get("stock_name", ""),
                        })
            if results:
                break
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
                continue
            log(f"⚠️  东方财富股吧热搜获取失败: {e}")
    
    # 备用方案：抓取热门个股讨论
    if not results:
        results = _fetch_eastmoney_stock_hot()
    return results


def _fetch_eastmoney_stock_hot():
    """备用：东方财富热门股票讨论"""
    results = []
    try:
        url = "https://emappdata.eastmoney.com/stockrank/getAllCurrentList"
        payload = json.dumps({"appId": "appId01", "pageNo": 1, "pageSize": 30}).encode()
        req = urllib.request.Request(url, data=payload, headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for i, item in enumerate(data.get("data", [])[:30]):
            results.append({
                "rank": i + 1,
                "keyword": item.get("name", ""),
                "hot": item.get("sc", 0),
                "platform": "eastmoney",
                "platform_cn": "东方财富股吧",
                "stock_code": item.get("code", ""),
            })
    except Exception as e:
        log(f"⚠️  东方财富备用源也失败: {e}")
    return results
