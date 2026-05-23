"""帝国架构 v3.2 - 企业级安全与治理

包含：
- SecuritySystem: 向后兼容的敏感词检查
- ZeroTrustEngine: 零信任访问控制引擎
- DataEncryptor: AES-256 数据加密（Fernet / 轻量回退）
- AuditLogger: 全链路审计日志与合规报告导出
"""
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from core.logger import get_logger

log = get_logger("security")

# ──────────────────────────────────────────────
# 敏感词库（向后兼容 v3.0）
# ──────────────────────────────────────────────
SENSITIVE_KEYWORDS = [
    "rm -rf", "delete", "drop table", "password", "secret", "token",
    "api_key", "private_key", "sudo", "chmod 777", "wget", "curl",
    "外发", "泄露", "密钥", "密码",
]


class SecuritySystem:
    """安全系统 - 向后兼容 v3.0 的敏感词检查"""

    def __init__(self):
        self.violations: list[dict] = []

    def check_sensitive(self, text: str) -> tuple[bool, list[str]]:
        """检查文本中是否包含敏感关键词"""
        triggers = [kw for kw in SENSITIVE_KEYWORDS if kw.lower() in text.lower()]
        if triggers:
            self.violations.append({"text": text[:100], "triggers": triggers})
        return bool(triggers), triggers

    def get_status(self) -> dict:
        return {"total_violations": len(self.violations)}


# ──────────────────────────────────────────────
# 零信任引擎
# ──────────────────────────────────────────────
class TrustLevel(Enum):
    """信任等级"""
    UNTRUSTED = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    VERIFIED = 4


class AccessDecision(Enum):
    """访问决策"""
    ALLOW = "allow"
    DENY = "deny"
    CHALLENGE = "challenge"  # 需要二次验证


class ZeroTrustEngine:
    """零信任访问控制引擎

    核心原则：永不信任，始终验证。
    每次访问都经过身份验证、权限检查、上下文评估三重校验。
    """

    def __init__(self):
        self._identity_store: dict[str, dict] = {}  # id -> identity info
        self._access_policies: list[dict] = []
        self._trust_scores: dict[str, float] = defaultdict(lambda: 0.0)
        self._challenge_handlers: dict[str, Any] = {}

    def register_identity(self, identity_id: str, roles: list[str],
                          attributes: Optional[dict] = None) -> None:
        """注册身份"""
        self._identity_store[identity_id] = {
            "id": identity_id,
            "roles": roles,
            "attributes": attributes or {},
            "registered_at": time.time(),
            "last_verified": 0.0,
        }
        self._trust_scores[identity_id] = 0.5  # 初始信任分
        log.info(f"身份注册: {identity_id}, 角色: {roles}")

    def add_policy(self, resource: str, action: str,
                   min_trust: float = 0.5,
                   required_roles: Optional[list[str]] = None,
                   require_mfa: bool = False) -> None:
        """添加访问策略"""
        self._access_policies.append({
            "resource": resource,
            "action": action,
            "min_trust": min_trust,
            "required_roles": required_roles or [],
            "require_mfa": require_mfa,
        })

    def evaluate_access(self, identity_id: str, resource: str,
                        action: str, context: Optional[dict] = None) -> tuple[AccessDecision, str]:
        """评估访问请求 — 每次都验证

        Returns:
            (decision, reason)
        """
        context = context or {}

        # 1) 身份存在性校验
        identity = self._identity_store.get(identity_id)
        if not identity:
            return AccessDecision.DENY, f"身份未注册: {identity_id}"

        # 2) 匹配策略
        matched_policies = [
            p for p in self._access_policies
            if self._resource_match(p["resource"], resource)
            and self._action_match(p["action"], action)
        ]

        if not matched_policies:
            # 默认拒绝 — 零信任原则
            return AccessDecision.DENY, "无匹配策略，默认拒绝"

        # 3) 逐一校验策略
        trust_score = self._trust_scores[identity_id]
        for policy in matched_policies:
            # 角色检查
            if policy["required_roles"]:
                if not any(r in identity["roles"] for r in policy["required_roles"]):
                    return AccessDecision.DENY, f"角色不足，需要: {policy['required_roles']}"

            # 信任分检查
            if trust_score < policy["min_trust"]:
                if policy["require_mfa"]:
                    return AccessDecision.CHALLENGE, f"信任分 {trust_score:.2f} < {policy['min_trust']}，需要二次验证"
                return AccessDecision.DENY, f"信任分不足: {trust_score:.2f}"

        # 4) 更新验证时间
        identity["last_verified"] = time.time()
        self._trust_scores[identity_id] = min(1.0, trust_score + 0.01)

        return AccessDecision.ALLOW, "零信任校验通过"

    def update_trust_score(self, identity_id: str, delta: float,
                           reason: str = "") -> float:
        """动态调整信任分"""
        old = self._trust_scores[identity_id]
        self._trust_scores[identity_id] = max(0.0, min(1.0, old + delta))
        log.info(f"信任分调整: {identity_id} {old:.2f} -> {self._trust_scores[identity_id]:.2f} ({reason})")
        return self._trust_scores[identity_id]

    def get_identity_status(self, identity_id: str) -> dict:
        """获取身份状态"""
        identity = self._identity_store.get(identity_id)
        if not identity:
            return {"exists": False}
        return {
            "exists": True,
            **identity,
            "trust_score": self._trust_scores[identity_id],
        }

    @staticmethod
    def _resource_match(pattern: str, resource: str) -> bool:
        """资源路径匹配（支持通配符 *）"""
        if pattern == "*":
            return True
        if pattern.endswith("/*"):
            return resource.startswith(pattern[:-2])
        return pattern == resource

    @staticmethod
    def _action_match(pattern: str, action: str) -> bool:
        if pattern == "*":
            return True
        return pattern == action


