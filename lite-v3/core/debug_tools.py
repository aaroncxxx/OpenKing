"""帝国架构 v3.2 - 调试与监控工具

包含：
- TaskDebugger: 任务执行全链路追踪与调试
- LogAnalyzer: 日志搜索、错误摘要、Agent 活动分析
- SystemMonitor: 系统健康检查、资源监控、调试报告导出
"""
import json
import os
import re
import sqlite3
import time
import glob
import platform
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from core.logger import get_logger

log = get_logger("debug_tools")

# ──────────────── 路径常量 ────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "data")
_LOG_DIR = os.path.join(_DATA_DIR, "logs")
_MEMORY_DIR = os.path.join(_DATA_DIR, "memory")
_EVOLUTION_DIR = os.path.join(_DATA_DIR, "evolution")
_CHECKPOINT_DIR = os.path.join(_DATA_DIR, "checkpoints")
_TOKEN_DB = os.path.join(_DATA_DIR, "tokens.db")


# ══════════════════════════════════════════════
#  TaskDebugger — 任务执行调试器
# ══════════════════════════════════════════════
@dataclass
class TaskStep:
    """任务执行步骤"""
    step_id: str
    agent_id: str
    action: str
    started_at: float
    completed_at: float = 0.0
    status: str = "pending"  # pending / running / completed / failed
    input_data: str = ""
    output_data: str = ""
    tokens_used: int = 0
    model: str = ""
    error: str = ""


@dataclass
class TaskTrace:
    """任务全链路追踪"""
    task_id: str
    steps: list[TaskStep] = field(default_factory=list)
    total_tokens: int = 0
    total_time: float = 0.0
    status: str = "unknown"
    created_at: float = field(default_factory=time.time)


