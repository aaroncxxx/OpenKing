"""帝国架构 v3.0 - 任务队列（优先级 + 超时 + 重试 + 熔断）"""
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from core.logger import get_logger

log = get_logger("taskqueue")


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Task:
    task_id: str
    agent_id: str
    prompt: str
    priority: int = 2
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float = 0
    completed_at: float = 0
    retries: int = 0
    max_retries: int = 2
    result: str = ""
    error: str = ""


class CircuitBreaker:
    def __init__(self, fail_threshold: int = 5, recovery_time: float = 300):
        self.fail_counts: dict[str, int] = defaultdict(int)
        self.open_until: dict[str, float] = {}
        self.fail_threshold = fail_threshold
        self.recovery_time = recovery_time

    def is_open(self, agent_id: str) -> bool:
        if agent_id in self.open_until:
            if time.time() < self.open_until[agent_id]:
                return True
            del self.open_until[agent_id]
            self.fail_counts[agent_id] = 0
        return False

    def record_success(self, agent_id: str):
        self.fail_counts[agent_id] = 0

    def record_failure(self, agent_id: str):
        self.fail_counts[agent_id] += 1
        if self.fail_counts[agent_id] >= self.fail_threshold:
            self.open_until[agent_id] = time.time() + self.recovery_time
            log.warning(f"熔断器触发: {agent_id}，{self.recovery_time}s 后恢复")


class TaskQueue:
    """任务队列 v3.0"""

    def __init__(self, max_concurrent: int = 16):
        self.max_concurrent = max_concurrent
        self.tasks: list[Task] = []
        self.circuit = CircuitBreaker()
        self._stats = {"submitted": 0, "completed": 0, "failed": 0, "retried": 0}
        self._lock = threading.Lock()

    def submit(self, task: Task):
        with self._lock:
            self.tasks.append(task)
            self._stats["submitted"] += 1

    def complete(self, task: Task, result: str):
        with self._lock:
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = time.time()
            self._stats["completed"] += 1
            self.circuit.record_success(task.agent_id)

    def fail(self, task: Task, error: str):
        with self._lock:
            task.error = error
            if task.retries < task.max_retries:
                task.retries += 1
                task.status = TaskStatus.RETRYING
                self._stats["retried"] += 1
            else:
                task.status = TaskStatus.FAILED
                self._stats["failed"] += 1
                self.circuit.record_failure(task.agent_id)

    def is_circuit_open(self, agent_id: str) -> bool:
        return self.circuit.is_open(agent_id)

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "queue_size": sum(1 for t in self.tasks if t.status == TaskStatus.PENDING),
            "circuit_open": [aid for aid in self.circuit.open_until if self.circuit.is_open(aid)],
        }