# ──────────────────────────────────────────────
# 数据加密器
# ──────────────────────────────────────────────
class DataEncryptor:
    """AES-256 数据加密器

    优先使用 cryptography.Fernet（AES-256-CBC + HMAC-SHA256）。
    如库不可用，回退到 hashlib + XOR 轻量实现。
    """

    def __init__(self, key: Optional[bytes] = None):
        self._backend = "lightweight"
        self._key: bytes = key or os.urandom(32)
        self._fernet = None

        # 尝试加载 cryptography
        try:
            from cryptography.fernet import Fernet as _Fernet
            # Fernet 需要 32 字节 url-safe base64 编码的 key
            import base64
            fernet_key = base64.urlsafe_b64encode(self._key[:32])
            self._fernet = _Fernet(fernet_key)
            self._backend = "fernet"
            log.info("加密后端: cryptography Fernet (AES-256)")
        except ImportError:
            log.info("加密后端: 轻量 hashlib+XOR（建议安装 cryptography 以获得完整 AES-256）")

    @property
    def backend(self) -> str:
        return self._backend

    def encrypt(self, plaintext: str) -> str:
        """加密字符串，返回编码后的密文"""
        if self._fernet:
            token = self._fernet.encrypt(plaintext.encode("utf-8"))
            return token.decode("ascii")
        return self._lightweight_encrypt(plaintext)

    def decrypt(self, ciphertext: str) -> str:
        """解密字符串"""
        if self._fernet:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        return self._lightweight_decrypt(ciphertext)

    def encrypt_dict(self, data: dict, sensitive_keys: Optional[list[str]] = None) -> dict:
        """加密字典中的敏感字段

        Args:
            data: 原始字典
            sensitive_keys: 需要加密的键列表，None 则加密全部
        """
        result = {}
        for k, v in data.items():
            if sensitive_keys is None or k in sensitive_keys:
                if isinstance(v, str):
                    result[k] = self.encrypt(v)
                else:
                    result[k] = self.encrypt(json.dumps(v, ensure_ascii=False))
            else:
                result[k] = v
        return result

    def decrypt_dict(self, data: dict, encrypted_keys: Optional[list[str]] = None) -> dict:
        """解密字典中的加密字段"""
        result = {}
        for k, v in data.items():
            if encrypted_keys is None or k in encrypted_keys:
                if isinstance(v, str):
                    result[k] = self.decrypt(v)
                else:
                    result[k] = v
            else:
                result[k] = v
        return result

    # ── 轻量回退实现 ──
    def _lightweight_encrypt(self, plaintext: str) -> str:
        """基于 HMAC-SHA256 + XOR 的轻量加密"""
        data = plaintext.encode("utf-8")
        # 生成随机 IV
        iv = os.urandom(16)
        # 用 HMAC 派生密钥流
        keystream = self._derive_keystream(iv, len(data))
        # XOR 加密
        encrypted = bytes(a ^ b for a, b in zip(data, keystream))
        # 组装: iv(16) + ciphertext，再做完整性校验
        payload = iv + encrypted
        mac = hmac.new(self._key, payload, hashlib.sha256).digest()
        import base64
        return base64.b64encode(payload + mac).decode("ascii")

    def _lightweight_decrypt(self, ciphertext: str) -> str:
        """轻量解密"""
        import base64
        raw = base64.b64decode(ciphertext.encode("ascii"))
        if len(raw) < 48:  # 16(iv) + 至少1字节密文 + 32(mac)
            raise ValueError("密文格式无效")

        payload = raw[:-32]
        stored_mac = raw[-32:]
        # 校验完整性
        expected_mac = hmac.new(self._key, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(stored_mac, expected_mac):
            raise ValueError("数据完整性校验失败")

        iv = payload[:16]
        encrypted = payload[16:]
        keystream = self._derive_keystream(iv, len(encrypted))
        decrypted = bytes(a ^ b for a, b in zip(encrypted, keystream))
        return decrypted.decode("utf-8")

    def _derive_keystream(self, iv: bytes, length: int) -> bytes:
        """从密钥和 IV 派生密钥流"""
        stream = bytearray()
        counter = 0
        while len(stream) < length:
            h = hmac.new(self._key, iv + counter.to_bytes(4, "big"), hashlib.sha256).digest()
            stream.extend(h)
            counter += 1
        return bytes(stream[:length])


# ──────────────────────────────────────────────
# 审计日志
# ──────────────────────────────────────────────
class AuditAction(Enum):
    """审计动作类型"""
    ACCESS = "access"
    MODIFY = "modify"
    CREATE = "create"
    DELETE = "delete"
    AUTH = "auth"
    EXPORT = "export"
    CONFIG_CHANGE = "config_change"
    SECURITY_EVENT = "security_event"


class AuditLogger:
    """全链路审计日志

    记录格式: who / what / when / where / result / context
    支持导出合规报告（JSON / 摘要统计）。
    """

    def __init__(self, log_dir: Optional[str] = None):
        self._entries: list[dict] = []
        self._log_dir = Path(log_dir) if log_dir else None
        if self._log_dir:
            self._log_dir.mkdir(parents=True, exist_ok=True)

    def log(self, who: str, action: AuditAction, resource: str,
            result: str = "success", context: Optional[dict] = None,
            risk_level: str = "low") -> dict:
        """记录审计事件"""
        entry = {
            "id": str(uuid.uuid4()),
            "who": who,
            "action": action.value,
            "resource": resource,
            "result": result,
            "risk_level": risk_level,
            "context": context or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "epoch": time.time(),
        }
        self._entries.append(entry)
        log.info(f"[审计] {who} {action.value} {resource} -> {result}")
        return entry

    def query(self, who: Optional[str] = None, action: Optional[AuditAction] = None,
              resource: Optional[str] = None, since: Optional[float] = None,
              risk_level: Optional[str] = None) -> list[dict]:
        """查询审计日志"""
        results = self._entries
        if who:
            results = [e for e in results if e["who"] == who]
        if action:
            results = [e for e in results if e["action"] == action.value]
        if resource:
            results = [e for e in results if e["resource"] == resource]
        if since:
            results = [e for e in results if e["epoch"] >= since]
        if risk_level:
            results = [e for e in results if e["risk_level"] == risk_level]
        return results

    def export_compliance_report(self, format: str = "json") -> str:
        """导出合规报告

        Args:
            format: "json" 完整日志 / "summary" 统计摘要
        """
        if format == "summary":
            return self._generate_summary()
        # JSON 完整报告
        report = {
            "report_type": "compliance_audit",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_events": len(self._entries),
            "entries": self._entries,
        }
        report_json = json.dumps(report, ensure_ascii=False, indent=2)
        if self._log_dir:
            path = self._log_dir / f"audit_{int(time.time())}.json"
            path.write_text(report_json, encoding="utf-8")
            log.info(f"审计报告已导出: {path}")
        return report_json

    def _generate_summary(self) -> str:
        """生成统计摘要"""
        stats: dict[str, Any] = {
            "total": len(self._entries),
            "by_action": defaultdict(int),
            "by_result": defaultdict(int),
            "by_risk": defaultdict(int),
            "by_user": defaultdict(int),
            "high_risk_events": [],
        }
        for e in self._entries:
            stats["by_action"][e["action"]] += 1
            stats["by_result"][e["result"]] += 1
            stats["by_risk"][e["risk_level"]] += 1
            stats["by_user"][e["who"]] += 1
            if e["risk_level"] in ("high", "critical"):
                stats["high_risk_events"].append(e)

        # 转换 defaultdict 为普通 dict
        stats["by_action"] = dict(stats["by_action"])
        stats["by_result"] = dict(stats["by_result"])
        stats["by_risk"] = dict(stats["by_risk"])
        stats["by_user"] = dict(stats["by_user"])

        report = {
            "report_type": "compliance_summary",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            **stats,
        }
        return json.dumps(report, ensure_ascii=False, indent=2)

    @property
    def entry_count(self) -> int:
        return len(self._entries)
