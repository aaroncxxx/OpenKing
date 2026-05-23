"""帝国架构 v3.2 - 记忆系统升级：因果推理与跨Agent知识迁移
Forms-Functions-Dynamics 三维记忆框架（原有）+ 四大扩展模块：
- CausalMemoryGraph: 因果记忆图谱，支持因果推理与链式追溯
- ImperialLibrary:   帝国图书馆，跨Agent知识共享与版本控制
- MemoryDistiller:   记忆蒸馏，从历史记忆中提取通用规律
- ProactiveRetriever: 主动记忆检索，上下文驱动的相关记忆推送
"""
import json
import os
import re
import time
import math
import hashlib
import threading
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Callable, Any
from core.logger import get_logger

log = get_logger("memory3d")


# ═══════════════════════════════════════════════════════════════
#  原有模块：形式层 / 功能层 / 记忆条目 / Memory3D（完全向后兼容）
# ═══════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════
#  v3.2 扩展模块一：因果记忆图谱 (CausalMemoryGraph)
# ═══════════════════════════════════════════════════════════════


@dataclass
class CausalEdge:
    """因果关系边"""
    edge_id: str
    cause: str           # 原因节点标识
    effect: str          # 结果节点标识
    confidence: float    # 置信度 [0, 1]
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "cause": self.cause,
            "effect": self.effect,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CausalEdge":
        return cls(**d)


