"""帝国架构 v3.0 - Agent 基类（多模型 + 自进化 + 插件支持）"""
import asyncio
import json
import time
from dataclasses import dataclass, field
from collections import deque
from core.bus import MessageBus, Message, MessageType
from core.tokens import TokenTracker
from core.config import load_empire_config, load_llm_credentials
from core.model_router import select_model, call_llm_api
from core.memory import AgentMemory
from core.logger import get_logger

log = get_logger("agent")


@dataclass
class AgentState:
    agent_id: str
    name: str
    role: str
    tags: list = field(default_factory=list)
    status: str = "idle"
    current_task: str = ""
    tasks_completed: int = 0
    tasks_failed: int = 0
    avg_response_time: float = 0.0
    performance_score: float = 1.0
    uptime_start: float = field(default_factory=time.time)


class Agent:
    """Agent 基类 v3.0 - 多模型 + 自进化 + 对话历史"""

    def __init__(self, agent_id: str, name: str, role: str,
                 system_prompt: str, bus: MessageBus, tracker: TokenTracker,
                 tags: list = None, model_alias: str = None):
        self.state = AgentState(
            agent_id=agent_id, name=name, role=role, tags=tags or []
        )
        self.system_prompt = system_prompt
        self.bus = bus
        self.tracker = tracker
        self.bus.register(agent_id)
        self._credentials = None
        self._config = None
        self._model_alias = model_alias  # v3.0: 指定模型
        self.memory = AgentMemory(agent_id)
        self.conversation_history: deque[dict] = deque(maxlen=10)
        self._response_times: deque[float] = deque(maxlen=20)

    def _get_credentials(self):
        if self._credentials is None:
            self._credentials = load_llm_credentials()
            self._config = load_empire_config()
        return self._credentials, self._config

    async def call_llm(self, prompt: str, context: str = "", task_type: str = "") -> str:
        """调用 LLM v3.0 - 多模型路由 + 统一接口"""
        creds, cfg = self._get_credentials()
        if not creds:
            return "[ERROR] 无可用的 LLM 凭据"

        if not self.tracker.check_budget(self.state.agent_id):
            return "[ERROR] Token 额度已用完"

        # v3.0: 智能模型选择
        model_info = select_model(self.state.role, prompt, task_type)
        model_name = model_info.get("name", "mimo-v2.5-pro")
        max_tokens = model_info.get("max_tokens", 4096)
        temperature = model_info.get("temperature", 0.7)

        # 记忆上下文注入
        memory_ctx = self.memory.get_context_window(max_chars=1500)

        messages = [{"role": "system", "content": self.system_prompt}]

        if memory_ctx:
            messages.append({"role": "system", "content": f"近期经验和记忆：\n{memory_ctx}"})
        if context:
            messages.append({"role": "user", "content": f"背景知识：\n{context}"})

        # 对话历史
        for hist in list(self.conversation_history)[-4:]:
            messages.append(hist)

        messages.append({"role": "user", "content": prompt})

        start_time = time.time()

        try:
            # v3.0: 统一 API 调用
            result = call_llm_api(model_info, messages, creds["api_key"],
                                  timeout=cfg["llm"]["timeout_seconds"])

            elapsed = time.time() - start_time
            self._response_times.append(elapsed)

            # 追踪 token
            self.tracker.log_usage(
                self.state.agent_id,
                result.get("input_tokens", 0),
                result.get("output_tokens", 0),
                model=model_name,
            )

            content = result["content"]
            self.state.tasks_completed += 1

            # 更新对话历史
            self.conversation_history.append({"role": "user", "content": prompt[:500]})
            self.conversation_history.append({"role": "assistant", "content": content[:500]})

            # 记忆
            self.memory.remember(
                f"任务: {prompt[:100]}... → 成功 (model={model_name})",
                importance=0.3, tags=["task", "success"],
            )

            # 更新平均响应时间
            if self._response_times:
                self.state.avg_response_time = sum(self._response_times) / len(self._response_times)

            return content

        except Exception as e:
            self.state.tasks_failed += 1
            self.memory.remember(f"任务失败: {e}", importance=0.6, tags=["error"])
            return f"[ERROR] {str(e)}"

    async def process_task(self, task_id: str, prompt: str, context: str = "",
                           task_type: str = "") -> str:
        """处理任务"""
        self.state.status = "busy"
        self.state.current_task = task_id
        try:
            result = await self.call_llm(prompt, context, task_type)
            self.state.status = "idle"
            self.state.current_task = ""
            return result
        except Exception as e:
            self.state.status = "error"
            return f"[ERROR] {self.state.name} 处理失败: {e}"

    def get_status(self) -> dict:
        return {
            "id": self.state.agent_id,
            "name": self.state.name,
            "role": self.state.role,
            "tags": self.state.tags,
            "status": self.state.status,
            "current_task": self.state.current_task,
            "tasks_completed": self.state.tasks_completed,
            "tasks_failed": self.state.tasks_failed,
            "avg_response_time": round(self.state.avg_response_time, 2),
            "performance_score": round(self.state.performance_score, 2),
            "memory": self.memory.get_stats(),
            "uptime": round(time.time() - self.state.uptime_start, 0),
        }
