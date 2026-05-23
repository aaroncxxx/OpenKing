"""帝国架构 v3.0 - 自进化系统（自我评估 + 技能进化 + 晋降级）"""
import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from core.logger import get_logger

log = get_logger("evolution")


@dataclass
class TaskEvaluation:
    task_id: str
    agent_id: str
    quality_score: float = 0.0    # 0-1, 输出质量
    speed_score: float = 0.0      # 0-1, 响应速度
    collaboration_score: float = 0.0  # 0-1, 协作效率
    overall_score: float = 0.0
    feedback: str = ""
    timestamp: float = field(default_factory=time.time)


class SelfEvolutionEngine:
    """自进化引擎 v3.0 - Agent 能自己学"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "evolution")
        os.makedirs(data_dir, exist_ok=True)
        self._eval_path = os.path.join(data_dir, "evaluations.json")
        self._prompt_path = os.path.join(data_dir, "evolved_prompts.json")
        self._rank_path = os.path.join(data_dir, "ranks.json")

        self.evaluations: list[TaskEvaluation] = []
        self.evolved_prompts: dict[str, str] = {}  # agent_id → 优化后的 prompt
        self.ranks: dict[str, str] = {}  # agent_id → 当前等级
        self._load()

    def _load(self):
        """加载历史数据"""
        try:
            if os.path.exists(self._eval_path):
                with open(self._eval_path, "r") as f:
                    data = json.load(f)
                self.evaluations = [TaskEvaluation(**e) for e in data[-500:]]
        except Exception:
            pass
        try:
            if os.path.exists(self._prompt_path):
                with open(self._prompt_path, "r") as f:
                    self.evolved_prompts = json.load(f)
        except Exception:
            pass
        try:
            if os.path.exists(self._rank_path):
                with open(self._rank_path, "r") as f:
                    self.ranks = json.load(f)
        except Exception:
            pass

    def _save(self):
        try:
            with open(self._eval_path, "w") as f:
                json.dump([{
                    "task_id": e.task_id, "agent_id": e.agent_id,
                    "quality_score": e.quality_score, "speed_score": e.speed_score,
                    "collaboration_score": e.collaboration_score,
                    "overall_score": e.overall_score, "feedback": e.feedback,
                    "timestamp": e.timestamp,
                } for e in self.evaluations[-500:]], f, ensure_ascii=False, indent=2)
            with open(self._prompt_path, "w") as f:
                json.dump(self.evolved_prompts, f, ensure_ascii=False, indent=2)
            with open(self._rank_path, "w") as f:
                json.dump(self.ranks, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ──────────────── 自我评估 ────────────────

    async def evaluate_task(self, agent_id: str, task_id: str, prompt: str,
                            result: str, elapsed_seconds: float,
                            chancellor_llm=None) -> TaskEvaluation:
        """每次任务后自动评分"""
        quality = self._assess_quality(result)
        speed = self._assess_speed(elapsed_seconds)
        collaboration = 0.8  # 默认

        overall = quality * 0.5 + speed * 0.2 + collaboration * 0.3

        eval_result = TaskEvaluation(
            task_id=task_id, agent_id=agent_id,
            quality_score=quality, speed_score=speed,
            collaboration_score=collaboration,
            overall_score=overall,
        )

        self.evaluations.append(eval_result)
        self._save()

        log.info(f"任务评估: {agent_id} 质量={quality:.2f} 速度={speed:.2f} 总分={overall:.2f}")
        return eval_result

    def _assess_quality(self, result: str) -> float:
        """评估输出质量"""
        if not result or result.startswith("[ERROR]"):
            return 0.1
        if len(result) < 20:
            return 0.3
        if len(result) < 100:
            return 0.5
        # 有结构化内容加分
        score = 0.6
        if "```" in result:
            score += 0.1
        if any(kw in result for kw in ["分析", "建议", "总结", "结论"]):
            score += 0.1
        if len(result) > 500:
            score += 0.1
        return min(score, 1.0)

    def _assess_speed(self, elapsed: float) -> float:
        """评估响应速度"""
        if elapsed < 5:
            return 1.0
        if elapsed < 15:
            return 0.8
        if elapsed < 30:
            return 0.6
        if elapsed < 60:
            return 0.4
        return 0.2

    # ──────────────── 技能进化 ────────────────

    async def evolve_prompt(self, agent_id: str, current_prompt: str,
                            recent_evals: list[TaskEvaluation],
                            chancellor_llm=None) -> str:
        """根据历史任务自动优化 Agent 的 system prompt"""
        if not recent_evals or len(recent_evals) < 5:
            return current_prompt

        avg_quality = sum(e.quality_score for e in recent_evals) / len(recent_evals)
        avg_speed = sum(e.speed_score for e in recent_evals) / len(recent_evals)
        weak_areas = []
        if avg_quality < 0.6:
            weak_areas.append("输出质量不足，需要更详细的回答")
        if avg_speed < 0.5:
            weak_areas.append("响应太慢，需要更简洁高效")

        if not weak_areas:
            return current_prompt

        evolved = current_prompt + f"\n\n【自进化优化】近期表现提示：{'; '.join(weak_areas)}。请针对性改进。"
        self.evolved_prompts[agent_id] = evolved
        self._save()
        log.info(f"技能进化: {agent_id} prompt 已优化（{len(weak_areas)} 项改进）")
        return evolved

    # ──────────────── 淘汰与晋升 ────────────────

    RANK_HIERARCHY = [
        "郡守", "执行", "监察", "翰林", "参谋", "九卿", "三公"
    ]

    def check_promotion_demotion(self, agent_id: str, config: dict) -> dict | None:
        """检查是否需要晋升或降级"""
        recent = [e for e in self.evaluations if e.agent_id == agent_id][-20:]
        if len(recent) < 10:
            return None

        avg_score = sum(e.overall_score for e in recent) / len(recent)
        current_rank = self.ranks.get(agent_id, "郡守")
        current_idx = self.RANK_HIERARCHY.index(current_rank) if current_rank in self.RANK_HIERARCHY else 0

        promotion_threshold = config.get("evolution", {}).get("promotion_threshold", 1.3)
        demotion_threshold = config.get("evolution", {}).get("demotion_threshold", 0.7)

        if avg_score > promotion_threshold and current_idx < len(self.RANK_HIERARCHY) - 1:
            new_rank = self.RANK_HIERARCHY[current_idx + 1]
            self.ranks[agent_id] = new_rank
            self._save()
            log.info(f"晋升: {agent_id} {current_rank} → {new_rank} (avg={avg_score:.2f})")
            return {"action": "promotion", "from": current_rank, "to": new_rank, "score": avg_score}

        if avg_score < demotion_threshold and current_idx > 0:
            new_rank = self.RANK_HIERARCHY[current_idx - 1]
            self.ranks[agent_id] = new_rank
            self._save()
            log.info(f"降级: {agent_id} {current_rank} → {new_rank} (avg={avg_score:.2f})")
            return {"action": "demotion", "from": current_rank, "to": new_rank, "score": avg_score}

        return None

    def get_agent_evolution_status(self, agent_id: str) -> dict:
        """获取 Agent 进化状态"""
        recent = [e for e in self.evaluations if e.agent_id == agent_id][-20:]
        if not recent:
            return {"evaluations": 0, "avg_score": 0, "rank": self.ranks.get(agent_id, "郡守")}

        return {
            "evaluations": len(recent),
            "avg_quality": sum(e.quality_score for e in recent) / len(recent),
            "avg_speed": sum(e.speed_score for e in recent) / len(recent),
            "avg_overall": sum(e.overall_score for e in recent) / len(recent),
            "rank": self.ranks.get(agent_id, "郡守"),
            "evolved_prompt": agent_id in self.evolved_prompts,
        }

    def get_all_status(self) -> dict:
        """全局进化状态"""
        agents = set(e.agent_id for e in self.evaluations)
        return {
            "total_evaluations": len(self.evaluations),
            "agents_tracked": len(agents),
            "ranks": dict(self.ranks),
            "evolved_prompts": len(self.evolved_prompts),
        }