class CausalMemoryGraph:
    """因果记忆图谱

    支持因果关系的添加、正向推理（因→果）、反向追溯（果→因）、
    因果链可视化和 JSON 持久化。
    """

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "causal")
        os.makedirs(data_dir, exist_ok=True)
        self._path = os.path.join(data_dir, "causal_graph.json")
        self._lock = threading.Lock()

        # cause → [CausalEdge, ...]
        self._forward: dict[str, list[CausalEdge]] = defaultdict(list)
        # effect → [CausalEdge, ...]
        self._backward: dict[str, list[CausalEdge]] = defaultdict(list)
        # edge_id → CausalEdge
        self._edges: dict[str, CausalEdge] = {}

        self._load()

    # ── 持久化 ──

    def _load(self):
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for d in data.get("edges", []):
                edge = CausalEdge.from_dict(d)
                self._edges[edge.edge_id] = edge
                self._forward[edge.cause].append(edge)
                self._backward[edge.effect].append(edge)
        except Exception:
            pass

    def _save(self):
        try:
            data = {"edges": [e.to_dict() for e in self._edges.values()]}
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── 核心操作 ──

    def add_cause_effect(self, cause: str, effect: str,
                         confidence: float = 0.5,
                         metadata: dict = None) -> CausalEdge:
        """添加因果关系"""
        with self._lock:
            edge_id = hashlib.md5(
                f"{cause}->{effect}_{time.time()}".encode()
            ).hexdigest()[:12]

            edge = CausalEdge(
                edge_id=edge_id, cause=cause, effect=effect,
                confidence=max(0.0, min(1.0, confidence)),
                metadata=metadata or {},
            )
            self._edges[edge_id] = edge
            self._forward[cause].append(edge)
            self._backward[effect].append(edge)
            self._save()
            log.debug(f"因果关系: {cause} → {effect} (置信度={confidence:.2f})")
            return edge

    def infer_effects(self, cause: str, min_confidence: float = 0.0) -> list[tuple[str, float]]:
        """正向推理：给定原因，推理可能的结果

        Returns:
            [(effect, confidence), ...] 按置信度降序排列
        """
        results = []
        for edge in self._forward.get(cause, []):
            if edge.confidence >= min_confidence:
                results.append((edge.effect, edge.confidence))
        results.sort(key=lambda x: -x[1])
        return results

    def infer_causes(self, effect: str, min_confidence: float = 0.0) -> list[tuple[str, float]]:
        """反向追溯：给定结果，追溯可能的原因

        Returns:
            [(cause, confidence), ...] 按置信度降序排列
        """
        results = []
        for edge in self._backward.get(effect, []):
            if edge.confidence >= min_confidence:
                results.append((edge.cause, edge.confidence))
        results.sort(key=lambda x: -x[1])
        return results

    def infer_chain_forward(self, start: str, max_depth: int = 5,
                            min_confidence: float = 0.1) -> list[list[tuple[str, float]]]:
        """正向因果链推理：从起点展开因果树

        Returns:
            多条因果路径，每条为 [(node, cumulative_confidence), ...]
        """
        paths = []
        self._dfs_forward(start, [(start, 1.0)], paths, set(), max_depth, min_confidence)
        return paths

    def _dfs_forward(self, node, current_path, all_paths, visited, max_depth, min_confidence):
        if len(current_path) > max_depth:
            all_paths.append(list(current_path))
            return
        visited.add(node)
        edges = self._forward.get(node, [])
        found = False
        for edge in edges:
            cum_conf = current_path[-1][1] * edge.confidence
            if cum_conf < min_confidence or edge.effect in visited:
                continue
            found = True
            current_path.append((edge.effect, cum_conf))
            self._dfs_forward(edge.effect, current_path, all_paths, visited, max_depth, min_confidence)
            current_path.pop()
        if not found:
            all_paths.append(list(current_path))
        visited.discard(node)

    def visualize_chain(self, start: str, direction: str = "forward",
                        max_depth: int = 4, min_confidence: float = 0.1) -> str:
        """因果链可视化（文本树形格式）

        Args:
            start: 起始节点
            direction: "forward"（因→果）或 "backward"（果→因）
            max_depth: 最大深度
            min_confidence: 最小置信度阈值

        Returns:
            树形文本字符串
        """
        if direction == "forward":
            paths = self.infer_chain_forward(start, max_depth, min_confidence)
        else:
            paths = self._infer_chain_backward(start, max_depth, min_confidence)

        if not paths:
            return f"[{start}] 无因果关系"

        lines = [f"🌳 因果链 ({direction}): {start}"]
        for i, path in enumerate(paths):
            is_last_path = (i == len(paths) - 1)
            prefix = "└── " if is_last_path else "├── "
            for j, (node, conf) in enumerate(path[1:], 1):  # skip start
                indent = "    " * j if is_last_path else "│   " * j
                connector = "└── " if j == len(path) - 1 else "├── "
                if j == 1:
                    lines.append(f"{prefix}{node} [{conf:.0%}]")
                else:
                    lines.append(f"{indent}{connector}{node} [{conf:.0%}]")

        return "\n".join(lines)

    def _infer_chain_backward(self, start, max_depth, min_confidence):
        paths = []
        self._dfs_backward(start, [(start, 1.0)], paths, set(), max_depth, min_confidence)
        return paths

    def _dfs_backward(self, node, current_path, all_paths, visited, max_depth, min_confidence):
        if len(current_path) > max_depth:
            all_paths.append(list(current_path))
            return
        visited.add(node)
        edges = self._backward.get(node, [])
        found = False
        for edge in edges:
            cum_conf = current_path[-1][1] * edge.confidence
            if cum_conf < min_confidence or edge.cause in visited:
                continue
            found = True
            current_path.append((edge.cause, cum_conf))
            self._dfs_backward(edge.cause, current_path, all_paths, visited, max_depth, min_confidence)
            current_path.pop()
        if not found:
            all_paths.append(list(current_path))
        visited.discard(node)

    def get_all_nodes(self) -> set[str]:
        """获取所有节点"""
        nodes = set()
        for edge in self._edges.values():
            nodes.add(edge.cause)
            nodes.add(edge.effect)
        return nodes

    def remove_edge(self, edge_id: str) -> bool:
        """删除因果关系"""
        with self._lock:
            edge = self._edges.pop(edge_id, None)
            if edge is None:
                return False
            self._forward[edge.cause] = [e for e in self._forward[edge.cause] if e.edge_id != edge_id]
            self._backward[edge.effect] = [e for e in self._backward[edge.effect] if e.edge_id != edge_id]
            self._save()
            return True

    def get_stats(self) -> dict:
        return {
            "total_edges": len(self._edges),
            "total_nodes": len(self.get_all_nodes()),
            "forward_sources": len(self._forward),
            "backward_targets": len(self._backward),
        }


# ═══════════════════════════════════════════════════════════════
#  v3.2 扩展模块二：帝国图书馆 (ImperialLibrary)
# ═══════════════════════════════════════════════════════════════


@dataclass
class KnowledgeEntry:
    """知识条目"""
    knowledge_id: str
    content: str
    author: str              # 发布者 agent_id
    tags: list[str] = field(default_factory=list)
    category: str = "general"
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_control: list[str] = field(default_factory=list)  # 允许访问的 agent_id 列表，空 = 全局可见
    history: list[dict] = field(default_factory=list)         # 历史版本
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "knowledge_id": self.knowledge_id,
            "content": self.content,
            "author": self.author,
            "tags": self.tags,
            "category": self.category,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_control": self.access_control,
            "history": self.history,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeEntry":
        return cls(**d)