class TaskDebugger:
    """任务调试器 — 全链路追踪、性能分解、重放与对比"""

    def __init__(self, chancellor=None):
        self._chancellor = chancellor
        self._traces: dict[str, TaskTrace] = {}
        self._lock = threading.Lock()

    def _get_chancellor(self):
        """延迟获取 chancellor 实例"""
        if self._chancellor is None:
            try:
                from chancellor import Chancellor
                self._chancellor = Chancellor()
            except Exception:
                pass
        return self._chancellor

    # ──────────────── trace_task ────────────────
    def trace_task(self, task_id: str) -> dict:
        """任务执行全链路追踪

        Args:
            task_id: 任务 ID

        Returns:
            包含任务完整执行链路的字典
        """
        result = {
            "task_id": task_id,
            "found": False,
            "trace": None,
            "timeline": [],
            "agent_chain": [],
            "message_flow": [],
        }

        chancellor = self._get_chancellor()

        # 从任务队列获取任务信息
        task_info = None
        if chancellor and hasattr(chancellor, "task_queue"):
            tq = chancellor.task_queue
            if task_id in tq.tasks:
                task = tq.tasks[task_id]
                task_info = {
                    "agent_id": task.agent_id,
                    "prompt": task.prompt,
                    "priority": task.priority,
                    "status": task.status.value,
                    "created_at": task.created_at,
                    "started_at": task.started_at,
                    "completed_at": task.completed_at,
                    "retries": task.retries,
                    "result": task.result[:500] if task.result else "",
                    "error": task.error[:500] if task.error else "",
                }

        if not task_info:
            # 从日志回溯
            task_info = self._search_task_in_logs(task_id)

        if task_info:
            result["found"] = True
            result["task"] = task_info

            # 构建时间线
            timeline = []
            if task_info.get("created_at"):
                timeline.append({"event": "created", "time": task_info["created_at"], "desc": "任务创建"})
            if task_info.get("started_at"):
                timeline.append({"event": "started", "time": task_info["started_at"], "desc": "开始执行"})
            if task_info.get("completed_at"):
                timeline.append({"event": "completed", "time": task_info["completed_at"], "desc": "执行完成"})
            result["timeline"] = sorted(timeline, key=lambda x: x["time"])

            # 从消息总线提取相关消息
            if chancellor and hasattr(chancellor, "bus"):
                for msg in chancellor.bus.history:
                    if task_id in str(msg.metadata) or task_id in msg.content:
                        result["message_flow"].append({
                            "sender": msg.sender,
                            "receiver": msg.receiver,
                            "type": msg.msg_type.value,
                            "content": msg.content[:200],
                            "timestamp": msg.timestamp,
                        })

            # Agent 执行链
            result["agent_chain"] = self._build_agent_chain(task_id)

            # 已有追踪数据
            if task_id in self._traces:
                result["trace"] = {
                    "total_tokens": self._traces[task_id].total_tokens,
                    "total_time": self._traces[task_id].total_time,
                    "steps_count": len(self._traces[task_id].steps),
                    "steps": [
                        {
                            "step_id": s.step_id,
                            "agent_id": s.agent_id,
                            "action": s.action,
                            "status": s.status,
                            "duration": s.completed_at - s.started_at if s.completed_at else 0,
                            "tokens": s.tokens_used,
                            "model": s.model,
                            "error": s.error,
                        }
                        for s in self._traces[task_id].steps
                    ],
                }

        return result

    def _search_task_in_logs(self, task_id: str) -> Optional[dict]:
        """从日志文件中搜索任务信息"""
        for log_name in ["taskqueue", "chancellor", "agent"]:
            log_path = os.path.join(_LOG_DIR, f"{log_name}.log")
            if not os.path.exists(log_path):
                continue
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if task_id in line:
                            # 简单提取信息
                            info = {"source": log_name, "raw_line": line.strip()}
                            # 尝试解析时间
                            time_match = re.search(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", line)
                            if time_match:
                                try:
                                    info["timestamp"] = datetime.strptime(time_match.group(1), "%Y-%m-%d %H:%M:%S").timestamp()
                                except Exception:
                                    pass
                            return info
            except Exception:
                continue
        return None

    def _build_agent_chain(self, task_id: str) -> list[dict]:
        """构建 Agent 执行链"""
        chain = []
        chancellor = self._get_chancellor()

        if chancellor and hasattr(chancellor, "bus"):
            task_messages = []
            for msg in chancellor.bus.history:
                if task_id in str(msg.metadata):
                    task_messages.append(msg)

            # 按时间排序
            task_messages.sort(key=lambda m: m.timestamp)

            seen_agents = set()
            for msg in task_messages:
                if msg.sender not in seen_agents:
                    seen_agents.add(msg.sender)
                    chain.append({
                        "agent_id": msg.sender,
                        "first_seen": msg.timestamp,
                        "role": "sender",
                    })
                if msg.receiver not in seen_agents and msg.receiver != "*":
                    seen_agents.add(msg.receiver)
                    chain.append({
                        "agent_id": msg.receiver,
                        "first_seen": msg.timestamp,
                        "role": "receiver",
                    })

        return chain

    # ──────────────── get_performance_breakdown ────────────────
    def get_performance_breakdown(self, task_id: str) -> dict:
        """性能分解 — 每个 Agent 耗时/Token

        Args:
            task_id: 任务 ID

        Returns:
            性能分解数据
        """
        breakdown = {
            "task_id": task_id,
            "total_time": 0.0,
            "total_tokens": 0,
            "agent_breakdown": {},
            "bottleneck": None,
            "token_distribution": {},
        }

        chancellor = self._get_chancellor()

        # 从 Token 数据库查询
        conn = self._get_token_db()
        if conn:
            try:
                rows = conn.execute(
                    "SELECT agent_id, SUM(input_tokens) as inp, SUM(output_tokens) as outp, "
                    "SUM(cost) as cost, COUNT(*) as calls "
                    "FROM token_usage WHERE timestamp >= ? GROUP BY agent_id",
                    (time.time() - 3600,)  # 最近 1 小时
                ).fetchall()

                for row in rows:
                    agent_id = row["agent_id"]
                    breakdown["agent_breakdown"][agent_id] = {
                        "input_tokens": row["inp"] or 0,
                        "output_tokens": row["outp"] or 0,
                        "total_tokens": (row["inp"] or 0) + (row["outp"] or 0),
                        "cost": row["cost"] or 0,
                        "calls": row["calls"] or 0,
                    }
                    breakdown["total_tokens"] += (row["inp"] or 0) + (row["outp"] or 0)
            except Exception as e:
                log.warning(f"Token DB query failed: {e}")
            finally:
                conn.close()

        # 从追踪数据补充耗时
        if task_id in self._traces:
            trace = self._traces[task_id]
            breakdown["total_time"] = trace.total_time

            for step in trace.steps:
                agent_id = step.agent_id
                if agent_id not in breakdown["agent_breakdown"]:
                    breakdown["agent_breakdown"][agent_id] = {
                        "input_tokens": 0, "output_tokens": 0,
                        "total_tokens": 0, "cost": 0, "calls": 0,
                        "total_time": 0.0,
                    }
                ab = breakdown["agent_breakdown"][agent_id]
                duration = step.completed_at - step.started_at if step.completed_at else 0
                ab["total_time"] = ab.get("total_time", 0) + duration
                ab["tokens_used"] = ab.get("tokens_used", 0) + step.tokens_used

        # 识别瓶颈
        if breakdown["agent_breakdown"]:
            max_time_agent = max(
                breakdown["agent_breakdown"].items(),
                key=lambda x: x[1].get("total_time", 0),
                default=(None, {}),
            )
            if max_time_agent[0]:
                breakdown["bottleneck"] = {
                    "agent_id": max_time_agent[0],
                    "time": max_time_agent[1].get("total_time", 0),
                    "reason": "耗时最长",
                }

        # Token 分布
        total = breakdown["total_tokens"] or 1
        for agent_id, data in breakdown["agent_breakdown"].items():
            agent_total = data.get("total_tokens", 0)
            breakdown["token_distribution"][agent_id] = round(agent_total / total, 4)

        return breakdown

    def _get_token_db(self):
        """获取 Token 数据库连接"""
        if not os.path.exists(_TOKEN_DB):
            return None
        try:
            conn = sqlite3.connect(_TOKEN_DB)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception:
            return None

    # ──────────────── replay_task ────────────────
    def replay_task(self, task_id: str, dry_run: bool = True) -> dict:
        """重放任务执行

        Args:
            task_id: 要重放的任务 ID
            dry_run: True 则只模拟不实际执行

        Returns:
            重放结果
        """
        result = {
            "task_id": task_id,
            "dry_run": dry_run,
            "replay_started": time.time(),
            "original_trace": None,
            "replay_steps": [],
            "success": False,
        }

        # 获取原始执行信息
        trace_result = self.trace_task(task_id)
        if not trace_result["found"]:
            result["error"] = f"任务 {task_id} 未找到"
            return result

        result["original_trace"] = trace_result

        chancellor = self._get_chancellor()
        if not chancellor:
            result["error"] = "丞相系统未就绪"
            return result

        task_info = trace_result.get("task", {})
        prompt = task_info.get("prompt", "")
        agent_id = task_info.get("agent_id", "")

        if dry_run:
            result["replay_steps"].append({
                "step": "dry_run",
                "action": "模拟重放",
                "prompt": prompt[:200],
                "agent": agent_id,
                "status": "simulated",
            })
            result["success"] = True
            result["note"] = "Dry run 模式，未实际执行。设置 dry_run=False 执行真实重放。"
        else:
            # 真实重放
            try:
                import asyncio
                start = time.time()
                exec_result = asyncio.run(chancellor.receive_command(prompt))
                elapsed = time.time() - start

                result["replay_steps"].append({
                    "step": "execute",
                    "action": "重新执行",
                    "prompt": prompt[:200],
                    "elapsed": elapsed,
                    "task_id": exec_result.get("task_id"),
                    "status": "completed",
                })
                result["new_task_id"] = exec_result.get("task_id")
                result["success"] = True

                # 对比结果
                result["comparison"] = {
                    "original_result": task_info.get("result", "")[:300],
                    "new_result": exec_result.get("results", {}).get("chancellor_summary", "")[:300],
                }
            except Exception as e:
                result["error"] = str(e)
                result["replay_steps"].append({
                    "step": "execute",
                    "action": "重新执行",
                    "status": "failed",
                    "error": str(e),
                })

        result["replay_completed"] = time.time()
        return result

    # ──────────────── compare_runs ────────────────
    def compare_runs(self, task_id_1: str, task_id_2: str) -> dict:
        """对比两次执行结果

        Args:
            task_id_1: 第一次执行的任务 ID
            task_id_2: 第二次执行的任务 ID

        Returns:
            对比结果
        """
        comparison = {
            "task_1": task_id_1,
            "task_2": task_id_2,
            "traces": {},
            "performance_diff": {},
            "result_diff": {},
        }

        # 获取两次执行的追踪
        trace_1 = self.trace_task(task_id_1)
        trace_2 = self.trace_task(task_id_2)

        comparison["traces"]["task_1"] = trace_1
        comparison["traces"]["task_2"] = trace_2

        if not trace_1["found"] or not trace_2["found"]:
            comparison["error"] = "至少一个任务未找到"
            return comparison

        t1 = trace_1.get("task", {})
        t2 = trace_2.get("task", {})

        # 性能对比
        time_1 = (t1.get("completed_at", 0) - t1.get("started_at", 0))
        time_2 = (t2.get("completed_at", 0) - t2.get("started_at", 0))
        comparison["performance_diff"] = {
            "time_1": time_1,
            "time_2": time_2,
            "time_diff": time_2 - time_1,
            "time_change_pct": ((time_2 - time_1) / time_1 * 100) if time_1 else 0,
            "retries_1": t1.get("retries", 0),
            "retries_2": t2.get("retries", 0),
        }

        # 结果对比
        result_1 = t1.get("result", "")
        result_2 = t2.get("result", "")
        comparison["result_diff"] = {
            "result_1_length": len(result_1),
            "result_2_length": len(result_2),
            "identical": result_1 == result_2,
            "result_1_preview": result_1[:300],
            "result_2_preview": result_2[:300],
        }

        # 瓶颈对比
        bp_1 = self.get_performance_breakdown(task_id_1)
        bp_2 = self.get_performance_breakdown(task_id_2)
        comparison["breakdown_diff"] = {
            "total_tokens_1": bp_1["total_tokens"],
            "total_tokens_2": bp_2["total_tokens"],
            "token_diff": bp_2["total_tokens"] - bp_1["total_tokens"],
            "bottleneck_1": bp_1.get("bottleneck"),
            "bottleneck_2": bp_2.get("bottleneck"),
        }

        return comparison

    # ──────────────── 辅助：记录步骤 ────────────────
    def record_step(self, task_id: str, agent_id: str, action: str,
                    input_data: str = "", output_data: str = "",
                    tokens: int = 0, model: str = "", error: str = ""):
        """记录一个执行步骤（供外部调用）"""
        with self._lock:
            if task_id not in self._traces:
                self._traces[task_id] = TaskTrace(task_id=task_id)

            step = TaskStep(
                step_id=f"{task_id}_{len(self._traces[task_id].steps)}",
                agent_id=agent_id,
                action=action,
                started_at=time.time(),
                completed_at=time.time(),
                status="completed" if not error else "failed",
                input_data=input_data[:500],
                output_data=output_data[:500],
                tokens_used=tokens,
                model=model,
                error=error,
            )
            self._traces[task_id].steps.append(step)
            self._traces[task_id].total_tokens += tokens

            if step.status == "completed" and self._traces[task_id].steps:
                first = self._traces[task_id].steps[0].started_at
                self._traces[task_id].total_time = step.completed_at - first


# ══════════════════════════════════════════════
#  LogAnalyzer — 日志分析器
# ══════════════════════════════════════════════
class LogAnalyzer:
    """日志分析器 — 搜索、错误摘要、Agent 活动报告"""

    def __init__(self, log_dir: str = None):
        self.log_dir = log_dir or _LOG_DIR

    # ──────────────── search_logs ────────────────
    def search_logs(self, query: str, level: str = None,
                    time_range: tuple = None, log_name: str = None,
                    max_results: int = 200) -> dict:
        """日志搜索

        Args:
            query: 搜索关键词（支持正则）
            level: 日志级别过滤（DEBUG/INFO/WARNING/ERROR/CRITICAL）
            time_range: (start_ts, end_ts) 时间范围
            log_name: 指定日志文件名（不含 .log），None 则搜索全部
            max_results: 最大返回条数

        Returns:
            搜索结果
        """
        results = {
            "query": query,
            "level": level,
            "total_matches": 0,
            "matches": [],
            "files_searched": 0,
            "errors": [],
        }

        # 确定要搜索的文件
        if log_name:
            log_files = [os.path.join(self.log_dir, f"{log_name}.log")]
        else:
            log_files = glob.glob(os.path.join(self.log_dir, "*.log"))

        # 编译正则
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            pattern = re.compile(re.escape(query), re.IGNORECASE)

        # 时间解析正则
        time_pattern = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")

        for log_path in log_files:
            if not os.path.exists(log_path):
                continue
            results["files_searched"] += 1
            fname = os.path.basename(log_path)

            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    for line_num, line in enumerate(f, 1):
                        # 级别过滤
                        if level and f" {level} " not in line.upper():
                            # 更宽松的匹配
                            if level.upper() not in line.upper():
                                continue

                        # 时间过滤
                        if time_range:
                            time_match = time_pattern.search(line)
                            if time_match:
                                try:
                                    line_time = datetime.strptime(time_match.group(1), "%Y-%m-%d %H:%M:%S").timestamp()
                                    if line_time < time_range[0] or line_time > time_range[1]:
                                        continue
                                except Exception:
                                    pass

                        # 关键词匹配
                        if pattern.search(line):
                            results["total_matches"] += 1
                            if len(results["matches"]) < max_results:
                                results["matches"].append({
                                    "file": fname,
                                    "line": line_num,
                                    "content": line.strip()[:300],
                                    "level": self._extract_level(line),
                                })

                            if len(results["matches"]) >= max_results:
                                break
            except Exception as e:
                results["errors"].append(f"{fname}: {str(e)}")

        return results

    def _extract_level(self, line: str) -> str:
        """从日志行提取级别"""
        for level in ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]:
            if level in line.upper():
                return level
        return "UNKNOWN"

    # ──────────────── get_error_summary ────────────────
    def get_error_summary(self, hours: int = 24) -> dict:
        """错误摘要

        Args:
            hours: 回溯小时数

        Returns:
            错误摘要
        """
        summary = {
            "time_range_hours": hours,
            "total_errors": 0,
            "total_warnings": 0,
            "errors_by_file": {},
            "top_errors": [],
            "error_timeline": [],
            "critical_alerts": [],
        }

        since = time.time() - hours * 3600
        error_counter = defaultdict(int)
        time_pattern = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")

        for log_path in glob.glob(os.path.join(self.log_dir, "*.log")):
            fname = os.path.basename(log_path).replace(".log", "")
            file_errors = 0
            file_warnings = 0

            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        # 时间过滤
                        time_match = time_pattern.search(line)
                        if time_match:
                            try:
                                line_time = datetime.strptime(time_match.group(1), "%Y-%m-%d %H:%M:%S").timestamp()
                                if line_time < since:
                                    continue
                            except Exception:
                                continue

                        if "ERROR" in line.upper():
                            file_errors += 1
                            # 提取错误模式
                            error_msg = line.strip()[-200:]
                            # 简化错误消息用于分组
                            simplified = re.sub(r"[\d\.]+", "N", error_msg)
                            error_counter[simplified[:100]] += 1

                            # 错误时间线
                            if time_match:
                                summary["error_timeline"].append({
                                    "time": time_match.group(1),
                                    "file": fname,
                                    "message": error_msg[:100],
                                })

                        elif "WARNING" in line.upper():
                            file_warnings += 1

                        if "CRITICAL" in line.upper():
                            summary["critical_alerts"].append({
                                "file": fname,
                                "message": line.strip()[-200:],
                            })

            except Exception:
                continue

            if file_errors or file_warnings:
                summary["errors_by_file"][fname] = {
                    "errors": file_errors,
                    "warnings": file_warnings,
                }
            summary["total_errors"] += file_errors
            summary["total_warnings"] += file_warnings

        # Top 错误
        summary["top_errors"] = [
            {"pattern": pattern, "count": count}
            for pattern, count in sorted(error_counter.items(), key=lambda x: -x[1])[:20]
        ]

        # 限制时间线
        summary["error_timeline"] = summary["error_timeline"][-100:]

        return summary

    # ──────────────── get_agent_activity ────────────────
    def get_agent_activity(self, agent_id: str, hours: int = 24) -> dict:
        """Agent 活动报告

        Args:
            agent_id: Agent ID
            hours: 回溯小时数

        Returns:
            Agent 活动报告
        """
        report = {
            "agent_id": agent_id,
            "time_range_hours": hours,
            "total_log_entries": 0,
            "errors": 0,
            "warnings": 0,
            "info": 0,
            "activity_timeline": [],
            "recent_messages": [],
            "task_count": 0,
        }

        since = time.time() - hours * 3600
        time_pattern = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")

        # 搜索所有日志文件
        for log_path in glob.glob(os.path.join(self.log_dir, "*.log")):
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if agent_id not in line:
                            continue

                        # 时间过滤
                        time_match = time_pattern.search(line)
                        if time_match:
                            try:
                                line_time = datetime.strptime(time_match.group(1), "%Y-%m-%d %H:%M:%S").timestamp()
                                if line_time < since:
                                    continue
                            except Exception:
                                continue

                        report["total_log_entries"] += 1

                        if "ERROR" in line.upper():
                            report["errors"] += 1
                        elif "WARNING" in line.upper():
                            report["warnings"] += 1
                        elif "INFO" in line.upper():
                            report["info"] += 1

                        if len(report["recent_messages"]) < 50:
                            report["recent_messages"].append({
                                "time": time_match.group(1) if time_match else "unknown",
                                "file": os.path.basename(log_path),
                                "content": line.strip()[:200],
                            })
            except Exception:
                continue

        # 从记忆系统获取任务相关数据
        mem_path = os.path.join(_MEMORY_DIR, f"{agent_id}.json")
        if os.path.exists(mem_path):
            try:
                with open(mem_path, "r", encoding="utf-8") as f:
                    mem_data = json.load(f)
                long_term = mem_data.get("long_term", [])
                recent_memories = [m for m in long_term if m.get("time", 0) >= since]
                report["task_count"] = len([m for m in recent_memories if m.get("task_id")])
                report["memory_entries"] = len(recent_memories)
            except Exception:
                pass

        # 从进化系统获取评估数据
        eval_path = os.path.join(_EVOLUTION_DIR, "evaluations.json")
        if os.path.exists(eval_path):
            try:
                with open(eval_path, "r") as f:
                    evals = json.load(f)
                agent_evals = [e for e in evals if e.get("agent_id") == agent_id and e.get("timestamp", 0) >= since]
                report["evaluations"] = len(agent_evals)
                if agent_evals:
                    report["avg_quality"] = sum(e.get("quality_score", 0) for e in agent_evals) / len(agent_evals)
                    report["avg_speed"] = sum(e.get("speed_score", 0) for e in agent_evals) / len(agent_evals)
            except Exception:
                pass

        report["recent_messages"] = report["recent_messages"][-50:]
        return report


