"""帝国架构 v3.2 - 自主执行增强

升级内容：
  - GoTPlanner: Graph of Thoughts 思维图规划器
  - DynamicScheduler: 动态资源调度（复杂度感知 + DAG-Shapley）
  - CheckpointManager: 断点续传（持久化快照 + 暂停/恢复/迁移）
  - SelfHealer 增强: 指数退避 / 熔断器 / 优雅降级 / 异常分类
  - 向后兼容: AutonomousEngine / ParallelOrchestrator / SelfHealer 原有 API 不变
"""
import asyncio
import json
import os
import time
import hashlib
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from core.logger import get_logger

log = get_logger("autonomous")

# ═══════════════════════════════════════════════════════════════
# 异常分类枚举
# ═══════════════════════════════════════════════════════════════


class ErrorCategory(Enum):
    """异常分类 - 不同类型对应不同恢复策略"""
    NETWORK = "network"
    TIMEOUT = "timeout"
    MODEL = "model"
    PERMISSION = "permission"
    RESOURCE = "resource"
    UNKNOWN = "unknown"


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class ModelTier(Enum):
    """模型等级"""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


# ═══════════════════════════════════════════════════════════════
# GoTPlanner - Graph of Thoughts 思维图规划器
# ═══════════════════════════════════════════════════════════════


@dataclass
class ThoughtNode:
    """思维图节点 = 一个思考步骤"""
    node_id: str
    content: str
    node_type: str = "reasoning"          # reasoning | decomposition | refinement | aggregation
    complexity: float = 0.5               # 0.0 ~ 1.0
    dependencies: list[str] = field(default_factory=list)   # 前置节点 ID
    metadata: dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None


@dataclass
class ThoughtEdge:
    """思维图边 = 依赖 / 增强关系"""
    source: str
    target: str
    edge_type: str = "dependency"         # dependency | enhancement | alternative
    weight: float = 1.0