class ImperialLibrary:
    """帝国图书馆 - 跨 Agent 知识共享与管理

    功能：
    - 知识发布与搜索
    - 访问控制（授权/撤销）
    - 版本控制（历史版本 + 回滚）
    - 分类和标签体系
    """

    CATEGORIES = [
        "general", "technical", "strategy", "protocol",
        "experience", "pattern", "warning", "best_practice",
    ]

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "library")
        os.makedirs(data_dir, exist_ok=True)
        self._path = os.path.join(data_dir, "imperial_library.json")
        self._lock = threading.Lock()

        self._entries: dict[str, KnowledgeEntry] = {}
        self._tag_index: dict[str, set[str]] = defaultdict(set)     # tag → {knowledge_id}
        self._category_index: dict[str, set[str]] = defaultdict(set) # category → {knowledge_id}
        self._author_index: dict[str, set[str]] = defaultdict(set)   # author → {knowledge_id}

        self._load()

    # ── 持久化 ──

    def _load(self):
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for d in data.get("entries", []):
                entry = KnowledgeEntry.from_dict(d)
                self._entries[entry.knowledge_id] = entry
                self._rebuild_indexes(entry)
        except Exception:
            pass

    def _save(self):
        try:
            data = {"entries": [e.to_dict() for e in self._entries.values()]}
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _rebuild_indexes(self, entry: KnowledgeEntry):
        for tag in entry.tags:
            self._tag_index[tag].add(entry.knowledge_id)
        self._category_index[entry.category].add(entry.knowledge_id)
        self._author_index[entry.author].add(entry.knowledge_id)

    # ── 发布知识 ──

    def publish_knowledge(self, agent_id: str, content: str,
                          tags: list[str] = None,
                          category: str = "general",
                          metadata: dict = None) -> KnowledgeEntry:
        """发布知识到帝国图书馆

        Args:
            agent_id: 发布者 ID
            content: 知识内容
            tags: 标签列表
            category: 分类（见 CATEGORIES）
            metadata: 附加元数据

        Returns:
            创建的 KnowledgeEntry
        """
        with self._lock:
            kid = hashlib.md5(
                f"{agent_id}_{content[:80]}_{time.time()}".encode()
            ).hexdigest()[:14]

            entry = KnowledgeEntry(
                knowledge_id=kid,
                content=content,
                author=agent_id,
                tags=tags or [],
                category=category if category in self.CATEGORIES else "general",
                metadata=metadata or {},
            )

            self._entries[kid] = entry
            self._rebuild_indexes(entry)
            self._save()

            log.info(f"帝国图书馆: {agent_id} 发布知识 [{category}] {content[:60]}...")
            return entry

    # ── 更新知识（带版本控制）──

    def update_knowledge(self, knowledge_id: str, agent_id: str,
                         new_content: str = None,
                         new_tags: list[str] = None,
                         new_category: str = None) -> bool:
        """更新知识条目，自动保留历史版本"""
        with self._lock:
            entry = self._entries.get(knowledge_id)
            if entry is None:
                return False

            # 保存当前版本到历史
            entry.history.append({
                "version": entry.version,
                "content": entry.content,
                "tags": list(entry.tags),
                "category": entry.category,
                "updated_by": agent_id,
                "timestamp": entry.updated_at,
            })

            if new_content is not None:
                entry.content = new_content
            if new_tags is not None:
                # 更新标签索引
                for old_tag in entry.tags:
                    self._tag_index[old_tag].discard(knowledge_id)
                entry.tags = new_tags
                for tag in new_tags:
                    self._tag_index[tag].add(knowledge_id)
            if new_category is not None and new_category in self.CATEGORIES:
                self._category_index[entry.category].discard(knowledge_id)
                entry.category = new_category
                self._category_index[new_category].add(knowledge_id)

            entry.version += 1
            entry.updated_at = time.time()
            self._save()
            return True

    def rollback_knowledge(self, knowledge_id: str, target_version: int) -> bool:
        """回滚知识到指定版本"""
        with self._lock:
            entry = self._entries.get(knowledge_id)
            if entry is None or not entry.history:
                return False

            target = None
            for h in entry.history:
                if h["version"] == target_version:
                    target = h
                    break
            if target is None:
                return False

            # 保存当前版本
            entry.history.append({
                "version": entry.version,
                "content": entry.content,
                "tags": list(entry.tags),
                "category": entry.category,
                "updated_by": "rollback",
                "timestamp": entry.updated_at,
            })

            entry.content = target["content"]
            entry.tags = target.get("tags", entry.tags)
            entry.category = target.get("category", entry.category)
            entry.version += 1
            entry.updated_at = time.time()
            self._save()
            return True

    # ── 搜索知识 ──

    def search_knowledge(self, query: str, top_k: int = 5,
                         category: str = None,
                         tags: list[str] = None,
                         requester_id: str = None) -> list[KnowledgeEntry]:
        """搜索帝国图书馆

        Args:
            query: 搜索关键词
            top_k: 返回数量
            category: 过滤分类
            tags: 过滤标签（任一匹配）
            requester_id: 请求者 ID（用于访问控制）

        Returns:
            按相关性排序的知识条目列表
        """
        candidates = []
        query_lower = query.lower()
        query_words = set(query_lower.split()) if query_lower else set()

        for entry in self._entries.values():
            # 访问控制检查
            if requester_id and entry.access_control:
                if requester_id not in entry.access_control and requester_id != entry.author:
                    continue

            # 分类过滤
            if category and entry.category != category:
                continue

            # 标签过滤
            if tags and not set(tags) & set(entry.tags):
                continue

            # 计算相关性
            score = 0.0
            content_lower = entry.content.lower()
            content_words = set(content_lower.split())

            if query_words:
                overlap = query_words & content_words
                score += len(overlap) * 0.3

            # 标签匹配加分
            if tags:
                score += len(set(tags) & set(entry.tags)) * 0.4

            # 新鲜度加分
            age_hours = (time.time() - entry.updated_at) / 3600
            freshness = math.exp(-age_hours / 720)  # 30天半衰期
            score += freshness * 0.2

            # 版本数加分（更成熟的文档）
            score += min(0.1, entry.version * 0.02)

            candidates.append((entry, score))

        candidates.sort(key=lambda x: -x[1])
        return [e for e, _ in candidates[:top_k]]

    # ── 访问控制 ──

    def grant_access(self, agent_id: str, knowledge_id: str) -> bool:
        """授权 Agent 访问特定知识"""
        with self._lock:
            entry = self._entries.get(knowledge_id)
            if entry is None:
                return False
            if agent_id not in entry.access_control:
                entry.access_control.append(agent_id)
                self._save()
            return True

    def revoke_access(self, agent_id: str, knowledge_id: str) -> bool:
        """撤销 Agent 对特定知识的访问权限"""
        with self._lock:
            entry = self._entries.get(knowledge_id)
            if entry is None:
                return False
            if agent_id in entry.access_control:
                entry.access_control.remove(agent_id)
                self._save()
            return True

    def get_accessible_knowledge(self, agent_id: str) -> list[KnowledgeEntry]:
        """获取 Agent 可访问的所有知识"""
        result = []
        for entry in self._entries.values():
            if not entry.access_control or agent_id in entry.access_control or agent_id == entry.author:
                result.append(entry)
        return result

    # ── 查询接口 ──

    def get_by_id(self, knowledge_id: str) -> Optional[KnowledgeEntry]:
        return self._entries.get(knowledge_id)

    def get_by_tags(self, tags: list[str]) -> list[KnowledgeEntry]:
        ids = set()
        for tag in tags:
            ids |= self._tag_index.get(tag, set())
        return [self._entries[kid] for kid in ids if kid in self._entries]

    def get_by_category(self, category: str) -> list[KnowledgeEntry]:
        ids = self._category_index.get(category, set())
        return [self._entries[kid] for kid in ids if kid in self._entries]

    def get_by_author(self, agent_id: str) -> list[KnowledgeEntry]:
        ids = self._author_index.get(agent_id, set())
        return [self._entries[kid] for kid in ids if kid in self._entries]

    def get_version_history(self, knowledge_id: str) -> list[dict]:
        """获取知识的版本历史"""
        entry = self._entries.get(knowledge_id)
        if entry is None:
            return []
        return entry.history + ([{
            "version": entry.version,
            "content": entry.content,
            "tags": entry.tags,
            "category": entry.category,
            "timestamp": entry.updated_at,
            "status": "current",
        }] if entry.history else [])

    def get_stats(self) -> dict:
        cat_counts = {cat: len(ids) for cat, ids in self._category_index.items() if ids}
        return {
            "total_entries": len(self._entries),
            "categories": cat_counts,
            "total_tags": len(self._tag_index),
            "total_authors": len(self._author_index),
        }