# ══════════════════════════════════════════════
#  SystemMonitor — 系统监控
# ══════════════════════════════════════════════
class SystemMonitor:
    """系统监控 — 健康检查、资源使用、调试报告"""

    def __init__(self):
        self._start_time = time.time()

    # ──────────────── get_system_health ────────────────
    def get_system_health(self) -> dict:
        """系统健康检查

        Returns:
            系统健康状态
        """
        health = {
            "status": "healthy",
            "checks": [],
            "uptime_seconds": time.time() - self._start_time,
            "timestamp": datetime.now().isoformat(),
        }

        # 1. 数据目录检查
        for name, path in [
            ("data", _DATA_DIR),
            ("logs", _LOG_DIR),
            ("memory", _MEMORY_DIR),
            ("evolution", _EVOLUTION_DIR),
        ]:
            exists = os.path.exists(path)
            health["checks"].append({
                "name": f"目录: {name}",
                "status": "ok" if exists else "error",
                "detail": path if exists else f"缺失: {path}",
            })
            if not exists:
                health["status"] = "degraded"

        # 2. 日志文件健康
        log_files = glob.glob(os.path.join(_LOG_DIR, "*.log"))
        total_log_size = sum(os.path.getsize(f) for f in log_files)
        health["checks"].append({
            "name": "日志文件",
            "status": "ok" if total_log_size < 500 * 1024 * 1024 else "warning",
            "detail": f"{len(log_files)} 个文件, {total_log_size / 1024 / 1024:.1f} MB",
        })
        if total_log_size > 500 * 1024 * 1024:
            health["status"] = "warning"

        # 3. Token 数据库检查
        if os.path.exists(_TOKEN_DB):
            try:
                conn = sqlite3.connect(_TOKEN_DB)
                count = conn.execute("SELECT COUNT(*) FROM token_usage").fetchone()[0]
                conn.close()
                health["checks"].append({
                    "name": "Token 数据库",
                    "status": "ok",
                    "detail": f"{count} 条记录",
                })
            except Exception as e:
                health["checks"].append({
                    "name": "Token 数据库",
                    "status": "error",
                    "detail": str(e),
                })
                health["status"] = "degraded"
        else:
            health["checks"].append({
                "name": "Token 数据库",
                "status": "warning",
                "detail": "数据库文件不存在",
            })

        # 4. 记忆文件检查
        mem_files = glob.glob(os.path.join(_MEMORY_DIR, "*.json"))
        corrupted = 0
        for mf in mem_files:
            try:
                with open(mf, "r") as f:
                    json.load(f)
            except Exception:
                corrupted += 1
        health["checks"].append({
            "name": "记忆文件",
            "status": "ok" if corrupted == 0 else "warning",
            "detail": f"{len(mem_files)} 个文件, {corrupted} 个损坏",
        })

        # 5. 检查点目录
        ckpt_files = glob.glob(os.path.join(_CHECKPOINT_DIR, "*.json"))
        health["checks"].append({
            "name": "检查点",
            "status": "ok",
            "detail": f"{len(ckpt_files)} 个检查点",
        })

        # 6. 进化数据
        eval_path = os.path.join(_EVOLUTION_DIR, "evaluations.json")
        if os.path.exists(eval_path):
            try:
                with open(eval_path, "r") as f:
                    evals = json.load(f)
                health["checks"].append({
                    "name": "进化数据",
                    "status": "ok",
                    "detail": f"{len(evals)} 条评估记录",
                })
            except Exception:
                health["checks"].append({
                    "name": "进化数据",
                    "status": "error",
                    "detail": "评估文件损坏",
                })

        # 7. 系统错误率
        analyzer = LogAnalyzer()
        error_summary = analyzer.get_error_summary(hours=1)
        if error_summary["total_errors"] > 50:
            health["status"] = "unhealthy"
            health["checks"].append({
                "name": "错误率",
                "status": "error",
                "detail": f"最近 1 小时 {error_summary['total_errors']} 个错误",
            })
        elif error_summary["total_errors"] > 10:
            health["checks"].append({
                "name": "错误率",
                "status": "warning",
                "detail": f"最近 1 小时 {error_summary['total_errors']} 个错误",
            })
        else:
            health["checks"].append({
                "name": "错误率",
                "status": "ok",
                "detail": f"最近 1 小时 {error_summary['total_errors']} 个错误",
            })

        return health

    # ──────────────── get_resource_usage ────────────────
    def get_resource_usage(self) -> dict:
        """资源使用情况

        Returns:
            资源使用数据
        """
        usage = {
            "timestamp": datetime.now().isoformat(),
            "system": {},
            "disk": {},
            "empire_data": {},
        }

        # 系统资源（轻量级，不依赖 psutil）
        try:
            import resource
            ru = resource.getrusage(resource.RUSAGE_SELF)
            usage["system"]["memory_mb"] = ru.ru_maxrss / 1024  # Linux: KB → MB
            usage["system"]["user_time"] = ru.ru_utime
            usage["system"]["system_time"] = ru.ru_stime
        except Exception:
            pass

        # 平台信息
        usage["system"]["platform"] = platform.platform()
        usage["system"]["python"] = platform.python_version()
        usage["system"]["cpu_count"] = os.cpu_count()

        # 磁盘使用
        try:
            stat = os.statvfs(_DATA_DIR)
            usage["disk"]["total_gb"] = (stat.f_blocks * stat.f_frsize) / (1024 ** 3)
            usage["disk"]["free_gb"] = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            usage["disk"]["used_pct"] = round(
                (1 - stat.f_bavail / stat.f_blocks) * 100, 1
            ) if stat.f_blocks else 0
        except Exception:
            pass

        # Empire 数据大小
        for name, path in [
            ("logs", _LOG_DIR),
            ("memory", _MEMORY_DIR),
            ("evolution", _EVOLUTION_DIR),
            ("checkpoints", _CHECKPOINT_DIR),
        ]:
            if os.path.exists(path):
                total = sum(
                    os.path.getsize(os.path.join(dp, f))
                    for dp, _, filenames in os.walk(path)
                    for f in filenames
                )
                usage["empire_data"][name] = {
                    "size_mb": round(total / 1024 / 1024, 2),
                    "file_count": sum(len(filenames) for _, _, filenames in os.walk(path)),
                }

        # Token 数据库大小
        if os.path.exists(_TOKEN_DB):
            usage["empire_data"]["token_db"] = {
                "size_mb": round(os.path.getsize(_TOKEN_DB) / 1024 / 1024, 2),
            }

        return usage

    # ──────────────── export_debug_report ────────────────
    def export_debug_report(self, output_path: str = None) -> str:
        """导出调试报告

        Args:
            output_path: 输出文件路径，默认 data/debug_report_<timestamp>.json

        Returns:
            报告文件路径
        """
        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(_DATA_DIR, f"debug_report_{ts}.json")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "version": "v3.2",
                "generator": "SystemMonitor.export_debug_report",
            },
            "system_health": self.get_system_health(),
            "resource_usage": self.get_resource_usage(),
            "error_summary": LogAnalyzer().get_error_summary(hours=24),
        }

        # Agent 活动（从记忆文件推断 Agent 列表）
        agent_ids = [
            os.path.basename(f).replace(".json", "")
            for f in glob.glob(os.path.join(_MEMORY_DIR, "*.json"))
        ]
        report["agent_activities"] = {}
        analyzer = LogAnalyzer()
        for agent_id in agent_ids[:20]:  # 限制最多 20 个
            report["agent_activities"][agent_id] = analyzer.get_agent_activity(agent_id, hours=24)

        # 进化数据
        eval_path = os.path.join(_EVOLUTION_DIR, "evaluations.json")
        if os.path.exists(eval_path):
            try:
                with open(eval_path, "r") as f:
                    report["evolution_evaluations_count"] = len(json.load(f))
            except Exception:
                pass

        ranks_path = os.path.join(_EVOLUTION_DIR, "ranks.json")
        if os.path.exists(ranks_path):
            try:
                with open(ranks_path, "r") as f:
                    report["evolution_ranks"] = json.load(f)
            except Exception:
                pass

        # 检查点列表
        report["checkpoints"] = [
            {
                "name": os.path.basename(f),
                "size_kb": round(os.path.getsize(f) / 1024, 1),
                "modified": datetime.fromtimestamp(os.path.getmtime(f)).isoformat(),
            }
            for f in glob.glob(os.path.join(_CHECKPOINT_DIR, "*.json"))
        ]

        # 写入文件
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        log.info(f"调试报告已导出: {output_path}")
        return output_path