class GoTPlanner:
    """Graph of Thoughts 规划器

    将复杂目标分解为思维图（有向无环图），而非线性链。
    支持：
      - 多条推理路径并行探索
      - 拓扑排序获取执行顺序
      - 路径合并 / 结果聚合
      - 循环检测与图优化
      - 与现有 ParallelOrchestrator DAG 调度器兼容
    """

    def __init__(self):
        self.nodes: dict[str, ThoughtNode] = {}
        self.edges: list[ThoughtEdge] = []
        self._adj: dict[str, list[str]] = defaultdict(list)   # 邻接表
        self._rev_adj: dict[str, list[str]] = defaultdict(list)  # 反向邻接表

    # ── 构建思维图 ────────────────────────────────────────────

    def build_graph(self, goal: str) -> dict[str, ThoughtNode]:
        """将复杂目标分解为思维图

        分解策略：
          1. 根节点 = 原始目标
          2. 第一层 = 目标分解（decomposition）
          3. 第二层 = 各子问题独立推理（reasoning）
          4. 第三层 = 结果精炼（refinement）
          5. 汇总节点 = 多路径聚合（aggregation）
        """
        self.nodes.clear()
        self.edges.clear()
        self._adj.clear()
        self._rev_adj.clear()

        # 根节点
        root_id = "root"
        self._add_node(ThoughtNode(
            node_id=root_id,
            content=goal,
            node_type="decomposition",
            complexity=1.0,
        ))

        # 自动分解子目标（基于目标长度和复杂度启发式）
        sub_goals = self._decompose_goal(goal)
        for i, sg in enumerate(sub_goals):
            sg_id = f"sub_{i}"
            self._add_node(ThoughtNode(
                node_id=sg_id,
                content=sg,
                node_type="reasoning",
                complexity=self._estimate_node_complexity(sg),
                dependencies=[root_id],
            ))
            self._add_edge(ThoughtEdge(source=root_id, target=sg_id, edge_type="dependency"))

        # 为每个子目标生成推理路径
        for i, sg in enumerate(sub_goals):
            sg_id = f"sub_{i}"
            refine_id = f"refine_{i}"
            self._add_node(ThoughtNode(
                node_id=refine_id,
                content=f"精炼: {sg}",
                node_type="refinement",
                complexity=self._estimate_node_complexity(sg) * 0.8,
                dependencies=[sg_id],
            ))
            self._add_edge(ThoughtEdge(source=sg_id, target=refine_id, edge_type="dependency"))

        # 增强边：识别跨子目标的关联
        self._detect_enhancement_links(sub_goals)

        # 聚合节点
        agg_id = "aggregate"
        refine_ids = [f"refine_{i}" for i in range(len(sub_goals))]
        self._add_node(ThoughtNode(
            node_id=agg_id,
            content=f"聚合结果: {goal}",
            node_type="aggregation",
            complexity=0.6,
            dependencies=refine_ids,
        ))
        for rid in refine_ids:
            self._add_edge(ThoughtEdge(source=rid, target=agg_id, edge_type="dependency"))

        return self.nodes

    def _decompose_goal(self, goal: str) -> list[str]:
        """启发式目标分解"""
        # 简单实现：按标点 / 关键词拆分，实际场景由 LLM 驱动
        separators = ["；", "并且", "同时", "另外", "此外", "然后", "接着", "最后"]
        parts = [goal]
        for sep in separators:
            new_parts = []
            for p in parts:
                new_parts.extend([s.strip() for s in p.split(sep) if s.strip()])
            parts = new_parts

        if len(parts) < 2:
            # 长目标拆为 2-3 个子任务
            mid = len(goal) // 2
            space_pos = goal.find("，", mid)
            if space_pos == -1:
                space_pos = goal.find(" ", mid)
            if space_pos > 0:
                parts = [goal[:space_pos], goal[space_pos + 1:]]
            else:
                parts = [goal]

        return parts[:5]  # 最多 5 个子目标

    def _estimate_node_complexity(self, text: str) -> float:
        """启发式估算节点复杂度"""
        score = min(len(text) / 500, 0.5)
        keywords = ["分析", "设计", "优化", "重构", "架构", "系统", "算法", "策略", "决策"]
        for kw in keywords:
            if kw in text:
                score += 0.1
        return min(score, 1.0)

    def _detect_enhancement_links(self, sub_goals: list[str]):
        """检测子目标之间的增强关系"""
        for i in range(len(sub_goals)):
            for j in range(i + 1, len(sub_goals)):
                # 简单：共享关键词则建立增强边
                words_i = set(sub_goals[i])
                words_j = set(sub_goals[j])
                overlap = len(words_i & words_j)
                if overlap > 3:
                    self._add_edge(ThoughtEdge(
                        source=f"sub_{i}",
                        target=f"sub_{j}",
                        edge_type="enhancement",
                        weight=overlap / max(len(words_i), len(words_j), 1),
                    ))

    # ── 图操作 ────────────────────────────────────────────────

    def _add_node(self, node: ThoughtNode):
        self.nodes[node.node_id] = node

    def _add_edge(self, edge: ThoughtEdge):
        self.edges.append(edge)
        self._adj[edge.source].append(edge.target)
        self._rev_adj[edge.target].append(edge.source)
        # 更新依赖
        if edge.edge_type == "dependency" and edge.source in self.nodes:
            target = self.nodes.get(edge.target)
            if target and edge.source not in target.dependencies:
                target.dependencies.append(edge.source)

    def has_cycle(self) -> bool:
        """检测图中是否存在循环（Kahn 算法）"""
        in_degree = defaultdict(int)
        for node_id in self.nodes:
            in_degree[node_id] = len(self._rev_adj.get(node_id, []))

        queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
        visited = 0

        while queue:
            nid = queue.popleft()
            visited += 1
            for neighbor in self._adj.get(nid, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return visited != len(self.nodes)

    def get_execution_order(self) -> list[str]:
        """拓扑排序获取执行顺序（Kahn 算法）

        与 ParallelOrchestrator.build_dependency_graph 兼容：
          返回的列表中，同一批次的节点可并行执行。
        """
        if self.has_cycle():
            log.warning("思维图存在循环，尝试移除最小反馈边集")
            self._break_cycles()

        in_degree = defaultdict(int)
        for node_id in self.nodes:
            in_degree[node_id] = len(self._rev_adj.get(node_id, []))

        queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
        order = []

        while queue:
            # 按复杂度降序排列（优先处理高复杂度节点）
            batch = sorted(queue, key=lambda n: -self.nodes[n].complexity)
            queue.clear()
            for nid in batch:
                order.append(nid)
                for neighbor in self._adj.get(nid, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        return order

    def _break_cycles(self):
        """移除最小反馈边集以打破循环（贪心策略）"""
        # 简单实现：迭代移除入度最大的节点的某条入边
        removed = True
        while removed and self.has_cycle():
            removed = False
            in_deg = {nid: len(self._rev_adj.get(nid, [])) for nid in self.nodes}
            max_node = max(in_deg, key=in_deg.get) if in_deg else None
            if max_node and in_deg[max_node] > 0:
                # 移除权重最低的入边
                rev_edges = [e for e in self.edges if e.target == max_node]
                if rev_edges:
                    weakest = min(rev_edges, key=lambda e: e.weight)
                    self.edges.remove(weakest)
                    if weakest.target in self._adj.get(weakest.source, []):
                        self._adj[weakest.source].remove(weakest.target)
                    if weakest.source in self._rev_adj.get(weakest.target, []):
                        self._rev_adj[weakest.target].remove(weakest.source)
                    removed = True

    def merge_paths(self, paths: list[list[str]]) -> dict[str, Any]:
        """合并多条推理路径的结果

        策略：
          - 共识节点（多路径都经过）→ 高置信度
          - 独占节点（仅一条路径）→ 低置信度
          - 聚合节点综合所有上游结果
        """
        node_visit_count: dict[str, int] = defaultdict(int)
        path_results: dict[str, list[str]] = defaultdict(list)

        for path in paths:
            for nid in path:
                node_visit_count[nid] += 1
                node = self.nodes.get(nid)
                if node and node.result:
                    path_results[nid].append(node.result)

        merged = {}
        for nid, count in node_visit_count.items():
            node = self.nodes.get(nid)
            if not node:
                continue
            confidence = min(count / len(paths), 1.0) if paths else 0.0
            merged[nid] = {
                "content": node.content,
                "node_type": node.node_type,
                "visit_count": count,
                "confidence": round(confidence, 2),
                "results": path_results.get(nid, []),
            }

        return merged

    def get_parallel_layers(self) -> list[list[str]]:
        """返回可并行执行的层级（兼容 ParallelOrchestrator）"""
        in_degree = defaultdict(int)
        for node_id in self.nodes:
            in_degree[node_id] = len(self._rev_adj.get(node_id, []))

        layers = []
        current_layer = [nid for nid, deg in in_degree.items() if deg == 0]

        while current_layer:
            layers.append(sorted(current_layer))
            next_layer = []
            for nid in current_layer:
                for neighbor in self._adj.get(nid, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_layer.append(neighbor)
            current_layer = next_layer

        return layers

    def to_dict(self) -> dict:
        """序列化为字典（兼容 DAG 调度器）"""
        return {
            "nodes": {nid: asdict(n) for nid, n in self.nodes.items()},
            "edges": [asdict(e) for e in self.edges],
            "execution_order": self.get_execution_order(),
            "parallel_layers": self.get_parallel_layers(),
        }


# ═══════════════════════════════════════════════════════════════
# DynamicScheduler - 动态资源调度
# ═══════════════════════════════════════════════════════════════


@dataclass
class ScheduledTask:
    """调度任务"""
    task_id: str
    description: str
    priority: TaskPriority = TaskPriority.MEDIUM
    complexity: float = 0.5
    model_tier: ModelTier = ModelTier.MEDIUM
    allocated_agents: list[str] = field(default_factory=list)
    deadline: Optional[float] = None
    preemptible: bool = True


class DynamicScheduler:
    """动态资源调度器

    根据任务复杂度自动选择模型等级、分配 Agent 数量。
    支持：
      - 复杂度感知的模型选择
      - DAG-Shapley 贡献度资源配额
      - 优先级队列 + 抢占式调度
    """

    # 复杂度 → 模型等级映射
    COMPLEXITY_TIER_MAP = {
        (0.0, 0.3): ModelTier.SMALL,
        (0.3, 0.7): ModelTier.MEDIUM,
        (0.7, 1.01): ModelTier.LARGE,
    }

    # 模型等级 → 基础 Agent 数量
    TIER_AGENT_MAP = {
        ModelTier.SMALL: 1,
        ModelTier.MEDIUM: 2,
        ModelTier.LARGE: 4,
    }

    def __init__(self):
        self._priority_queue: list[ScheduledTask] = []
        self._shapley_cache: dict[str, dict[str, float]] = {}  # dag_id → {agent_id: shapley_value}
        self._running: dict[str, ScheduledTask] = {}  # task_id → task

    def estimate_complexity(self, task: str) -> float:
        """估算任务复杂度（0.0 ~ 1.0）

        启发式规则：
          - 文本长度
          - 关键词权重
          - 结构复杂度（代码块、列表等）
        """
        score = 0.0

        # 长度因子
        length_score = min(len(task) / 1000, 0.3)
        score += length_score

        # 关键词因子
        high_complexity_kw = ["架构", "系统", "算法", "优化", "重构", "分布式", "并发", "安全", "机器学习", "深度学习"]
        medium_complexity_kw = ["分析", "设计", "实现", "测试", "部署", "集成", "配置"]
        low_complexity_kw = ["查询", "查看", "列出", "显示", "获取", "读取"]

        for kw in high_complexity_kw:
            if kw in task:
                score += 0.15
        for kw in medium_complexity_kw:
            if kw in task:
                score += 0.08
        for kw in low_complexity_kw:
            if kw in task:
                score -= 0.05

        # 结构复杂度
        if "```" in task:
            score += 0.1
        if task.count("\n") > 10:
            score += 0.05
        if any(c in task for c in ["{", "}", "(", ")", "[", "]"]):
            score += 0.05

        return max(0.0, min(1.0, score))

    def allocate_for_task(self, task: str, available_agents: set[str]) -> ScheduledTask:
        """动态分配 Agent

        1. 估算复杂度 → 选择模型等级
        2. 根据等级决定 Agent 数量
        3. 基于 DAG-Shapley 贡献度选择最优 Agent 组合
        """
        complexity = self.estimate_complexity(task)
        model_tier = self._select_tier(complexity)
        target_count = self.TIER_AGENT_MAP[model_tier]

        # 优先使用 Shapley 贡献度高的 Agent
        agent_list = list(available_agents)
        if agent_list:
            shapley_scores = self._get_shapley_scores(agent_list)
            agent_list.sort(key=lambda a: shapley_scores.get(a, 0.5), reverse=True)

        allocated = agent_list[:target_count] if agent_list else []

        task_obj = ScheduledTask(
            task_id=hashlib.md5(task.encode()).hexdigest()[:12],
            description=task,
            complexity=complexity,
            model_tier=model_tier,
            allocated_agents=allocated,
        )

        log.info(
            f"调度: 复杂度={complexity:.2f}, 模型={model_tier.value}, "
            f"Agent数={len(allocated)}, 节点={allocated}"
        )
        return task_obj

    def _select_tier(self, complexity: float) -> ModelTier:
        """根据复杂度选择模型等级"""
        for (lo, hi), tier in self.COMPLEXITY_TIER_MAP.items():
            if lo <= complexity < hi:
                return tier
        return ModelTier.LARGE

    def _get_shapley_scores(self, agents: list[str]) -> dict[str, float]:
        """基于 DAG-Shapley 值计算 Agent 贡献度

        Shapley 值 = 每个 Agent 对所有可能联盟的边际贡献的加权平均。
        简化实现：基于历史任务成功率。
        """
        scores = {}
        for agent in agents:
            # 从缓存中取，不存在则用默认值
            all_scores = []
            for dag_scores in self._shapley_cache.values():
                if agent in dag_scores:
                    all_scores.append(dag_scores[agent])
            scores[agent] = sum(all_scores) / len(all_scores) if all_scores else 0.5
        return scores

    def update_shapley(self, dag_id: str, agent_contributions: dict[str, float]):
        """更新 DAG-Shapley 贡献度缓存"""
        self._shapley_cache[dag_id] = agent_contributions

    # ── 优先级队列 + 抢占式调度 ──────────────────────────────

    def enqueue(self, task: ScheduledTask):
        """入队（按优先级插入）"""
        self._priority_queue.append(task)
        self._priority_queue.sort(key=lambda t: t.priority.value)

    def dequeue(self) -> Optional[ScheduledTask]:
        """出队（最高优先级）"""
        return self._priority_queue.pop(0) if self._priority_queue else None

    def preempt(self, incoming: ScheduledTask) -> Optional[str]:
        """抢占式调度

        如果新任务优先级更高，抢占当前最低优先级的运行任务。
        返回被抢占的任务 ID（如果没有发生抢占则返回 None）。
        """
        if not self._running:
            return None

        # 找到当前运行中优先级最低且可抢占的任务
        preemptable = [
            (tid, t) for tid, t in self._running.items()
            if t.preemptible and t.priority.value > incoming.priority.value
        ]

        if not preemptable:
            return None

        # 抢占优先级最低的
        preemptable.sort(key=lambda x: x[1].priority.value, reverse=True)
        victim_id, victim_task = preemptable[0]
        del self._running[victim_id]

        log.info(f"抢占: {victim_id} (优先级 {victim_task.priority.name}) → {incoming.task_id}")
        return victim_id

    def start_task(self, task: ScheduledTask):
        """标记任务开始运行"""
        self._running[task.task_id] = task

    def finish_task(self, task_id: str):
        """标记任务完成"""
        self._running.pop(task_id, None)

    def get_queue_status(self) -> dict:
        """获取队列状态"""
        return {
            "queued": len(self._priority_queue),
            "running": len(self._running),
            "tasks": [
                {"id": t.task_id, "priority": t.priority.name, "tier": t.model_tier.value}
                for t in self._priority_queue
            ],
            "running_tasks": [
                {"id": t.task_id, "priority": t.priority.name, "agents": t.allocated_agents}
                for t in self._running.values()
            ],
        }


# ═══════════════════════════════════════════════════════════════
# CheckpointManager - 断点续传
# ═══════════════════════════════════════════════════════════════


@dataclass
class Checkpoint:
    """检查点数据"""
    task_id: str
    state: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    status: str = "paused"                # paused | running | completed | migrated
    metadata: dict[str, Any] = field(default_factory=dict)


class CheckpointManager:
    """断点续传管理器

    支持：
      - 任务状态快照保存 / 恢复
      - 暂停 / 恢复 / 迁移
      - JSON 文件持久化
      - 自动清理过期检查点
    """

    DEFAULT_CHECKPOINT_DIR = "checkpoints"
    DEFAULT_TTL = 86400 * 7  # 7 天过期

    def __init__(self, checkpoint_dir: Optional[str] = None, ttl: float = DEFAULT_TTL):
        self._dir = Path(checkpoint_dir or self.DEFAULT_CHECKPOINT_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ttl = ttl
        self._cache: dict[str, Checkpoint] = {}
        self._load_all()

    def _load_all(self):
        """启动时加载所有检查点到缓存"""
        for f in self._dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                cp = Checkpoint(**data)
                self._cache[cp.task_id] = cp
            except Exception as e:
                log.warning(f"加载检查点失败: {f.name} - {e}")

    def _path_for(self, task_id: str) -> Path:
        safe_id = task_id.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe_id}.json"

    def save_checkpoint(self, task_id: str, state: dict[str, Any], metadata: Optional[dict] = None) -> Checkpoint:
        """保存任务状态快照"""
        cp = Checkpoint(
            task_id=task_id,
            state=state,
            timestamp=time.time(),
            status="paused",
            metadata=metadata or {},
        )
        self._cache[task_id] = cp
        self._persist(cp)
        log.info(f"检查点已保存: {task_id}")
        return cp

    def load_checkpoint(self, task_id: str) -> Optional[Checkpoint]:
        """恢复任务状态"""
        cp = self._cache.get(task_id)
        if cp:
            log.info(f"检查点已加载: {task_id} (状态={cp.status})")
        else:
            log.warning(f"检查点不存在: {task_id}")
        return cp

    def list_checkpoints(self, status_filter: Optional[str] = None) -> list[dict]:
        """列出所有检查点"""
        result = []
        for cp in self._cache.values():
            if status_filter and cp.status != status_filter:
                continue
            result.append({
                "task_id": cp.task_id,
                "status": cp.status,
                "timestamp": cp.timestamp,
                "age_seconds": round(time.time() - cp.timestamp, 1),
                "metadata": cp.metadata,
            })
        return sorted(result, key=lambda x: x["timestamp"], reverse=True)

    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        cp = self._cache.get(task_id)
        if cp:
            cp.status = "paused"
            self._persist(cp)
            log.info(f"任务已暂停: {task_id}")
            return True
        return False

    def resume_task(self, task_id: str) -> Optional[Checkpoint]:
        """恢复任务"""
        cp = self._cache.get(task_id)
        if cp:
            cp.status = "running"
            self._persist(cp)
            log.info(f"任务已恢复: {task_id}")
            return cp
        return None

    def migrate_task(self, task_id: str, target_node: str, new_state: Optional[dict] = None) -> bool:
        """迁移任务到其他节点"""
        cp = self._cache.get(task_id)
        if cp:
            cp.status = "migrated"
            cp.metadata["migrated_to"] = target_node
            cp.metadata["migrated_at"] = time.time()
            if new_state:
                cp.state.update(new_state)
            self._persist(cp)
            log.info(f"任务已迁移到 {target_node}: {task_id}")
            return True
        return False

    def delete_checkpoint(self, task_id: str) -> bool:
        """删除检查点"""
        if task_id in self._cache:
            del self._cache[task_id]
            path = self._path_for(task_id)
            if path.exists():
                path.unlink()
            log.info(f"检查点已删除: {task_id}")
            return True
        return False

    def cleanup_expired(self) -> int:
        """清理过期检查点"""
        now = time.time()
        expired = [
            tid for tid, cp in self._cache.items()
            if (now - cp.timestamp) > self._ttl
        ]
        for tid in expired:
            self.delete_checkpoint(tid)
        if expired:
            log.info(f"已清理 {len(expired)} 个过期检查点")
        return len(expired)

    def _persist(self, cp: Checkpoint):
        """持久化到 JSON 文件"""
        path = self._path_for(cp.task_id)
        data = asdict(cp)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════
# SelfHealer v3.2 增强版
# ═══════════════════════════════════════════════════════════════


class SelfHealer:
    """异常自愈 v3.2 - 指数退避 / 熔断器 / 优雅降级 / 异常分类

    向后兼容原有 API：get_backup / heal_plan
    """

    # 备用节点映射（v3.2 扩展）
    BACKUP_MAP = {
        "executor_writer": ["executor_researcher", "advisor_strategy", "advisor_intel"],
        "executor_coder": ["advisor_tech", "executor_tester", "executor_researcher"],
        "executor_researcher": ["advisor_intel", "executor_writer", "advisor_data"],
        "executor_analyst": ["advisor_data", "executor_researcher", "advisor_strategy"],
        "executor_tester": ["executor_coder", "advisor_tech", "executor_analyst"],
        "advisor_strategy": ["advisor_intel", "advisor_tech", "advisor_data"],
        "advisor_tech": ["executor_coder", "advisor_data", "advisor_strategy"],
        "advisor_intel": ["executor_researcher", "advisor_strategy", "executor_writer"],
        "advisor_data": ["executor_analyst", "advisor_intel", "executor_researcher"],
    }

    # 异常分类 → 恢复策略映射
    ERROR_STRATEGY = {
        ErrorCategory.NETWORK: {"retry": True, "max_retries": 3, "backoff": True, "switch_node": True},
        ErrorCategory.TIMEOUT: {"retry": True, "max_retries": 2, "backoff": True, "switch_node": False},
        ErrorCategory.MODEL: {"retry": True, "max_retries": 1, "backoff": False, "switch_node": True, "downgrade_tier": True},
        ErrorCategory.PERMISSION: {"retry": False, "switch_node": True, "escalate": True},
        ErrorCategory.RESOURCE: {"retry": True, "max_retries": 2, "backoff": True, "switch_node": True},
        ErrorCategory.UNKNOWN: {"retry": True, "max_retries": 1, "backoff": True, "switch_node": True},
    }

    def __init__(self):
        # 熔断器状态: agent_id → {"failures": int, "state": "closed|open|half_open", "last_failure": float}
        self._circuit_breakers: dict[str, dict] = {}
        self._cb_failure_threshold = 3
        self._cb_recovery_timeout = 60.0  # 秒

    # ── 原有 API（向后兼容）────────────────────────────────────

    @staticmethod
    def get_backup(original_id: str, available_agents: set) -> str | None:
        """获取备用节点"""
        backups = SelfHealer.BACKUP_MAP.get(original_id, [])
        for backup in backups:
            if backup in available_agents:
                return backup
        return None

    @staticmethod
    def heal_plan(plan: dict, failed_agents: set, available_agents: set) -> dict:
        """修复执行计划"""
        healed_tasks = []
        for task in plan.get("tasks", []):
            agent_id = task.get("agent_id", "")
            if agent_id in failed_agents:
                backup = SelfHealer.get_backup(agent_id, available_agents)
                if backup:
                    log.info(f"自愈: {agent_id} → {backup}")
                    task["agent_id"] = backup
                    task["prompt"] = f"【替代节点】原节点 {agent_id} 不可用，请执行：{task.get('prompt', '')}"
                else:
                    log.warning(f"无备用节点: {agent_id}")
            healed_tasks.append(task)

        plan["tasks"] = healed_tasks
        return plan

    # ── v3.2 新增 API ─────────────────────────────────────────

    @staticmethod
    def classify_error(error: Exception) -> ErrorCategory:
        """异常分类"""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()

        if any(kw in error_str for kw in ["connection", "network", "dns", "socket", "http"]):
            return ErrorCategory.NETWORK
        if any(kw in error_str for kw in ["timeout", "timed out", "deadline"]):
            return ErrorCategory.TIMEOUT
        if any(kw in error_str for kw in ["rate limit", "quota", "model", "token", "context length"]):
            return ErrorCategory.MODEL
        if any(kw in error_str for kw in ["permission", "forbidden", "unauthorized", "401", "403"]):
            return ErrorCategory.PERMISSION
        if any(kw in error_str for kw in ["memory", "resource", "capacity", "overload"]):
            return ErrorCategory.RESOURCE
        return ErrorCategory.UNKNOWN

    @staticmethod
    def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0, jitter: bool = True) -> float:
        """指数退避策略

        delay = min(base_delay * 2^attempt, max_delay)
        添加抖动防止雷群效应。
        """
        import random
        delay = min(base_delay * (2 ** attempt), max_delay)
        if jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        return delay

    def circuit_breaker(self, agent_id: str) -> bool:
        """熔断器集成

        返回 True 表示允许调用，False 表示熔断（应降级或切换节点）。
        状态机：closed → open → half_open → closed
        """
        cb = self._circuit_breakers.get(agent_id)
        if cb is None:
            # 初始化熔断器
            self._circuit_breakers[agent_id] = {
                "failures": 0,
                "state": "closed",
                "last_failure": 0.0,
            }
            return True

        state = cb["state"]

        if state == "closed":
            return True

        if state == "open":
            # 检查是否超过恢复超时
            if time.time() - cb["last_failure"] > self._cb_recovery_timeout:
                cb["state"] = "half_open"
                log.info(f"熔断器半开: {agent_id}")
                return True
            return False

        if state == "half_open":
            return True

        return False

    def record_failure(self, agent_id: str):
        """记录节点失败（用于熔断器）"""
        cb = self._circuit_breakers.setdefault(agent_id, {
            "failures": 0, "state": "closed", "last_failure": 0.0,
        })
        cb["failures"] += 1
        cb["last_failure"] = time.time()

        if cb["failures"] >= self._cb_failure_threshold:
            cb["state"] = "open"
            log.warning(f"熔断器打开: {agent_id} (连续失败 {cb['failures']} 次)")

    def record_success(self, agent_id: str):
        """记录节点成功（重置熔断器）"""
        if agent_id in self._circuit_breakers:
            self._circuit_breakers[agent_id] = {
                "failures": 0, "state": "closed", "last_failure": 0.0,
            }

    def graceful_degradation(self, task: dict, error: Exception) -> dict:
        """优雅降级 - 返回部分结果而非完全失败

        策略：
          1. 分类异常
          2. 根据异常类型选择降级策略
          3. 返回部分结果 + 降级标记
        """
        category = self.classify_error(error)
        strategy = self.ERROR_STRATEGY.get(category, self.ERROR_STRATEGY[ErrorCategory.UNKNOWN])

        result = {
            "status": "degraded",
            "error_category": category.value,
            "error_message": str(error),
            "strategy": strategy,
            "partial_result": None,
            "task": task,
        }

        # 根据异常类型执行不同降级策略
        if category == ErrorCategory.NETWORK:
            result["partial_result"] = "[降级] 网络异常，返回缓存结果或离线模式输出"
            result["suggestion"] = "检查网络连接，稍后重试"

        elif category == ErrorCategory.TIMEOUT:
            result["partial_result"] = "[降级] 执行超时，返回已完成部分"
            result["suggestion"] = "任务可能过于复杂，建议拆分或增加超时时间"

        elif category == ErrorCategory.MODEL:
            result["partial_result"] = "[降级] 模型异常，尝试降级模型重试"
            result["suggestion"] = "切换到更小/更稳定的模型"
            result["downgrade_tier"] = True

        elif category == ErrorCategory.PERMISSION:
            result["partial_result"] = "[降级] 权限不足，跳过此任务"
            result["suggestion"] = "检查 Agent 权限配置"
            result["escalate"] = True

        elif category == ErrorCategory.RESOURCE:
            result["partial_result"] = "[降级] 资源不足，减少并行度重试"
            result["suggestion"] = "等待资源释放或减少 Agent 数量"

        else:
            result["partial_result"] = "[降级] 未知异常，返回默认结果"
            result["suggestion"] = "检查日志获取详细信息"

        log.warning(f"优雅降级: {task.get('task_id', '?')} | {category.value} | {str(error)[:100]}")
        return result

    def get_circuit_breaker_status(self) -> dict[str, dict]:
        """获取所有熔断器状态"""
        return dict(self._circuit_breakers)


# ═══════════════════════════════════════════════════════════════
# AutonomousEngine v3.2 - 向后兼容增强版
# ═══════════════════════════════════════════════════════════════


class AutonomousEngine:
    """自治引擎 v3.2 - 丞相独立决策 + GoT 规划 + 断点续传 + 降级

    向后兼容 v3.0 API：autonomous_execute 参数不变
    """

    def __init__(self, max_iterations: int = 3, quality_threshold: float = 0.7,
                 checkpoint_dir: Optional[str] = None, enable_got: bool = True):
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        self.enable_got = enable_got
        self.got_planner = GoTPlanner() if enable_got else None
        self.scheduler = DynamicScheduler()
        self.checkpoint_mgr = CheckpointManager(checkpoint_dir=checkpoint_dir)
        self.healer = SelfHealer()

    async def autonomous_execute(self, chancellor, command: str, task_id: str) -> dict:
        """自治执行 v3.2：规划 → 执行 → 评估 → 迭代（支持断点续传 + 降级）"""
        # 检查是否有断点
        checkpoint = self.checkpoint_mgr.load_checkpoint(task_id)
        if checkpoint and checkpoint.status == "paused":
            log.info(f"从断点恢复: {task_id}")
            iteration = checkpoint.state.get("iteration", 0)
            best_result = checkpoint.state.get("best_result")
            best_score = checkpoint.state.get("best_score", 0.0)
            command = checkpoint.state.get("command", command)
        else:
            iteration = 0
            best_result = None
            best_score = 0.0

        # GoT 规划（可选）
        if self.enable_got and self.got_planner:
            got_graph = self.got_planner.build_graph(command)
            execution_order = self.got_planner.get_execution_order()
            log.info(f"GoT 规划: {len(got_graph)} 节点, 执行顺序: {execution_order[:5]}...")

        while iteration < self.max_iterations:
            iteration += 1
            log.info(f"自治迭代 {iteration}/{self.max_iterations}: {command[:50]}")

            # 保存断点
            self.checkpoint_mgr.save_checkpoint(task_id, {
                "iteration": iteration,
                "command": command,
                "best_result": best_result,
                "best_score": best_score,
            })

            try:
                # 1. 丞相规划
                plan = await chancellor._plan(task_id, command)
                if not plan or not plan.get("tasks"):
                    log.warning("规划失败，使用 fallback")
                    plan = chancellor._smart_fallback(command)

                # 2. 并行执行（带降级保护）
                results = await chancellor._execute_plan(task_id, command, plan)

            except Exception as e:
                log.error(f"执行异常: {e}")
                degraded = self.healer.graceful_degradation(
                    {"task_id": task_id, "command": command}, e
                )
                results = {"degraded": degraded.get("partial_result", "[ERROR] 降级失败")}
                self.healer.record_failure("chancellor")

            # 3. 自我评估
            score = self._evaluate_result(results)
            log.info(f"迭代 {iteration} 评分: {score:.2f}")

            if score > best_score:
                best_score = score
                best_result = results

            # 4. 达标则停止
            if score >= self.quality_threshold:
                log.info(f"达标 ({score:.2f} >= {self.quality_threshold})，停止迭代")
                break

            # 5. 不达标，优化 prompt 重试
            command = self._refine_command(command, results, score)

        # 清理断点
        self.checkpoint_mgr.delete_checkpoint(task_id)

        return {
            "iterations": iteration,
            "best_score": best_score,
            "results": best_result,
            "got_enabled": self.enable_got,
        }

    def _evaluate_result(self, results: dict) -> float:
        """评估执行结果"""
        if not results:
            return 0.0

        scores = []
        for agent_id, content in results.items():
            if agent_id == "chancellor_summary":
                continue
            if isinstance(content, dict):
                # 降级结果
                if content.get("status") == "degraded":
                    scores.append(0.2)
                    continue
                content = str(content)
            if content.startswith("[ERROR]") or content.startswith("[TIMEOUT]"):
                scores.append(0.1)
            elif content.startswith("[降级]"):
                scores.append(0.2)
            elif len(content) < 50:
                scores.append(0.3)
            elif len(content) < 200:
                scores.append(0.5)
            else:
                scores.append(0.7)
                if "```" in content or "分析" in content or "建议" in content:
                    scores.append(0.9)

        return sum(scores) / len(scores) if scores else 0.0

    def _refine_command(self, original: str, results: dict, score: float) -> str:
        """优化指令重试"""
        error_agents = []
        for aid, r in results.items():
            content = r if isinstance(r, str) else str(r)
            if content.startswith("[ERROR]") or content.startswith("[TIMEOUT]") or content.startswith("[降级]"):
                error_agents.append(aid)

        if error_agents:
            return f"{original}\n\n【注意】上次执行节点 {','.join(error_agents)} 失败，请选择其他节点或调整策略。输出要更详细、更有结构。"
        return f"{original}\n\n【优化要求】上次输出质量不足（评分{score:.2f}），请提供更详细、更有结构的分析。"


# ═══════════════════════════════════════════════════════════════
# ParallelOrchestrator - 保持原有实现
# ═══════════════════════════════════════════════════════════════


class ParallelOrchestrator:
    """并行编排器 - 独立任务同时跑，依赖任务自动排序

    v3.2: 与 GoTPlanner.get_parallel_layers() 兼容
    """

    @staticmethod
    def build_dependency_graph(tasks: list[dict]) -> list[list[dict]]:
        """构建依赖图，返回可并行执行的层级"""
        independent = []
        dependent = []

        for task in tasks:
            if task.get("dependencies"):
                dependent.append(task)
            else:
                independent.append(task)

        layers = []
        if independent:
            layers.append(independent)

        resolved = set()
        while dependent:
            layer = []
            remaining = []
            for task in dependent:
                deps = set(task["dependencies"])
                if deps.issubset(resolved):
                    layer.append(task)
                else:
                    remaining.append(task)
            if not layer:
                layers.append(remaining)
                break
            layers.append(layer)
            resolved.update(t.get("agent_id", "") for t in layer)
            dependent = remaining

        return layers

    @staticmethod
    def from_got_planner(got: GoTPlanner) -> list[list[dict]]:
        """从 GoTPlanner 的并行层级构建编排计划（v3.2 新增）"""
        layers = got.get_parallel_layers()
        result = []
        for layer in layers:
            tasks = []
            for nid in layer:
                node = got.nodes.get(nid)
                if node:
                    tasks.append({
                        "task_id": nid,
                        "agent_id": nid,
                        "prompt": node.content,
                        "complexity": node.complexity,
                        "node_type": node.node_type,
                    })
            if tasks:
                result.append(tasks)
        return result
