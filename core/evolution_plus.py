"""帝国架构 v3.1 - 自我进化增强
闭环优化 + 自动 Prompt 工程 + 经验库
"""
import json
import os
import time
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional
from core.logger import get_logger

log = get_logger("evolution_plus")


@dataclass
class Experience:
    """经验条目 - 成功的任务执行流程"""
    exp_id: str
    task_type: str
    task_pattern: str         # 任务关键词模式
    solution_flow: list[dict] # 解决流程 [{agent_id, prompt, result_quality}]
    total_time: float
    total_tokens: int
    success_score: float      # 0-1
    reuse_count: int = 0
    created_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)


class ClosedLoopOptimizer:
    """闭环优化器 - 性能评估→贡献测量→瓶颈识别→提示优化→系统更新"""

    def __init__(self):
        self.bottlenecks: list[dict] = []
        self.optimizations: list[dict] = []

    def identify_bottlenecks(self, agent_stats: dict) -> list[dict]:
        """识别系统瓶颈"""
        bottlenecks = []

        for agent_id, stats in agent_stats.items():
            # 高失败率
            total = stats.get("tasks_completed", 0) + stats.get("tasks_failed", 0)
            if total > 5:
                fail_rate = stats.get("tasks_failed", 0) / total
                if fail_rate > 0.3:
                    bottlenecks.append({
                        "type": "high_failure_rate",
                        "agent_id": agent_id,
                        "severity": fail_rate,
                        "recommendation": "降低该 Agent 任务复杂度或替换为备用节点",
                    })

            # 响应时间过长
            avg_rt = stats.get("avg_response_time", 0)
            if avg_rt > 60:
                bottlenecks.append({
                    "type": "slow_response",
                    "agent_id": agent_id,
                    "severity": avg_rt / 60,
                    "recommendation": "切换到更快的模型或简化 prompt",
                })

            # 评分过低
            score = stats.get("performance_score", 1.0)
            if score < 0.5:
                bottlenecks.append({
                    "type": "low_quality",
                    "agent_id": agent_id,
                    "severity": 1 - score,
                    "recommendation": "优化 system prompt 或替换 Agent",
                })

        self.bottlenecks = bottlenecks
        return bottlenecks

    def generate_optimizations(self, bottlenecks: list[dict]) -> list[dict]:
        """生成优化建议"""
        optimizations = []
        for b in bottlenecks:
            opt = {
                "bottleneck": b,
                "actions": [],
            }

            if b["type"] == "high_failure_rate":
                opt["actions"] = [
                    f"将 {b['agent_id']} 的任务分配给评分更高的备用节点",
                    f"为 {b['agent_id']} 添加错误处理和重试逻辑",
                    f"降低分配给 {b['agent_id']} 的任务优先级",
                ]
            elif b["type"] == "slow_response":
                opt["actions"] = [
                    f"将 {b['agent_id']} 的模型切换为更快的 DeepSeek",
                    f"缩短 {b['agent_id']} 的 prompt 长度",
                    f"为 {b['agent_id']} 设置更严格的超时",
                ]
            elif b["type"] == "low_quality":
                opt["actions"] = [
                    f"为 {b['agent_id']} 添加更多上下文示例",
                    f"将 {b['agent_id']} 的模型升级为 Claude/GPT-4",
                    f"用经验库中的成功 prompt 替换当前 prompt",
                ]

            optimizations.append(opt)

        self.optimizations = optimizations
        return optimizations


