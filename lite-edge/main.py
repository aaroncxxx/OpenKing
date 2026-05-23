#!/usr/bin/env python3
"""帝国架构 v3.1 - 轻量版（边缘设备）
保留核心功能，去除重型依赖
"""
import asyncio
import json
import sys
import os
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))

# 最小化配置
API_KEY = os.environ.get("MIMO_API_KEY", "")
API_URL = os.environ.get("MIMO_API_ENDPOINT", "https://api.xiaomimimo.com/v1")

def call_llm(prompt: str, system: str = "") -> str:
    url = f"{API_URL.rstrip(\'\'\/\'\')}/chat/completions"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({"model": "mimo-v2.5-pro", "messages": messages, "max_tokens": 2048}).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]

async def main():
    print("🏛️ Empire Architecture v3.1 Lite (Edge)")
    print(f"模型: mimo-v2.5-pro | API: {API_URL}")
    print()

    while True:
        try:
            cmd = input("👑 > ").strip()
            if cmd in ("exit", "quit", "q"):
                break
            if not cmd:
                continue
            result = call_llm(cmd, "你是帝国架构的丞相，简洁高效地回答皇帝的指令。")
            print(f"\n📊 {result}\n")
        except (KeyboardInterrupt, EOFError):
            break

if __name__ == "__main__":
    asyncio.run(main())