# ══════════════════════════════════════════════
#  便捷入口
# ══════════════════════════════════════════════
def get_task_debugger(chancellor=None) -> TaskDebugger:
    """获取 TaskDebugger 实例"""
    return TaskDebugger(chancellor=chancellor)


def get_log_analyzer() -> LogAnalyzer:
    """获取 LogAnalyzer 实例"""
    return LogAnalyzer()


def get_system_monitor() -> SystemMonitor:
    """获取 SystemMonitor 实例"""
    return SystemMonitor()


# ──────────────── CLI 入口 ────────────────
if __name__ == "__main__":
    import sys

    usage = """
帝国架构 v3.2 调试工具

用法:
  python -m core.debug_tools health          系统健康检查
  python -m core.debug_tools errors [hours]  错误摘要
  python -m core.debug_tools search <query>  日志搜索
  python -m core.debug_tools agent <id>      Agent 活动报告
  python -m core.debug_tools export          导出调试报告
  python -m core.debug_tools resources       资源使用情况
"""

    if len(sys.argv) < 2:
        print(usage)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "health":
        monitor = SystemMonitor()
        health = monitor.get_system_health()
        print(f"\n系统状态: {health['status'].upper()}")
        print(f"运行时间: {health['uptime_seconds']:.0f}s")
        for check in health["checks"]:
            icon = {"ok": "✅", "warning": "⚠️", "error": "❌"}.get(check["status"], "❓")
            print(f"  {icon} {check['name']}: {check['detail']}")

    elif cmd == "errors":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        analyzer = LogAnalyzer()
        summary = analyzer.get_error_summary(hours=hours)
        print(f"\n错误摘要 (最近 {hours} 小时)")
        print(f"  总错误: {summary['total_errors']}")
        print(f"  总警告: {summary['total_warnings']}")
        if summary["top_errors"]:
            print("\nTop 错误:")
            for e in summary["top_errors"][:10]:
                print(f"  [{e['count']}次] {e['pattern'][:80]}")
        if summary["critical_alerts"]:
            print("\n🚨 严重告警:")
            for a in summary["critical_alerts"]:
                print(f"  {a['file']}: {a['message'][:100]}")

    elif cmd == "search":
        if len(sys.argv) < 3:
            print("用法: python -m core.debug_tools search <query>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        analyzer = LogAnalyzer()
        results = analyzer.search_logs(query)
        print(f"\n搜索 '{query}': {results['total_matches']} 匹配 (搜索 {results['files_searched']} 个文件)")
        for m in results["matches"][:20]:
            print(f"  [{m['file']}:{m['line']}] {m['content'][:120]}")

    elif cmd == "agent":
        if len(sys.argv) < 3:
            print("用法: python -m core.debug_tools agent <agent_id>")
            sys.exit(1)
        agent_id = sys.argv[2]
        analyzer = LogAnalyzer()
        report = analyzer.get_agent_activity(agent_id)
        print(f"\nAgent 活动报告: {agent_id}")
        print(f"  日志条目: {report['total_log_entries']}")
        print(f"  错误: {report['errors']}, 警告: {report['warnings']}")
        print(f"  任务数: {report['task_count']}")
        if "avg_quality" in report:
            print(f"  平均质量: {report['avg_quality']:.2f}")

    elif cmd == "export":
        monitor = SystemMonitor()
        path = monitor.export_debug_report()
        print(f"调试报告已导出: {path}")

    elif cmd == "resources":
        monitor = SystemMonitor()
        usage = monitor.get_resource_usage()
        print(f"\n资源使用:")
        print(f"  平台: {usage['system'].get('platform', 'N/A')}")
        print(f"  Python: {usage['system'].get('python', 'N/A')}")
        print(f"  CPU: {usage['system'].get('cpu_count', 'N/A')} 核")
        if "memory_mb" in usage["system"]:
            print(f"  内存: {usage['system']['memory_mb']:.1f} MB")
        if usage["disk"]:
            print(f"  磁盘: {usage['disk'].get('used_pct', 0)}% 已用, {usage['disk'].get('free_gb', 0):.1f} GB 可用")
        for name, data in usage.get("empire_data", {}).items():
            print(f"  {name}: {data.get('size_mb', 0)} MB ({data.get('file_count', '?')} 文件)")

    else:
        print(usage)