class AutoPromptEngine:
    """自动 Prompt 工程 - 借鉴 DSPy / AutoPrompt"""

    def __init__(self):
        self._prompt_templates: dict[str, str] = {}
        self._prompt_scores: dict[str, list[float]] = defaultdict(list)

    def optimize_prompt(self, agent_id: str, current_prompt: str,
                        task_type: str, successful_examples: list[dict],
                        failed_examples: list[dict]) -> str:
        """根据成功/失败案例自动优化 prompt"""
        if not successful_examples and not failed_examples:
            return current_prompt

        # 提取成功模式
        success_patterns = []
        for ex in successful_examples[:5]:
            if ex.get("result", "").startswith("[ERROR]"):
                continue
            # 提取结果中的关键词
            keywords = self._extract_keywords(ex.get("result", ""))
            success_patterns.extend(keywords)

        # 提取失败模式
        failure_patterns = []
        for ex in failed_examples[:3]:
            keywords = self._extract_keywords(ex.get("result", ""))
            failure_patterns.extend(keywords)

        # 构建优化指令
        optimization = f"\n\n【自动 Prompt 优化 - {task_type}】"
        if success_patterns:
            top_patterns = list(set(success_patterns))[:5]
            optimization += f"\n成功模式参考：{', '.join(top_patterns)}"
        if failure_patterns:
            top_failures = list(set(failure_patterns))[:3]
            optimization += f"\n避免以下模式：{', '.join(top_failures)}"

        optimized = current_prompt + optimization
        self._prompt_templates[agent_id] = optimized

        log.info(f"自动 Prompt 优化: {agent_id} ({task_type})")
        return optimized

    def _extract_keywords(self, text: str) -> list[str]:
        """提取关键短语"""
        # 简单实现：提取高频词
        words = text.lower().split()
        stopwords = {"的", "是", "在", "了", "和", "与", "或", "不", "有", "这", "那",
                     "the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
                     "to", "for", "of", "with", "by", "and", "or", "not"}
        keywords = [w for w in words if len(w) > 2 and w not in stopwords]
        # 频率统计
        freq = defaultdict(int)
        for kw in keywords:
            freq[kw] += 1
        return sorted(freq, key=freq.get, reverse=True)[:10]

    def score_prompt(self, agent_id: str, prompt: str, result_score: float):
        """记录 prompt 效果评分"""
        prompt_hash = hashlib.md5(prompt[:200].encode()).hexdigest()[:8]
        self._prompt_scores[f"{agent_id}_{prompt_hash}"].append(result_score)

    def get_best_prompt(self, agent_id: str) -> Optional[str]:
        """获取效果最好的 prompt"""
        return self._prompt_templates.get(agent_id)


class ExperienceLibrary:
    """经验库 - 将成功的任务执行流程保存复用"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "experience")
        os.makedirs(data_dir, exist_ok=True)
        self._path = os.path.join(data_dir, "experiences.json")
        self.experiences: list[Experience] = []
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.experiences = [Experience(**e) for e in data[-200:]]
            except Exception:
                pass

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump([{
                    "exp_id": e.exp_id, "task_type": e.task_type,
                    "task_pattern": e.task_pattern,
                    "solution_flow": e.solution_flow,
                    "total_time": e.total_time, "total_tokens": e.total_tokens,
                    "success_score": e.success_score, "reuse_count": e.reuse_count,
                    "created_at": e.created_at, "tags": e.tags,
                } for e in self.experiences[-200:]], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def save_experience(self, task_type: str, task_pattern: str,
                        solution_flow: list[dict], total_time: float,
                        total_tokens: int, success_score: float,
                        tags: list[str] = None):
        """保存成功经验"""
        exp_id = hashlib.md5(f"{task_type}_{time.time()}".encode()).hexdigest()[:12]
        exp = Experience(
            exp_id=exp_id, task_type=task_type,
            task_pattern=task_pattern,
            solution_flow=solution_flow,
            total_time=total_time, total_tokens=total_tokens,
            success_score=success_score, tags=tags or [],
        )
        self.experiences.append(exp)
        self._save()
        log.info(f"经验保存: {exp_id} ({task_type}) score={success_score:.2f}")

    def find_similar_experience(self, task_type: str, task_text: str,
                                 top_k: int = 3) -> list[Experience]:
        """查找相似经验"""
        candidates = []
        for exp in self.experiences:
            if exp.success_score < 0.6:
                continue

            # 类型匹配
            type_match = 1.0 if exp.task_type == task_type else 0.3

            # 关键词匹配
            task_words = set(task_text.lower().split())
            pattern_words = set(exp.task_pattern.lower().split())
            word_match = len(task_words & pattern_words) / max(1, len(task_words | pattern_words))

            score = type_match * 0.5 + word_match * 0.3 + exp.success_score * 0.2
            candidates.append((exp, score))

        candidates.sort(key=lambda x: -x[1])
        return [e for e, _ in candidates[:top_k]]

    def apply_experience(self, experience: Experience) -> list[dict]:
        """应用经验到当前任务"""
        experience.reuse_count += 1
        self._save()
        return experience.solution_flow

    def get_stats(self) -> dict:
        by_type = defaultdict(int)
        total_reuse = 0
        for exp in self.experiences:
            by_type[exp.task_type] += 1
            total_reuse += exp.reuse_count
        return {
            "total_experiences": len(self.experiences),
            "by_type": dict(by_type),
            "total_reuse": total_reuse,
            "avg_success": (
                sum(e.success_score for e in self.experiences) / max(1, len(self.experiences))
            ),
        }
