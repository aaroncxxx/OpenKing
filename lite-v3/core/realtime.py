"""帝国架构 v3.0 - 实时协作（持续监控 + 事件驱动 + 消息推送）"""
import asyncio
import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Optional
from core.logger import get_logger

log = get_logger("realtime")


@dataclass
class MonitorRule:
    rule_id: str
    name: str
    condition: str          # 条件描述
    check_fn: Callable      # 检查函数
    action_prompt: str      # 触发时的任务 prompt
    interval_seconds: int = 300
    last_check: float = 0
    enabled: bool = True


@dataclass
class WebhookConfig:
    name: str
    url: str
    webhook_type: str = "generic"  # dingtalk, feishu, wecom, generic
    enabled: bool = True


class RealtimeEngine:
    """实时协作引擎 v3.0 - 持续监控 + 事件驱动"""

    def __init__(self):
        self.monitor_rules: dict[str, MonitorRule] = {}
        self.webhooks: list[WebhookConfig] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def add_monitor_rule(self, rule: MonitorRule):
        """添加监控规则"""
        self.monitor_rules[rule.rule_id] = rule
        log.info(f"监控规则添加: {rule.name} (间隔 {rule.interval_seconds}s)")

    def remove_monitor_rule(self, rule_id: str):
        self.monitor_rules.pop(rule_id, None)

    def add_webhook(self, config: WebhookConfig):
        self.webhooks.append(config)
        log.info(f"Webhook 添加: {config.name} ({config.webhook_type})")

    async def start(self, chancellor):
        """启动实时监控"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop(chancellor))
        log.info("实时监控已启动")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        log.info("实时监控已停止")

    async def _monitor_loop(self, chancellor):
        """监控主循环"""
        while self._running:
            now = time.time()
            for rule_id, rule in self.monitor_rules.items():
                if not rule.enabled:
                    continue
                if now - rule.last_check < rule.interval_seconds:
                    continue

                rule.last_check = now
                try:
                    should_trigger = rule.check_fn()
                    if should_trigger:
                        log.info(f"监控触发: {rule.name}")
                        result = await chancellor.receive_command(rule.action_prompt)
                        await self._notify(result, rule.name)
                except Exception as e:
                    log.error(f"监控检查失败: {rule.name}: {e}")

            await asyncio.sleep(10)

    async def _notify(self, result: dict, rule_name: str):
        """推送通知到 Webhook"""
        summary = result.get("results", {}).get("chancellor_summary", "无汇总")
        message = f"🔔 **{rule_name}** 触发\n\n{summary[:500]}"

        for webhook in self.webhooks:
            if not webhook.enabled:
                continue
            try:
                await self._send_webhook(webhook, message)
            except Exception as e:
                log.error(f"Webhook 发送失败: {webhook.name}: {e}")

    async def _send_webhook(self, config: WebhookConfig, message: str):
        """发送 Webhook"""
        if config.webhook_type == "dingtalk":
            body = json.dumps({"msgtype": "text", "text": {"content": message}}).encode()
        elif config.webhook_type == "feishu":
            body = json.dumps({"msg_type": "text", "content": {"text": message}}).encode()
        elif config.webhook_type == "wecom":
            body = json.dumps({"msgtype": "text", "text": {"content": message}}).encode()
        else:
            body = json.dumps({"text": message}).encode()

        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(config.url, data=body, headers=headers)
        urllib.request.urlopen(req, timeout=10)

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "rules": len(self.monitor_rules),
            "webhooks": len(self.webhooks),
            "rules_detail": [
                {"id": r.rule_id, "name": r.name, "interval": r.interval_seconds, "enabled": r.enabled}
                for r in self.monitor_rules.values()
            ],
        }
