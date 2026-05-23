"""帝国架构 v3.2 - 企业级安全与治理

RBAC 角色权限控制、身份认证与多租户框架
"""
import hashlib
import json
import secrets
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from core.logger import get_logger

log = get_logger("rbac")


# ──────────────────────────────────────────────
# 角色定义
# ──────────────────────────────────────────────
class Role(Enum):
    """帝国角色体系"""
    EMPEROR = "emperor"       # 皇帝 — 最高权限
    CHANCELLOR = "chancellor" # 丞相 — 行政权
    SAN_GONG = "san_gong"     # 三公 — 太尉/司徒/司空
    JIU_QING = "jiu_qing"     # 九卿 — 部门长官
    EXECUTOR = "executor"     # 执行 — 任务执行者
    INSPECTOR = "inspector"   # 监察 — 御史台
    VISITOR = "visitor"       # 访客 — 最低权限


# 角色权限映射
ROLE_PERMISSIONS: dict[Role, dict[str, set[str]]] = {
    Role.EMPEROR: {
        "empire": {"read", "write", "delete", "admin", "govern"},
        "task": {"create", "read", "update", "delete", "assign", "cancel"},
        "agent": {"create", "read", "update", "delete", "command"},
        "finance": {"read", "write", "approve", "audit"},
        "security": {"read", "write", "audit", "override"},
        "config": {"read", "write"},
        "audit": {"read", "export"},
        "tenant": {"create", "read", "update", "delete"},
    },
    Role.CHANCELLOR: {
        "empire": {"read", "write", "govern"},
        "task": {"create", "read", "update", "assign"},
        "agent": {"create", "read", "update", "command"},
        "finance": {"read", "write", "approve"},
        "security": {"read"},
        "config": {"read", "write"},
        "audit": {"read"},
        "tenant": {"read"},
    },
    Role.SAN_GONG: {
        "empire": {"read", "write"},
        "task": {"create", "read", "update", "assign"},
        "agent": {"read", "update", "command"},
        "finance": {"read", "approve"},
        "security": {"read", "audit"},
        "config": {"read"},
        "audit": {"read", "export"},
        "tenant": {"read"},
    },
    Role.JIU_QING: {
        "empire": {"read"},
        "task": {"create", "read", "update"},
        "agent": {"read"},
        "finance": {"read", "write"},
        "security": {"read"},
        "config": {"read"},
        "audit": {"read"},
    },
    Role.EXECUTOR: {
        "empire": {"read"},
        "task": {"read", "update"},
        "agent": {"read"},
        "config": {"read"},
    },
    Role.INSPECTOR: {
        "empire": {"read"},
        "task": {"read"},
        "agent": {"read"},
        "finance": {"read", "audit"},
        "security": {"read", "audit"},
        "audit": {"read", "export"},
    },
    Role.VISITOR: {
        "empire": {"read"},
        "task": {"read"},
    },
}


# ──────────────────────────────────────────────
# 权限检查
# ──────────────────────────────────────────────
def check_permission(role: str | Role, action: str, resource: str) -> tuple[bool, str]:
    """检查角色是否对指定资源拥有指定操作权限

    Args:
        role: 角色名（字符串或 Role 枚举）
        action: 操作（如 read, write, delete）
        resource: 资源类型（如 task, agent, finance）

    Returns:
        (allowed, reason)
    """
    if isinstance(role, str):
        try:
            role = Role(role)
        except ValueError:
            return False, f"未知角色: {role}"

    perms = ROLE_PERMISSIONS.get(role, {})
    allowed_actions = perms.get(resource, set())

    if action in allowed_actions:
        return True, f"角色 {role.value} 拥有 {resource}:{action} 权限"
    return False, f"角色 {role.value} 无 {resource}:{action} 权限"


def get_role_permissions(role: str | Role) -> dict[str, list[str]]:
    """获取角色的完整权限列表"""
    if isinstance(role, str):
        try:
            role = Role(role)
        except ValueError:
            return {}
    perms = ROLE_PERMISSIONS.get(role, {})
    return {k: sorted(v) for k, v in perms.items()}


