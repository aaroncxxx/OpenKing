#!/usr/bin/env python3
"""
自动化与定时任务 V2.2
- 定时执行（开盘前/盘中/收盘后）
- 自动推送（Webhook: 邮箱/钉钉/企微/微信）
- 本地数据归档（按日期）
"""

import json
import os
import urllib.request
from datetime import datetime
from utils.common import log, CACHE_DIR

ARCHIVE_DIR = os.path.join(CACHE_DIR, "archive")
CONFIG_FILE = os.path.join(CACHE_DIR, "automation.json")


class AutomationManager:
    """自动化管理器"""

    def __init__(self):
        self.config = self._load_config()

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"schedules": [], "webhooks": [], "archive_enabled": True}

    def _save_config(self):
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    # ============================================================
    # 定时任务配置
    # ============================================================
    def add_schedule(self, name, time_str, args="", enabled=True):
        """
        添加定时任务
        time_str: "09:00" 格式
        args: 命令行参数，如 "--brief --md"
        """
        schedule = {
            "name": name,
            "time": time_str,
            "args": args,
            "enabled": enabled,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        self.config["schedules"].append(schedule)
        self._save_config()
        return schedule

    def remove_schedule(self, name):
        self.config["schedules"] = [s for s in self.config["schedules"] if s["name"] != name]
        self._save_config()

    def list_schedules(self):
        return self.config.get("schedules", [])

    def get_cron_entries(self, script_path):
        """
        生成 crontab 条目（供参考，不直接写入系统 crontab）
        """
        entries = []
        for s in self.config.get("schedules", []):
            if not s.get("enabled"):
                continue
            time_parts = s["time"].split(":")
            hour, minute = time_parts[0], time_parts[1] if len(time_parts) > 1 else "0"
            entry = f"{minute} {hour} * * 1-5 cd {os.path.dirname(script_path)} && python3 {script_path} {s.get('args', '')} >> {CACHE_DIR}/cron.log 2>&1"
            entries.append({"name": s["name"], "cron": entry, "time": s["time"]})
        return entries

    # ============================================================
    # Webhook 推送
    # ============================================================
    def add_webhook(self, name, url, webhook_type="custom", enabled=True):
        """
        添加 Webhook
        webhook_type: "dingtalk" | "wechat" | "feishu" | "custom"
        """
        wh = {
            "name": name,
            "url": url,
            "type": webhook_type,
            "enabled": enabled,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        self.config["webhooks"].append(wh)
        self._save_config()
        return wh

    def remove_webhook(self, name):
        self.config["webhooks"] = [w for w in self.config["webhooks"] if w["name"] != name]
        self._save_config()

    def list_webhooks(self):
        return self.config.get("webhooks", [])

    def push_report(self, report_text, title="A股热搜分析报告"):
        """推送报告到所有已启用的 Webhook"""
        results = []
        for wh in self.config.get("webhooks", []):
            if not wh.get("enabled"):
                continue
            try:
                success = self._send_webhook(wh, report_text, title)
                results.append({"name": wh["name"], "success": success})
            except Exception as e:
                results.append({"name": wh["name"], "success": False, "error": str(e)})
        return results

    def _send_webhook(self, webhook, text, title):
        """发送到单个 Webhook"""
        wh_type = webhook.get("type", "custom")
        url = webhook["url"]

        if wh_type == "dingtalk":
            payload = json.dumps({
                "msgtype": "text",
                "text": {"content": f"{title}\n\n{text}"},
            }).encode()
        elif wh_type == "wechat":
            payload = json.dumps({
                "msgtype": "text",
                "text": {"content": f"{title}\n\n{text}"},
            }).encode()
        elif wh_type == "feishu":
            payload = json.dumps({
                "msg_type": "text",
                "content": {"text": f"{title}\n\n{text}"},
            }).encode()
        else:
            payload = json.dumps({
                "title": title,
                "content": text,
            }).encode()

        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "User-Agent": "AStockAnalyzer/2.4",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200

    # ============================================================
    # 本地数据归档
    # ============================================================
    def archive_report(self, report_text, report_data=None):
        """按日期归档报告"""
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H%M")

        # 文本报告
        txt_path = os.path.join(ARCHIVE_DIR, f"{today}_{time_str}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(report_text)

        # JSON 数据
        if report_data:
            json_path = os.path.join(ARCHIVE_DIR, f"{today}_{time_str}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)

        return txt_path

    def list_archives(self, date=None):
        """列出归档文件"""
        if not os.path.exists(ARCHIVE_DIR):
            return []
        files = sorted(os.listdir(ARCHIVE_DIR), reverse=True)
        if date:
            files = [f for f in files if f.startswith(date)]
        return [f for f in files if f.endswith((".txt", ".json"))]

    def load_archive(self, filename):
        """加载归档文件"""
        path = os.path.join(ARCHIVE_DIR, filename)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
