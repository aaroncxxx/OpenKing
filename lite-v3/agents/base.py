"""帝国架构 v3.2 - Agent 基类升级
在 v3.0 基础上集成 Memory3D + 因果推理 + 帝国图书馆 + 记忆蒸馏 + 主动检索
"""
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
from core.memory3d import (
    Memory3D, MemoryFunction, MemoryForm,
    CausalMemoryGraph, ImperialLibrary,
    MemoryDistiller, ProactiveRetriever,
)
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
    """Agent 基类 v3.2 - 多模型 + 自进化 + 三维记忆 + 因果推理 + 知识共享

    v3.2 新增:
    - Memory3D 三维记忆替代简单记忆
    - CausalMemoryGraph 因果推理
    - ImperialLibrary 知识共享（全局单例，由 Chancellor 注入）
    - MemoryDistiller 记忆蒸馏
    - ProactiveRetriever 主动记忆检索
    """

    def __init__(self, agent_id: str, name: str, role: str,
                 system_prompt: str, bus: MessageBus, tracker: TokenTracker,
                 tags: list = None, model_alias: str = None,
                 use_memory3d: bool = True):
        self.state = AgentState(
            agent_id=agent_id, name=name, role=role, tags=tags or []
        )
        self.system_prompt = system_prompt
        self.bus = bus
        self.tracker = tracker
        self.bus.register(agent_id)
        self._credentials = None
        self._config = None
        self._model_alias = model_alias

        # v3.2: 记忆系统
        self.use_memory3d = use_memory3d
        if use_memory3d:
            self.memory3d = Memory3D(agent_id)
            self.distiller = MemoryDistiller(self.memory3d)
            self.retriever = ProactiveRetriever(self.memory3d)
            # 旧接口兼容层
            self.memory = _Memory3DCompat(self.memory3d)
        else:
            self.memory3d = None
            self.distiller = None
            self.retriever = None
            self.memory = AgentMemory(agent_id)

        # v3.2: 因果推理（可选，由 Chancellor 注入或独立创建）
        self.causal: CausalMemoryGraph | None = None
        # v3.2: 帝国图书馆引用（全局单例，由 Chancellor 注入）
        self.library: ImperialLibrary | None = None

        self.conversation_history: deque[dict] = deque(maxlen=10)
        self._response_times: deque[float] = deque(maxlen=20)

    def inject_causal(self, causal: CausalMemoryGraph):
        """注入因果图谱引用"""
        self.causal = causal

    def inject_library(self, library: ImperialLibrary):
        """注入帝国图书馆引用"""
        self.library = library

    def _get_credentials(self):
        if self._credentials is None:
            self._credentials = load_llm_credentials()
            self._config = load_empire_config()
        return self._credentials, self._config

    async def call_llm(self, prompt: str, context: str = "", task_type: str = "") -> str:
        """调用 LLM v3.2 - 多模型路由 + 三维记忆上下文注入 + 主动检索"""
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

        # v3.2: 主动记忆检索 — 上下文变化时自动检索相关记忆
        proactive_ctx = ""
        if self.retriever:
            try:
                proactive_memories = self.retriever.on_context_change(prompt)
                if proactive_memories:
                    proactive_ctx = "\n".join(
                        f"- {m.content[:120]}" for m in proactive_memories[:3]
                    )
            except Exception:
                pass

        # v3.2: 因果推理上下文
        causal_ctx = ""
        if self.causal:
            try:
                # 尝试从 prompt 中提取关键词查询因果关系
                keywords = [w for w in prompt.lower().split() if len(w) > 2]
                for kw in keywords[:3]:
                    effects = self.causal.infer_effects(kw, min_confidence=0.5)
                    if effects:
                        causal_ctx += f"因果推理 [{kw}]: " + ", ".join(
                            f"{e}({c:.0%})" for e, c in effects[:3]
                        ) + "\n"
            except Exception:
                pass

        # v3.2: 帝国图书馆知识检索
        library_ctx = ""
        if self.library:
            try:
                kb_results = self.library.search_knowledge(
                    prompt[:200], top_k=2, requester_id=self.state.agent_id
                )
                if kb_results:
                    library_ctx = "\n".join(
                        f"- [{k.category}] {k.content[:120]}" for k in kb_results
                    )
            except Exception:
                pass

        # 组装记忆上下文
        memory_ctx = ""
        if self.memory3d:
            memory_ctx = self.memory3d.get_context_window(max_chars=1500)
        else:
            memory_ctx = self.memory.get_context_window(max_chars=1500)

        messages = [{"role": "system", "content": self.system_prompt}]

        if memory_ctx:
            messages.append({"role": "system", "content": f"【近期记忆】\n{memory_ctx}"})
        if proactive_ctx:
            messages.append({"role": "system", "content": f"【主动检索的记忆】\n{proactive_ctx}"})
        if causal_ctx:
            messages.append({"role": "system", "content": f"【因果推理】\n{causal_ctx}"})
        if library_ctx:
            messages.append({"role": "system", "content": f"【帝国图书馆知识】\n{library_ctx}"})
        if context:
            messages.append({"role": "user", "content": f"背景知识：\n{context}"})

        # 对话历史
        for hist in list(self.conversation_history)[-4:]:
            messages.append(hist)

        messages.append({"role": "user", "content": prompt})

        start_time = time.time()

        # v3.1: 优雅降级
        models_to_try = [model_info]
        if model_info.get("alias", "mimo") != "mimo":
            all_models = cfg.get("models", {})
            fallback = all_models.get("mimo", {}).copy()
            fallback["alias"] = "mimo"
            fallback["_fallback"] = True
            models_to_try.append(fallback)

        last_error = None
        for attempt_model in models_to_try:
            attempt_name = attempt_model.get("name", "mimo-v2.5-pro")
            try:
                result = call_llm_api(attempt_model, messages, creds["api_key"],
                                      timeout=cfg["llm"]["timeout_seconds"])

                elapsed = time.time() - start_time
                self._response_times.append(elapsed)

                actual_model = attempt_name
                self.tracker.log_usage(
                    self.state.agent_id,
                    result.get("input_tokens", 0),
                    result.get("output_tokens", 0),
                    model=actual_model,
                )

                content = result["content"]
                self.state.tasks_completed += 1

                if attempt_model.get("_fallback"):
                    log.info(f"Fallback: {self.state.agent_id} {model_name}→{actual_model}")
                    self._remember(
                        f"Fallback: {model_name} 失败，降级到 {actual_model}",
                        importance=0.4, tags=["fallback"],
                    )

                # 更新对话历史
                self.conversation_history.append({"role": "user", "content": prompt[:500]})
                self.conversation_history.append({"role": "assistant", "content": content[:500]})

                # 记忆
                self._remember(
                    f"任务: {prompt[:100]}... → 成功 (model={actual_model})",
                    importance=0.3, tags=["task", "success"],
                )

                if self._response_times:
                    self.state.avg_response_time = sum(self._response_times) / len(self._response_times)

                return content

            except Exception as e:
                last_error = e
                if attempt_model.get("_fallback"):
                    log.error(f"Fallback 也失败: {self.state.agent_id}: {e}")
                else:
                    log.warning(f"模型调用失败，尝试 fallback: {self.state.agent_id} {attempt_name}: {e}")
                continue

        self.state.tasks_failed += 1
        self._remember(f"任务失败: {last_error}", importance=0.6, tags=["error"])
        return f"[ERROR] {str(last_error)}"

    def _remember(self, text: str, importance: float = 0.5,
                  tags: list = None, task_id: str = ""):
        """统一记忆写入（兼容 Memory3D 和 AgentMemory）"""
        if self.memory3d:
            self.memory3d.form(
                text, function=MemoryFunction.EPISODIC,
                importance=importance, tags=tags or [], task_id=task_id,
            )
        else:
            self.memory.remember(text, importance=importance, tags=tags or [], task_id=task_id)

    async def process_task(self, task_id: str, prompt: str, context: str = "",
                           task_type: str = "") -> str:
        """处理任务"""
        self.state.status = "busy"
        self.state.current_task = task_id
        try:
            result = await self.call_llm(prompt, context, task_type)
            self.state.status = "idle"
            self.state.current_task = ""

            # v3.2: 自动从任务结果中学习因果关系
            if self.causal and len(result) > 20 and not result.startswith("[ERROR]"):
                try:
                    self._extract_causal_from_task(prompt, result)
                except Exception:
                    pass

            return result
        except Exception as e:
            self.state.status = "error"
            return f"[ERROR] {self.state.name} 处理失败: {e}"

    def _extract_causal_from_task(self, prompt: str, result: str):
        """从任务结果中自动提取因果关系（启发式）"""
        if not self.causal:
            return
        # 简单启发式：如果结果包含"导致"、"因为"、"所以"等因果词，提取关系
        causal_patterns = [
            (r"(.{2,20})导致(.{2,20})", 0.6),
            (r"(.{2,20})造成(.{2,20})", 0.6),
            (r"因为(.{2,20})[，,](.{2,20})", 0.5),
            (r"(.{2,20})因此(.{2,20})", 0.5),
            (r"(.{2,20})所以(.{2,20})", 0.5),
        ]
        import re
        for pattern, conf in causal_patterns:
            matches = re.findall(pattern, result)
            for cause, effect in matches[:2]:  # 最多提取 2 条
                self.causal.add_cause_effect(
                    cause.strip(), effect.strip(), conf,
                    metadata={"source_task": prompt[:50]},
                )

    def lifecycle_tick(self):
        """v3.2: Agent 生命周期管理"""
        if self.memory3d:
            self.memory3d.lifecycle_tick()
        if self.distiller:
            self.distiller.auto_distill_if_needed()

    def get_status(self) -> dict:
        status = {
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
            "uptime": round(time.time() - self.state.uptime_start, 0),
        }
        if self.memory3d:
            status["memory"] = self.memory3d.get_stats()
            status["memory_system"] = "Memory3D"
        else:
            status["memory"] = self.memory.get_stats()
            status["memory_system"] = "AgentMemory"

        if self.distiller:
            status["distillation"] = self.distiller.get_stats()
        if self.retriever:
            status["proactive_retriever"] = self.retriever.get_stats()
        if self.causal:
            status["causal_graph"] = self.causal.get_stats()

        return status