# ──────────────────────────────────────────────
# 身份认证管理器
# ──────────────────────────────────────────────
class AuthManager:
    """身份认证管理器

    支持 token 认证、会话管理、登录尝试限制。
    """

    def __init__(self, session_ttl: int = 3600, max_login_attempts: int = 5):
        self._users: dict[str, dict] = {}         # user_id -> user info
        self._sessions: dict[str, dict] = {}       # session_token -> session
        self._login_attempts: dict[str, list[float]] = {}  # user_id -> [timestamps]
        self._session_ttl = session_ttl
        self._max_login_attempts = max_login_attempts

    def register_user(self, user_id: str, role: str | Role,
                      name: str = "", attributes: Optional[dict] = None) -> bool:
        """注册用户"""
        if user_id in self._users:
            return False
        role_val = role.value if isinstance(role, Role) else role
        self._users[user_id] = {
            "user_id": user_id,
            "role": role_val,
            "name": name or user_id,
            "attributes": attributes or {},
            "created_at": time.time(),
            "active": True,
        }
        log.info(f"用户注册: {user_id} (角色: {role_val})")
        return True

    def authenticate(self, user_id: str, credential: str) -> Optional[str]:
        """认证用户并返回 session token

        Args:
            user_id: 用户 ID
            *: 凭证（简化版，生产环境应使用密码哈希或 OAuth）

        Returns:
            session token 或 None（认证失败）
        """
        user = self._users.get(user_id)
        if not user or not user["active"]:
            log.warning(f"认证失败: 用户不存在或已禁用 ({user_id})")
            return None

        # 检查登录频率限制
        if self._is_rate_limited(user_id):
            log.warning(f"认证失败: 登录频率限制 ({user_id})")
            return None

        # 生成 session token
        token = secrets.token_urlsafe(32)
        self._sessions[token] = {
            "user_id": user_id,
            "role": user["role"],
            "created_at": time.time(),
            "expires_at": time.time() + self._session_ttl,
            "last_active": time.time(),
        }
        log.info(f"认证成功: {user_id}, session={token[:8]}...")
        return token

    def validate_session(self, token: str) -> Optional[dict]:
        """验证 session token，返回会话信息或 None"""
        session = self._sessions.get(token)
        if not session:
            return None
        if time.time() > session["expires_at"]:
            del self._sessions[token]
            return None
        session["last_active"] = time.time()
        return session

    def revoke_session(self, token: str) -> bool:
        """撤销 session"""
        if token in self._sessions:
            del self._sessions[token]
            return True
        return False

    def revoke_all_sessions(self, user_id: str) -> int:
        """撤销用户所有 session"""
        tokens_to_remove = [
            t for t, s in self._sessions.items() if s["user_id"] == user_id
        ]
        for t in tokens_to_remove:
            del self._sessions[t]
        return len(tokens_to_remove)

    def get_active_sessions(self, user_id: Optional[str] = None) -> list[dict]:
        """获取活跃会话列表"""
        now = time.time()
        sessions = []
        for token, s in self._sessions.items():
            if now > s["expires_at"]:
                continue
            if user_id and s["user_id"] != user_id:
                continue
            sessions.append({
                "token_prefix": token[:8] + "...",
                "user_id": s["user_id"],
                "role": s["role"],
                "created_at": s["created_at"],
                "expires_at": s["expires_at"],
            })
        return sessions

    def get_user(self, user_id: str) -> Optional[dict]:
        """获取用户信息"""
        return self._users.get(user_id)

    def list_users(self) -> list[dict]:
        """列出所有用户"""
        return [
            {"user_id": u["user_id"], "role": u["role"],
             "name": u["name"], "active": u["active"]}
            for u in self._users.values()
        ]

    def _is_rate_limited(self, user_id: str) -> bool:
        """检查是否触发频率限制"""
        now = time.time()
        attempts = self._login_attempts.get(user_id, [])
        # 清理 5 分钟前的记录
        recent = [t for t in attempts if now - t < 300]
        self._login_attempts[user_id] = recent
        if len(recent) >= self._max_login_attempts:
            return True
        recent.append(now)
        return False


# ──────────────────────────────────────────────
# 多租户上下文
# ──────────────────────────────────────────────
class TenantContext:
    """多租户上下文管理器

    支持帝国实例隔离，每个租户有独立的资源命名空间。
    用作上下文管理器或手动设置/清理。
    """

    _current: Optional["TenantContext"] = None

    def __init__(self, tenant_id: str, name: str = "",
                 attributes: Optional[dict] = None):
        self.tenant_id = tenant_id
        self.name = name or tenant_id
        self.attributes = attributes or {}
        self.created_at = time.time()
        self._resource_registry: dict[str, dict] = {}

    def __enter__(self) -> "TenantContext":
        TenantContext._current = self
        log.info(f"租户上下文激活: {self.tenant_id}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        TenantContext._current = None
        log.info(f"租户上下文释放: {self.tenant_id}")

    @classmethod
    def current(cls) -> Optional["TenantContext"]:
        """获取当前活跃的租户上下文"""
        return cls._current

    def register_resource(self, resource_type: str, resource_id: str,
                          metadata: Optional[dict] = None) -> str:
        """注册资源到当前租户命名空间

        Returns:
            带租户前缀的资源标识符: tenant:{tenant_id}:{type}:{id}
        """
        qualified_id = f"tenant:{self.tenant_id}:{resource_type}:{resource_id}"
        self._resource_registry[qualified_id] = {
            "type": resource_type,
            "id": resource_id,
            "metadata": metadata or {},
            "registered_at": time.time(),
        }
        return qualified_id

    def get_resources(self, resource_type: Optional[str] = None) -> list[dict]:
        """获取租户下的资源列表"""
        results = []
        for qid, info in self._resource_registry.items():
            if resource_type and info["type"] != resource_type:
                continue
            results.append({"qualified_id": qid, **info})
        return results

    def isolate_key(self, key: str) -> str:
        """将通用 key 转换为租户隔离 key"""
        return f"{self.tenant_id}:{key}"

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "attributes": self.attributes,
            "resource_count": len(self._resource_registry),
            "created_at": self.created_at,
        }
