"""帝国架构 v3.1 - DAG-Shapley 任务调度算法
精确测量每个 Agent 的任务贡献，动态调整资源分配
"""
import time
from collections import defaultdict
from dataclasses import dataclass, field
from core.logger import get_logger

log = get_logger("dag_shapley")


@dataclass
class TaskNode:
    """DAG 任务节点"""
    task_id: str
    agent_id: str
    prompt: str
    dependencies: list[str] = field(default_factory=list)
    priority: int = 2
    estimated_time: float = 0
    actual_time: float = 0
    result_quality: float = 0
    contribution_score: float = 0


class DAGShapleyScheduler:
    """DAG-Shapley 调度器 - 基于贡献度的动态资源分配

    核心思想：
    1. 将任务分解为 DAG（有向无环图）
    2. 用 Shapley 值精确计算每个 Agent 的边际贡献
    3. 根据贡献度动态分配资源（模型等级、并发数、重试次数）
    """

    def __init__(self):
        self.contribution_history: dict[str, list[float]] = defaultdict(list)
        self.task_graph: dict[str, TaskNode] = {}
        self._execution_log: list[dict] = []

    def build_dag(self, tasks: list[dict]) -> dict[str, TaskNode]:
        """构建任务 DAG"""
        self.task_graph.clear()
        for t in tasks:
            node = TaskNode(
                task_id=t.get("task_id", ""),
                agent_id=t.get("agent_id", ""),
                prompt=t.get("prompt", ""),
                dependencies=t.get("dependencies", []),
                priority=t.get("priority", 2),
            )
            self.task_graph[node.task_id] = node
        return self.task_graph

    def topological_layers(self) -> list[list[TaskNode]]:
        """拓扑排序，返回可并行执行的层级"""
        in_degree = {tid: len(n.dependencies) for tid, n in self.task_graph.items()}
        layers = []

        while True:
            # 找出所有入度为 0 的节点
            ready = [tid for tid, deg in in_degree.items() if deg == 0 and tid in self.task_graph]
            if not ready:
                break

            layer = [self.task_graph[tid] for tid in ready]
            layers.append(layer)

            # 移除已处理的节点
            for tid in ready:
                del in_degree[tid]
                for other_tid, node in self.task_graph.items():
                    if tid in node.dependencies:
                        in_degree[other_tid] -= 1

        return layers

    def compute_shapley_values(self, task_id: str, agent_results: dict[str, float]) -> dict[str, float]:
        """计算 Shapley 值 - 每个 Agent 对任务的边际贡献

        简化实现：用排列近似法（采样排列计算边际贡献）
        """
        agents = list(agent_results.keys())
        n = len(agents)

        if n == 0:
            return {}
        if n == 1:
            return {agents[0]: agent_results[agents[0]]}

        shapley = defaultdict(float)
        num_samples = min(100, 2 ** n)  # 采样数

        import random
        for _ in range(num_samples):
            perm = agents[:]
            random.shuffle(perm)

            prev_value = 0.0
            coalition = set()

            for agent in perm:
                coalition.add(agent)
                # 联盟价值 = 成员质量的加权平均
                coalition_value = sum(
                    agent_results[a] for a in coalition
                ) / len(coalition)

                marginal = coalition_value - prev_value
                shapley[agent] += marginal / num_samples
                prev_value = coalition_value

        # 归一化
        total = sum(shapley.values())
        if total > 0:
            shapley = {a: v / total for a, v in shapley.items()}

        return dict(shapley)

    def record_execution(self, task_id: str, agent_id: str,
                         actual_time: float, result_quality: float):
        """记录执行结果，更新贡献历史"""
        self.contribution_history[agent_id].append(result_quality)
        self._execution_log.append({
            "task_id": task_id, "agent_id": agent_id,
            "actual_time": actual_time, "quality": result_quality,
            "timestamp": time.time(),
        })

        # 更新 DAG 节点
        if task_id in self.task_graph:
            self.task_graph[task_id].actual_time = actual_time
            self.task_graph[task_id].result_quality = result_quality

    def get_agent_contribution(self, agent_id: str) -> dict:
        """获取 Agent 的历史贡献度"""
        history = self.contribution_history.get(agent_id, [])
        if not history:
            return {"agent_id": agent_id, "avg_contribution": 0.5, "executions": 0}

        return {
            "agent_id": agent_id,
            "avg_contribution": sum(history) / len(history),
            "executions": len(history),
            "recent_trend": (
                "improving" if len(history) >= 3 and history[-1] > history[-3]
                else "stable" if len(history) < 3
                else "declining"
            ),
        }

    def allocate_resources(self, agent_id: str, base_config: dict) -> dict:
        """根据贡献度动态分配资源"""
        contribution = self.get_agent_contribution(agent_id)
        avg = contribution["avg_contribution"]

        config = base_config.copy()

        # 高贡献 Agent：更高优先级、更多重试、更大 token 配额
        if avg > 0.8:
            config["priority_boost"] = 2
            config["max_retries"] = 3
            config["max_tokens_multiplier"] = 1.5
            config["model_tier"] = "large"
        elif avg > 0.5:
            config["priority_boost"] = 1
            config["max_retries"] = 2
            config["max_tokens_multiplier"] = 1.0
            config["model_tier"] = "medium"
        else:
            config["priority_boost"] = 0
            config["max_retries"] = 1
            config["max_tokens_multiplier"] = 0.75
            config["model_tier"] = "small"

        return config

    def eliminate_redundancy(self, tasks: list[dict]) -> list[dict]:
        """消除信息冗余 - 合并相似任务"""
        if len(tasks) <= 1:
            return tasks

        # 按 agent_id 分组
        by_agent = defaultdict(list)
        for t in tasks:
            by_agent[t.get("agent_id", "")].append(t)

        # 同一 Agent 的相似任务合并
        merged = []
        for agent_id, agent_tasks in by_agent.items():
            if len(agent_tasks) == 1:
                merged.append(agent_tasks[0])
            else:
                # 合并 prompt
                prompts = [t.get("prompt", "") for t in agent_tasks]
                combined_prompt = "；".join(prompts)
                merged_task = agent_tasks[0].copy()
                merged_task["prompt"] = combined_prompt
                merged_task["merged_from"] = [t.get("task_id", "") for t in agent_tasks]
                merged.append(merged_task)
                log.info(f"合并冗余任务: {agent_id} {len(agent_tasks)}→1")

        return merged

    def get_stats(self) -> dict:
        return {
            "total_executions": len(self._execution_log),
            "agents_tracked": len(self.contribution_history),
            "contributions": {
                aid: self.get_agent_contribution(aid)
                for aid in self.contribution_history
            },
        }