class _Memory3DCompat:
    """兼容层：让 Memory3D 看起来像 AgentMemory"""

    def __init__(self, memory3d: Memory3D):
        self._m = memory3d
        self.agent_id = memory3d.agent_id

    @property
    def short_term(self):
        """模拟 short_term deque 接口"""
        recent = sorted(self._m.engrams.values(), key=lambda e: e.last_accessed, reverse=True)
        return deque(
            [{"text": e.content, "importance": e.importance,
              "tags": e.tags, "time": e.created_at}
             for e in recent[:20]],
            maxlen=20,
        )

    @property
    def long_term(self):
        """模拟 long_term list 接口"""
        return [
            {"text": e.content, "importance": e.importance,
             "tags": e.tags, "time": e.created_at}
            for e in self._m.engrams.values()
            if e.importance >= 0.6
        ]

    def remember(self, text: str, importance: float = 0.5,
                 tags: list = None, task_id: str = ""):
        self._m.form(text, importance=importance, tags=tags or [], task_id=task_id)

    def recall_recent(self, n: int = 5) -> list[str]:
        return self._m.recall_recent(n)

    def recall_important(self, n: int = 3) -> list[str]:
        return self._m.recall_important(n)

    def get_context_window(self, max_chars: int = 1500) -> str:
        return self._m.get_context_window(max_chars)

    def get_stats(self) -> dict:
        return self._m.get_stats()