# ═══════════════════════════════════════════════════════════════
#  v3.2 扩展模块三：记忆蒸馏器 (MemoryDistiller)
# ═══════════════════════════════════════════════════════════════


@dataclass
class Distillate:
    """蒸馏知识条目 - 从大量记忆中提取的通用规律"""
    distillate_id: str
    pattern: str           # 识别出的规律/模式描述
    evidence_count: int    # 支撑证据数量
    confidence: float      # 置信度 [0, 1]
    source_engrams: list[str] = field(default_factory=list)  # 来源 engram_id 列表
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    category: str = "general"  # frequency / co_occurrence / temporal / general

    def to_dict(self) -> dict:
        return {
            "distillate_id": self.distillate_id,
            "pattern": self.pattern,
            "evidence_count": self.evidence_count,
            "confidence": self.confidence,
            "source_engrams": self.source_engrams,
            "tags": self.tags,
            "created_at": self.created_at,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Distillate":
        return cls(**d)


class MemoryDistiller:
    """记忆蒸馏器

    从 Agent 的大量历史记忆中自动提取通用知识和规律：
    - 频率模式：反复出现的关键词/主题
    - 共现模式：经常一起出现的概念对
    - 时间模式：周期性规律
    - 输出结构化的 Distillate 条目
    """

    def __init__(self, memory: Memory3D, data_dir: str = None):
        self.memory = memory
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "distill")
        os.makedirs(data_dir, exist_ok=True)
        self._path = os.path.join(data_dir, f"{memory.agent_id}_distillates.json")
        self._lock = threading.Lock()

        self.distillates: list[Distillate] = []
        self._last_distill_time: float = 0
        self._distill_interval: float = 3600  # 默认 1 小时自动蒸馏一次

        self._load()

    def _load(self):
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for d in data.get("distillates", []):
                self.distillates.append(Distillate.from_dict(d))
            self._last_distill_time = data.get("last_distill_time", 0)
        except Exception:
            pass

    def _save(self):
        try:
            data = {
                "distillates": [d.to_dict() for d in self.distillates],
                "last_distill_time": self._last_distill_time,
            }
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── 核心蒸馏 ──

    def distill(self, agent_id: str = None, min_evidence: int = 2,
                min_confidence: float = 0.3) -> list[Distillate]:
        """从历史记忆中蒸馏通用知识

        Args:
            agent_id: 指定 Agent（未使用，保留接口一致性）
            min_evidence: 最小证据数
            min_confidence: 最小置信度

        Returns:
            新生成的 Distillate 列表
        """
        engrams = list(self.memory.engrams.values())
        if len(engrams) < 3:
            return []

        new_distillates = []

        # 1. 频率模式分析
        freq_patterns = self._analyze_frequency(engrams, min_evidence)
        for pattern, count, source_ids in freq_patterns:
            conf = min(1.0, count / max(len(engrams), 1) * 2)
            if conf >= min_confidence:
                new_distillates.append(Distillate(
                    distillate_id=hashlib.md5(f"freq_{pattern}_{time.time()}".encode()).hexdigest()[:12],
                    pattern=pattern,
                    evidence_count=count,
                    confidence=conf,
                    source_engrams=source_ids,
                    tags=["frequency"],
                    category="frequency",
                ))

        # 2. 共现模式分析
        co_patterns = self._analyze_co_occurrence(engrams, min_evidence)
        for (concept_a, concept_b), count, source_ids in co_patterns:
            conf = min(1.0, count / max(len(engrams), 1) * 3)
            if conf >= min_confidence:
                new_distillates.append(Distillate(
                    distillate_id=hashlib.md5(f"co_{concept_a}_{concept_b}_{time.time()}".encode()).hexdigest()[:12],
                    pattern=f"{concept_a} 与 {concept_b} 经常同时出现",
                    evidence_count=count,
                    confidence=conf,
                    source_engrams=source_ids,
                    tags=[concept_a, concept_b, "co_occurrence"],
                    category="co_occurrence",
                ))

        # 3. 标签聚类分析
        tag_patterns = self._analyze_tag_clusters(engrams, min_evidence)
        for tag_group, count, source_ids in tag_patterns:
            conf = min(1.0, count / max(len(engrams), 1) * 2.5)
            if conf >= min_confidence:
                new_distillates.append(Distillate(
                    distillate_id=hashlib.md5(f"tag_{'_'.join(tag_group)}_{time.time()}".encode()).hexdigest()[:12],
                    pattern=f"标签聚类: {', '.join(tag_group)}",
                    evidence_count=count,
                    confidence=conf,
                    source_engrams=source_ids,
                    tags=list(tag_group),
                    category="general",
                ))

        with self._lock:
            # 去重：检查是否已有相似的 distillate
            existing_patterns = {d.pattern for d in self.distillates}
            for d in new_distillates:
                if d.pattern not in existing_patterns:
                    self.distillates.append(d)

            self._last_distill_time = time.time()
            self._save()

        log.info(f"记忆蒸馏完成: {len(new_distillates)} 条新规律 (共 {len(self.distillates)} 条)")
        return new_distillates

    def _tokenize(self, text: str) -> list[str]:
        """简单分词"""
        text = text.lower()
        words = re.findall(r'[\w\u4e00-\u9fff]+', text)
        # 过滤停用词
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
            'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'and', 'but', 'or',
            'not', 'no', 'nor', 'so', 'yet', 'both', 'either', 'neither', 'each',
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都',
            '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你',
        }
        return [w for w in words if len(w) > 1 and w not in stopwords]

    def _analyze_frequency(self, engrams: list[MemoryEngram],
                           min_count: int) -> list[tuple[str, int, list[str]]]:
        """分析高频关键词/主题"""
        word_count: dict[str, int] = defaultdict(int)
        word_sources: dict[str, list[str]] = defaultdict(list)

        for e in engrams:
            tokens = set(self._tokenize(e.content))
            for token in tokens:
                word_count[token] += 1
                if len(word_sources[token]) < 10:
                    word_sources[token].append(e.engram_id)

        results = []
        for word, count in sorted(word_count.items(), key=lambda x: -x[1]):
            if count >= min_count:
                results.append((f"主题「{word}」频繁出现 (出现 {count} 次)", count, word_sources[word]))
        return results[:20]  # 最多 20 条

    def _analyze_co_occurrence(self, engrams: list[MemoryEngram],
                               min_count: int) -> list[tuple[tuple[str, str], int, list[str]]]:
        """分析概念共现模式"""
        pair_count: dict[tuple[str, str], int] = defaultdict(int)
        pair_sources: dict[tuple[str, str], list[str]] = defaultdict(list)

        for e in engrams:
            tokens = sorted(set(self._tokenize(e.content)))
            # 限制组合数
            if len(tokens) > 15:
                tokens = tokens[:15]
            for i in range(len(tokens)):
                for j in range(i + 1, len(tokens)):
                    pair = (tokens[i], tokens[j])
                    pair_count[pair] += 1
                    if len(pair_sources[pair]) < 5:
                        pair_sources[pair].append(e.engram_id)

        results = []
        for pair, count in sorted(pair_count.items(), key=lambda x: -x[1]):
            if count >= min_count:
                results.append((pair, count, pair_sources[pair]))
        return results[:15]

    def _analyze_tag_clusters(self, engrams: list[MemoryEngram],
                              min_count: int) -> list[tuple[tuple[str, ...], int, list[str]]]:
        """分析标签聚类"""
        tag_combo_count: dict[tuple[str, ...], int] = defaultdict(int)
        tag_combo_sources: dict[tuple[str, ...], list[str]] = defaultdict(list)

        for e in engrams:
            if len(e.tags) < 2:
                continue
            tags = sorted(e.tags)
            if len(tags) > 5:
                tags = tags[:5]
            # 两两组合
            for i in range(len(tags)):
                for j in range(i + 1, len(tags)):
                    combo = (tags[i], tags[j])
                    tag_combo_count[combo] += 1
                    if len(tag_combo_sources[combo]) < 5:
                        tag_combo_sources[combo].append(e.engram_id)

        results = []
        for combo, count in sorted(tag_combo_count.items(), key=lambda x: -x[1]):
            if count >= min_count:
                results.append((combo, count, tag_combo_sources[combo]))
        return results[:10]

    # ── 自动蒸馏 ──

    def auto_distill_if_needed(self) -> list[Distillate]:
        """定期自动蒸馏（应在 lifecycle_tick 中调用）"""
        now = time.time()
        if now - self._last_distill_time >= self._distill_interval:
            return self.distill()
        return []

    def set_distill_interval(self, seconds: float):
        """设置自动蒸馏间隔"""
        self._distill_interval = max(60, seconds)

    # ── 查询 ──

    def get_distillates(self, category: str = None,
                        min_confidence: float = 0.0) -> list[Distillate]:
        """获取蒸馏结果"""
        results = []
        for d in self.distillates:
            if category and d.category != category:
                continue
            if d.confidence >= min_confidence:
                results.append(d)
        results.sort(key=lambda x: -x.confidence)
        return results

    def get_distillate_summary(self) -> str:
        """获取蒸馏知识摘要（可注入 prompt）"""
        if not self.distillates:
            return ""

        lines = ["【蒸馏知识】"]
        by_category = defaultdict(list)
        for d in self.distillates:
            by_category[d.category].append(d)

        for cat, distillates in by_category.items():
            cat_name = {"frequency": "高频规律", "co_occurrence": "关联模式",
                        "temporal": "时间规律", "general": "通用规律"}.get(cat, cat)
            top = sorted(distillates, key=lambda d: -d.confidence)[:5]
            lines.append(f"  {cat_name}:")
            for d in top:
                lines.append(f"    · {d.pattern} [置信度 {d.confidence:.0%}]")

        return "\n".join(lines)

    def get_stats(self) -> dict:
        cat_counts = defaultdict(int)
        for d in self.distillates:
            cat_counts[d.category] += 1
        return {
            "total_distillates": len(self.distillates),
            "by_category": dict(cat_counts),
            "last_distill": self._last_distill_time,
            "interval_seconds": self._distill_interval,
        }


