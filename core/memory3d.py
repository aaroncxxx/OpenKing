"""帝国架构 v3.1 - 三维记忆系统升级
Forms-Functions-Dynamics 三维记忆框架：
- 形式层：Token级 / 参数级 / 潜在级
- 功能层：情景记忆 / 语义记忆 / 程序记忆
- 动态层：形成 / 巩固 / 检索 / 遗忘 / 更新
"""
import json
import os
import time
import math
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from core.logger import get_logger

log = get_logger("memory3d")


# ──────────────── 形式层 ────────────────

class MemoryForm(Enum):
    """记忆形式"""
    TOKEN = "token"         # Token 级：原始文本片段
    PARAMETER = "parameter" # 参数级：结构化参数/配置
    LATENT = "latent"       # 潜在级：embedding 向量表示


# ──────────────── 功能层 ────────────────

class MemoryFunction(Enum):
    """记忆功能"""
    EPISODIC = "episodic"    # 情景记忆：具体事件/经历
    SEMANTIC = "semantic"    # 语义记忆：知识/概念/事实
    PROCEDURAL = "procedural"  # 程序记忆：技能/流程/方法


# ──────────────── 记忆条目 ────────────────

@dataclass
class MemoryEngram:
    """记忆印迹 - 单条记忆的完整表示"""
    engram_id: str
    content: str                          # 原始内容
    form: MemoryForm = MemoryForm.TOKEN
    function: MemoryFunction = MemoryFunction.EPISODIC

    # 强度与衰退
    strength: float = 1.0                 # 记忆强度 [0, 1]
    consolidation_level: float = 0.0      # 巩固程度 [0, 1]
    access_count: int = 0                 # 访问次数
    last_accessed: float = 0              # 最后访问时间
    created_at: float = field(default_factory=time.time)

    # 向量表示（潜在级记忆）
    embedding: list[float] = field(default_factory=list)

    # 元数据
    source_agent: str = ""
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)
    task_id: str = ""
    metadata: dict = field(default_factory=dict)

    # 关联
    associations: list[str] = field(default_factory=list)  # 关联的其他 engram_id


