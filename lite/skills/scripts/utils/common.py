#!/usr/bin/env python3
"""V2.4 通用工具函数"""

import sys
import os
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

VERSION = "2.5.0"
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(SCRIPT_DIR, ".cache")

def log(msg):
    print(msg, file=sys.stderr)

def format_hot(num):
    if num >= 1000000:
        return f"{num/1000000:.1f}万"
    elif num >= 10000:
        return f"{num/10000:.1f}万"
    elif num >= 1000:
        return f"{num/1000:.1f}千"
    return str(num)

def format_yi(num):
    if abs(num) >= 10000:
        return f"{num/10000:.2f}万亿"
    return f"{num:.2f}亿"

def is_trading_day():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    return True

def get_last_trading_date():
    now = datetime.now()
    offset = 0
    if now.weekday() == 5:
        offset = 1
    elif now.weekday() == 6:
        offset = 2
    if now.hour < 9 or (now.hour == 9 and now.minute < 30):
        offset += 1
    return (now - timedelta(days=offset)).strftime("%Y-%m-%d")

def http_get_json(url, headers=None, timeout=10, retries=2):
    """通用 HTTP GET → JSON"""
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    if headers:
        default_headers.update(headers)
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=default_headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
                continue
            return None

def http_get_text(url, headers=None, timeout=10, retries=2):
    """通用 HTTP GET → text"""
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,*/*",
    }
    if headers:
        default_headers.update(headers)
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=default_headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
                continue
            return None

# ============================================================
# 快照缓存
# ============================================================
def save_snapshot(data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    snapshot = {
        "date": today,
        "market": data.get("market", []),
        "zt_dt": data.get("zt_dt", {}),
        "sectors": data.get("sectors", []),
        "northbound": data.get("northbound", {}),
        "hotsearch": data.get("stock_hot", []),
    }
    path = os.path.join(CACHE_DIR, f"{today}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_recent_snapshots(days=5):
    snapshots = []
    today = datetime.now()
    for i in range(days):
        date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        path = os.path.join(CACHE_DIR, f"{date}.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    snapshots.append(json.load(f))
            except Exception:
                pass
    return sorted(snapshots, key=lambda x: x["date"])
