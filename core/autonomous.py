"""帝国架构 v3.0 - Agent 自治（丞相独立决策 + 多轮迭代 + 异常自愈）"""
import asyncio
from core.logger import get_logger

log = get_logger("autonomous")


class AutonomousEngine:
    """自治引擎 v3.0 - 丞相独立决策"""

    def __init__(self, max_iterations: int = 3, quality_threshold: float = 0.7):
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold

    async def autonomous_execute(self, chancellor, command: str, task_id: str) -> dict:
        """自治执行：规划 → 执行 → 评估 → 迭代"""
        iteration = 0
        best_result = None
        best_score = 0.0

        while iteration < self.max_iterations:
            iteration += 1
            log.info(f"自治迭代 {iteration}/{self.max_iterations}: {command[:50]}")

            # 1. 丞相规划
            plan = await chancellor._plan(task_id, command)
            if not plan or not plan.get("tasks"):
                log.warning("规划失败，使用 fallback")
                plan = chancellor._smart_fallback(command)

            # 2. 并行执行
            results = await chancellor._execute_plan(task_id, command, plan)

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

        return {
            "iterations": iteration,
            "best_score": best_score,
            "results": best_result,
        }

    def _evaluate_result(self, results: dict) -> float:
        """评估执行结果"""
        if not results:
            return 0.0

        scores = []
        for agent_id, content in results.items():
            if agent_id == "chancellor_summary":
                continue
            if content.startswith("[ERROR]") or content.startswith("[TIMEOUT]"):
                scores.append(0.1)
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
        error_agents = [aid for aid, r in results.items() if r.startswith("[ERROR]") or r.startswith("[TIMEOUT]")]
        if error_agents:
            return f"{original}\n\n【注意】上次执行节点 {','.join(error_agents)} 失败，请选择其他节点或调整策略。输出要更详细、更有结构。"
        return f"{original}\n\n【优化要求】上次输出质量不足（评分{score:.2f}），请提供更详细、更有结构的分析。"


class ParallelOrchestrator:
    """并行编排器 - 独立任务同时跑，依赖任务自动排序"""

    @staticmethod
    def build_dependency_graph(tasks: list[dict]) -> list[list[dict]]:
        """构建依赖图，返回可并行执行的层级"""
        # 简单实现：有 dependencies 字段的按依赖排序，没有的并行
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

        # 按依赖层级排序
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
                # 循环依赖，全部放入同一层
                layers.append(remaining)
                break
            layers.append(layer)
            resolved.update(t.get("agent_id", "") for t in layer)
            dependent = remaining

        return layers


class SelfHealer:
    """异常自愈 - 节点失败自动切换备用节点"""

    # 备用节点映射
    BACKUP_MAP = {
        "executor_writer": ["executor_researcher", "advisor_strategy"],
        "executor_coder": ["advisor_tech", "executor_tester"],
        "executor_researcher": ["advisor_intel", "executor_writer"],
        "executor_analyst": ["advisor_data", "executor_researcher"],
        "advisor_strategy": ["advisor_intel", "advisor_tech"],
        "advisor_tech": ["executor_coder", "advisor_data"],
    }

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