class Memory3D:
    """三维记忆系统

    实现 Forms-Functions-Dynamics 框架：
    - 形式：Token/参数/潜在 三种表示
    - 功能：情景/语义/程序 三种类型
    - 动态：形成→巩固→检索→遗忘→更新 生命周期
    """

    def __init__(self, agent_id: str, data_dir: str = None):
        self.agent_id = agent_id
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "memory3d")
        os.makedirs(data_dir, exist_ok=True)
        self._path = os.path.join(data_dir, f"{agent_id}.json")

        self.engrams: dict[str, MemoryEngram] = {}
        self._consolidation_queue: list[str] = []

        # 统计
        self._stats = {
            "formed": 0, "consolidated": 0, "retrieved": 0,
            "forgotten": 0, "updated": 0,
        }

        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for e_data in data.get("engrams", []):
                    e = MemoryEngram(**e_data)
                    self.engrams[e.engram_id] = e
                self._stats = data.get("stats", self._stats)
            except Exception:
                pass

    def _save(self):
        try:
            data = {
                "engrams": [
                    {
                        "engram_id": e.engram_id, "content": e.content,
                        "form": e.form.value, "function": e.function.value,
                        "strength": e.strength, "consolidation_level": e.consolidation_level,
                        "access_count": e.access_count, "last_accessed": e.last_accessed,
                        "created_at": e.created_at, "source_agent": e.source_agent,
                        "importance": e.importance, "tags": e.tags,
                        "task_id": e.task_id, "associations": e.associations,
                    }
                    for e in list(self.engrams.values())[-500:]
                ],
                "stats": self._stats,
            }
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ──────────────── 形成（Formation）────────────────

    def form(self, content: str, function: MemoryFunction = MemoryFunction.EPISODIC,
             form: MemoryForm = MemoryForm.TOKEN, importance: float = 0.5,
             tags: list[str] = None, source_agent: str = "",
             embedding: list[float] = None, task_id: str = "") -> MemoryEngram:
        """形成新记忆"""
        import hashlib
        engram_id = hashlib.md5(f"{self.agent_id}_{time.time()}_{content[:50]}".encode()).hexdigest()[:16]

        engram = MemoryEngram(
            engram_id=engram_id, content=content,
            form=form, function=function,
            strength=importance * 0.8,  # 初始强度与重要性相关
            importance=importance, tags=tags or [],
            source_agent=source_agent, task_id=task_id,
            embedding=embedding or [],
            last_accessed=time.time(),
        )

        self.engrams[engram_id] = engram
        self._consolidation_queue.append(engram_id)
        self._stats["formed"] += 1

        log.debug(f"记忆形成: {self.agent_id} [{function.value}] {content[:50]}...")
        return engram

    # ──────────────── 巩固（Consolidation）────────────────

    def consolidate(self):
        """巩固记忆 - 将短期记忆转为长期记忆"""
        now = time.time()
        consolidated = 0

        for engram_id in list(self._consolidation_queue):
            if engram_id not in self.engrams:
                continue

            engram = self.engrams[engram_id]

            # 巩固条件：被访问多次 或 重要性高 或 经过时间
            age = now - engram.created_at
            if engram.access_count >= 2 or engram.importance >= 0.7 or age > 300:
                # 巩固强度衰减
                engram.consolidation_level = min(1.0, engram.consolidation_level + 0.3)
                consolidated += 1

                # 高重要性自动升级形式
                if engram.importance >= 0.8 and engram.form == MemoryForm.TOKEN:
                    engram.form = MemoryForm.PARAMETER

                self._consolidation_queue.remove(engram_id)

        self._stats["consolidated"] += consolidated
        if consolidated:
            self._save()
            log.debug(f"巩固 {consolidated} 条记忆")

    # ──────────────── 检索（Retrieval）────────────────

    def retrieve(self, query: str, top_k: int = 5,
                 function_filter: MemoryFunction = None) -> list[MemoryEngram]:
        """检索相关记忆"""
        self._stats["retrieved"] += 1

        candidates = []
        for engram in self.engrams.values():
            # 功能过滤
            if function_filter and engram.function != function_filter:
                continue

            # 计算相关性分数
            score = self._compute_relevance(query, engram)
            candidates.append((engram, score))

        # 按分数排序
        candidates.sort(key=lambda x: -x[1])

        # 更新访问记录
        for engram, score in candidates[:top_k]:
            engram.access_count += 1
            engram.last_accessed = time.time()
            # 访问增强记忆强度
            engram.strength = min(1.0, engram.strength + 0.05)

        return [e for e, _ in candidates[:top_k]]

    def _compute_relevance(self, query: str, engram: MemoryEngram) -> float:
        """计算查询与记忆的相关性"""
        score = 0.0

        # 关键词匹配
        query_lower = query.lower()
        content_lower = engram.content.lower()
        common_words = set(query_lower.split()) & set(content_lower.split())
        if common_words:
            score += len(common_words) * 0.2

        # 标签匹配
        query_tags = set(query_lower.split())
        matching_tags = query_tags & set(engram.tags)
        if matching_tags:
            score += len(matching_tags) * 0.3

        # 重要性加权
        score += engram.importance * 0.3

        # 强度加权
        score += engram.strength * 0.2

        # 时间衰减（越近越重要）
        age_hours = (time.time() - engram.last_accessed) / 3600
        time_factor = math.exp(-age_hours / 168)  # 一周半衰期
        score *= time_factor

        return score

    # ──────────────── 遗忘（Forgetting）────────────────

    def forget(self, decay_rate: float = 0.01):
        """自适应记忆衰退"""
        now = time.time()
        forgotten = 0
        to_remove = []

        for engram_id, engram in self.engrams.items():
            # 基础衰退：按时间
            age_hours = (now - engram.last_accessed) / 3600
            decay = decay_rate * age_hours

            # 重要性抵抗衰退
            resistance = engram.importance * 0.5
            # 访问频率抵抗衰退
            frequency_resistance = min(0.5, engram.access_count * 0.05)
            # 巩固程度抵抗衰退
            consolidation_resistance = engram.consolidation_level * 0.3

            effective_decay = decay * (1 - resistance - frequency_resistance - consolidation_resistance)
            effective_decay = max(0, effective_decay)

            engram.strength = max(0, engram.strength - effective_decay)

            # 强度过低 → 遗忘
            if engram.strength < 0.05:
                to_remove.append(engram_id)
                forgotten += 1

        for eid in to_remove:
            del self.engrams[eid]

        self._stats["forgotten"] += forgotten
        if forgotten:
            self._save()
            log.debug(f"遗忘 {forgotten} 条记忆")

        return forgotten

    # ──────────────── 更新（Updating）────────────────

    def update(self, engram_id: str, **kwargs) -> bool:
        """更新记忆"""
        if engram_id not in self.engrams:
            return False

        engram = self.engrams[engram_id]
        for key, value in kwargs.items():
            if hasattr(engram, key):
                setattr(engram, key, value)

        self._stats["updated"] += 1
        self._save()
        return True

    # ──────────────── 共享记忆空间 ────────────────

    def export_shareable(self, privacy_level: int = 0) -> list[dict]:
        """导出可共享的记忆（隐私过滤）

        privacy_level:
            0 = 全部共享
            1 = 隐藏敏感标签
            2 = 只共享语义记忆
        """
        shareable = []
        for engram in self.engrams.values():
            if privacy_level >= 2 and engram.function != MemoryFunction.SEMANTIC:
                continue

            entry = {
                "content": engram.content,
                "function": engram.function.value,
                "importance": engram.importance,
                "tags": engram.tags if privacy_level < 1 else [],
                "strength": engram.strength,
            }
            shareable.append(entry)

        return shareable

    def import_shared(self, shared_memories: list[dict], source: str = "shared"):
        """导入共享记忆"""
        for entry in shared_memories:
            self.form(
                content=entry["content"],
                function=MemoryFunction(entry.get("function", "semantic")),
                importance=entry.get("importance", 0.5) * 0.8,  # 共享记忆重要性打折
                tags=entry.get("tags", []) + ["shared"],
                source_agent=source,
            )

    # ──────────────── 生命周期管理 ────────────────

    def lifecycle_tick(self):
        """记忆生命周期管理（定期调用）"""
        self.consolidate()
        self.forget()
        self._save()

    def get_context_window(self, max_chars: int = 2000) -> str:
        """获取记忆上下文窗口（注入 prompt）"""
        # 按类型分组获取
        episodic = self.retrieve("", top_k=3, function_filter=MemoryFunction.EPISODIC)
        semantic = self.retrieve("", top_k=3, function_filter=MemoryFunction.SEMANTIC)
        procedural = self.retrieve("", top_k=2, function_filter=MemoryFunction.PROCEDURAL)

        parts = []
        if episodic:
            parts.append("【近期经历】\n" + "\n".join(f"- {e.content[:100]}" for e in episodic))
        if semantic:
            parts.append("【相关知识】\n" + "\n".join(f"- {e.content[:100]}" for e in semantic))
        if procedural:
            parts.append("【可用技能】\n" + "\n".join(f"- {e.content[:100]}" for e in procedural))

        text = "\n\n".join(parts)
        return text[:max_chars]

    def get_stats(self) -> dict:
        by_form = defaultdict(int)
        by_function = defaultdict(int)
        for e in self.engrams.values():
            by_form[e.form.value] += 1
            by_function[e.function.value] += 1

        return {
            "total_engrams": len(self.engrams),
            "by_form": dict(by_form),
            "by_function": dict(by_function),
            "lifecycle": self._stats,
            "consolidation_queue": len(self._consolidation_queue),
        }

    # ──────────────── 兼容旧接口 ────────────────

    def remember(self, text: str, importance: float = 0.5,
                 tags: list[str] = None, task_id: str = ""):
        """兼容 v2.x 接口"""
        self.form(text, importance=importance, tags=tags or [], task_id=task_id)

    def recall_recent(self, n: int = 5) -> list[str]:
        """兼容 v2.x 接口"""
        recent = sorted(self.engrams.values(), key=lambda e: e.last_accessed, reverse=True)
        return [e.content for e in recent[:n]]

    def recall_important(self, n: int = 3) -> list[str]:
        """兼容 v2.x 接口"""
        important = sorted(self.engrams.values(), key=lambda e: e.importance, reverse=True)
        return [e.content for e in important[:n]]