# ═══════════════════════════════════════════════════════════════
#  v3.2 扩展模块四：主动记忆检索器 (ProactiveRetriever)
# ═══════════════════════════════════════════════════════════════


@dataclass
class TriggerRule:
    """触发规则"""
    rule_id: str
    keywords: list[str]        # 触发关键词
    callback: Optional[Callable] = None  # 回调函数
    description: str = ""
    priority: int = 0          # 优先级，越高越先触发
    cooldown: float = 60.0     # 冷却时间（秒）
    last_triggered: float = 0
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "keywords": self.keywords,
            "description": self.description,
            "priority": self.priority,
            "cooldown": self.cooldown,
            "last_triggered": self.last_triggered,
            "enabled": self.enabled,
        }


class ProactiveRetriever:
    """主动记忆检索器

    当上下文变化时主动检索相关记忆，支持：
    - 关键词触发规则
    - 语义相似度匹配
    - 回调通知机制
    - 与 Memory3D.retrieve() 深度集成
    """

    def __init__(self, memory: Memory3D, data_dir: str = None):
        self.memory = memory
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "proactive")
        os.makedirs(data_dir, exist_ok=True)
        self._path = os.path.join(data_dir, f"{memory.agent_id}_triggers.json")
        self._lock = threading.Lock()

        self._rules: dict[str, TriggerRule] = {}
        self._history: list[dict] = []  # 检索历史
        self._max_history = 200

        self._load()

    def _load(self):
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for d in data.get("rules", []):
                rule = TriggerRule(**d)
                self._rules[rule.rule_id] = rule
        except Exception:
            pass

    def _save(self):
        try:
            data = {"rules": [r.to_dict() for r in self._rules.values()]}
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── 触发规则管理 ──

    def register_trigger(self, keywords: list[str],
                         callback: Optional[Callable] = None,
                         description: str = "",
                         priority: int = 0,
                         cooldown: float = 60.0) -> TriggerRule:
        """注册触发规则

        Args:
            keywords: 触发关键词列表
            callback: 触发时的回调函数 callback(memories: list[MemoryEngram])
            description: 规则描述
            priority: 优先级
            cooldown: 冷却时间（秒）

        Returns:
            创建的 TriggerRule
        """
        with self._lock:
            rule_id = hashlib.md5(
                f"{'_'.join(keywords)}_{time.time()}".encode()
            ).hexdigest()[:10]

            rule = TriggerRule(
                rule_id=rule_id,
                keywords=[kw.lower() for kw in keywords],
                callback=callback,
                description=description,
                priority=priority,
                cooldown=cooldown,
            )

            self._rules[rule_id] = rule
            self._save()
            log.debug(f"注册触发规则: {keywords} -> {description or rule_id}")
            return rule

    def remove_trigger(self, rule_id: str) -> bool:
        """移除触发规则"""
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                self._save()
                return True
            return False

    def enable_trigger(self, rule_id: str) -> bool:
        with self._lock:
            rule = self._rules.get(rule_id)
            if rule:
                rule.enabled = True
                self._save()
                return True
            return False

    def disable_trigger(self, rule_id: str) -> bool:
        with self._lock:
            rule = self._rules.get(rule_id)
            if rule:
                rule.enabled = False
                self._save()
                return True
            return False

    # ── 主动检索核心 ──

    def on_context_change(self, context: str) -> list[MemoryEngram]:
        """上下文变化时的主动检索

        1. 匹配触发规则
        2. 对每个匹配的规则执行检索
        3. 调用回调（如有）
        4. 记录历史

        Args:
            context: 当前上下文文本

        Returns:
            所有匹配触发规则检索到的记忆（去重，按相关性排序）
        """
        now = time.time()
        context_lower = context.lower()
        context_words = set(context_lower.split())

        matched_results: dict[str, MemoryEngram] = {}  # engram_id → engram
        triggered_rules = []

        # 按优先级排序检查规则
        sorted_rules = sorted(self._rules.values(), key=lambda r: -r.priority)

        for rule in sorted_rules:
            if not rule.enabled:
                continue

            # 冷却检查
            if now - rule.last_triggered < rule.cooldown:
                continue

            # 关键词匹配
            matched_keywords = set(rule.keywords) & context_words
            if not matched_keywords:
                # 也检查子串匹配
                for kw in rule.keywords:
                    if kw in context_lower:
                        matched_keywords.add(kw)
                        break

            if not matched_keywords:
                continue

            # 触发！
            rule.last_triggered = now
            triggered_rules.append(rule)

            # 执行检索
            query = " ".join(matched_keywords)
            memories = self.memory.retrieve(query, top_k=5)
            for m in memories:
                matched_results[m.engram_id] = m

            # 调用回调
            if rule.callback:
                try:
                    rule.callback(memories)
                except Exception as ex:
                    log.warning(f"触发规则回调异常: {ex}")

        # 记录历史
        if triggered_rules:
            self._history.append({
                "timestamp": now,
                "context_preview": context[:200],
                "triggered_rules": [r.rule_id for r in triggered_rules],
                "results_count": len(matched_results),
            })
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        self._save()

        # 按相关性排序返回
        results = list(matched_results.values())
        results.sort(key=lambda e: -self.memory._compute_relevance(context, e))
        return results

    def keyword_scan(self, text: str) -> list[TriggerRule]:
        """扫描文本，返回匹配的规则（不触发检索，仅检查）"""
        text_lower = text.lower()
        text_words = set(text_lower.split())
        matched = []
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            for kw in rule.keywords:
                if kw in text_words or kw in text_lower:
                    matched.append(rule)
                    break
        matched.sort(key=lambda r: -r.priority)
        return matched

    # ── 集成接口 ──

    def retrieve_proactive(self, query: str, top_k: int = 5,
                           include_triggers: bool = True) -> list[MemoryEngram]:
        """增强版检索：结合标准检索和触发规则

        Args:
            query: 检索查询
            top_k: 返回数量
            include_triggers: 是否同时检查触发规则

        Returns:
            去重后的记忆列表
        """
        # 标准检索
        standard_results = self.memory.retrieve(query, top_k=top_k)
        result_map = {e.engram_id: e for e in standard_results}

        if include_triggers:
            proactive_results = self.on_context_change(query)
            for e in proactive_results:
                if e.engram_id not in result_map:
                    result_map[e.engram_id] = e

        results = list(result_map.values())
        results.sort(key=lambda e: -self.memory._compute_relevance(query, e))
        return results[:top_k]

    # ── 查询 ──

    def get_rules(self, enabled_only: bool = False) -> list[TriggerRule]:
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        rules.sort(key=lambda r: -r.priority)
        return rules

    def get_history(self, limit: int = 20) -> list[dict]:
        return self._history[-limit:]

    def get_stats(self) -> dict:
        return {
            "total_rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules.values() if r.enabled),
            "history_count": len(self._history),
        }
