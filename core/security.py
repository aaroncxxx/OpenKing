"""帝国架构 v3.0 - 安全系统"""
from core.logger import get_logger

log = get_logger("security")

SENSITIVE_KEYWORDS = [
    "rm -rf", "delete", "drop table", "password", "secret", "token",
    "api_key", "private_key", "sudo", "chmod 777", "wget", "curl",
    "外发", "泄露", "密钥", "密码",
]


class SecuritySystem:
    """安全系统 v3.0 - 事前检查 + 锦衣卫审计"""

    def __init__(self):
        self.violations = []

    def check_sensitive(self, text: str) -> tuple[bool, list[str]]:
        triggers = [kw for kw in SENSITIVE_KEYWORDS if kw.lower() in text.lower()]
        if triggers:
            self.violations.append({"text": text[:100], "triggers": triggers})
        return bool(triggers), triggers

    def get_status(self) -> dict:
        return {"total_violations": len(self.violations)}
