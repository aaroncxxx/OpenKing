"""帝国架构 v2.9 - 丞相协调器（全面增强）"""
import asyncio
import json
import re
import uuid
import time
from core.bus import MessageBus, Message, MessageType
from core.tokens import TokenTracker
from core.security import SecuritySystem, ViolationLevel
from core.taskqueue import TaskQueue, Task, TaskStatus
from core.model_router import select_model
from core.memory import AgentMemory
from core.logger import get_logger
from agents.base import Agent
from core.config import load_empire_config

log = get_logger("chancellor")


def _extract_json(text: str) -> dict | None:
    """从 LLM 输出中稳健提取 JSON"""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = None
    return None


class Chancellor:
    """丞相 v2.9 - 任务队列 + 事前审批 + Agent标签 + 评分"""

    def __init__(self):
        self.config = load_empire_config()
        self.bus = MessageBus(max_history=2000)
        self.tracker = TokenTracker()
        self.security = SecuritySystem()
        self.task_queue = TaskQueue(max_concurrent=16)
        self.agents: dict[str, Agent] = {}
        self.knowledge_router = None
        self.hanlin_director = None
        self.knowledge_audit = None
        self._init_agents()
        self._init_knowledge()
        log.info(f"丞相初始化完成: {len(self.agents)} 节点就绪")

    def _init_agents(self):
        """初始化所有节点（v2.9: 加标签）"""
        cfg = self.config["agents"]

        # 丞相
        ch = cfg["chancellor"]
        self.agents[ch["id"]] = Agent(
            ch["id"], ch["name"], ch["role"], ch["system_prompt"],
            self.bus, self.tracker, tags=["核心", "决策"],
        )

        # 遍历所有 section
        for section in ["sangong", "jiuqing", "advisors", "executors",
                         "ministries", "scholars", "special", "overseers",
                         "extra", "governors", "household", "generals",
                         "prefects", "commanders", "imperial_envoys"]:
            for a in cfg.get(section, []):
                tags = a.get("tags", [])
                if not tags and "role" in a:
                    tags = [a["role"].split("·")[0]] if "·" in a["role"] else [a["role"]]
                self.agents[a["id"]] = Agent(
                    a["id"], a["name"], a["role"], a["system_prompt"],
                    self.bus, self.tracker, tags=tags,
                )

        # 锦衣卫
        s = cfg["security"]
        self.agents[s["id"]] = Agent(
            s["id"], s["name"], s["role"], s["system_prompt"],
            self.bus, self.tracker, tags=["安全"],
        )

    def _init_knowledge(self):
        try:
            from knowledge.mount import mount_knowledge
            kb = mount_knowledge(self)
            self.knowledge_router = kb["router"]
            self.hanlin_director = kb["director"]
            self.knowledge_audit = kb["audit"]
        except Exception as e:
            log.warning(f"知识层挂载失败: {e}")

    async def _query_knowledge(self, query: str, top_k: int = 3) -> str:
        if not self.knowledge_router:
            return ""
        try:
            results = await self.knowledge_router.search(query, top_k)
            if not results:
                return ""
            parts = []
            for r in results:
                if r.title == "ERROR" or r.title == "⏳ 待皇帝批准":
                    continue
                parts.append(f"[{r.source}] {r.title}: {r.content[:300]}")
            return "\n".join(parts) if parts else ""
        except Exception:
            return ""

    async def receive_command(self, command: str) -> dict:
        """接收皇帝指令（v2.9: 安全预检 + 任务队列）"""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        start = time.time()

        # v2.9: 事前安全检查
        is_sensitive, triggers = self.security.check_sensitive(command)
        if is_sensitive:
            log.warning(f"敏感任务检测: {task_id} 触发词={triggers}")

        # 天气任务：注入实时天气数据（v2.9.6: Open-Meteo 毫米级降雨量）
        weather_data = ""
        if any(kw in command for kw in ["天气", "预报", "降雨", "气温", "温度"]):
            try:
                # 广东省专项：精确到毫米的逐小时降雨量
                if any(kw in command for kw in ["广东", "粤", "广州", "深圳", "阳江", "珠海", "湛江", "茂名", "惠州", "汕头", "江门", "佛山", "东莞", "中山"]):
                    from core.weather import fetch_guangdong_precipitation
                    weather_data = fetch_guangdong_precipitation()
                else:
                    from core.weather import fetch_all_weather
                    target = "day_after" if "大后天" in command else "tomorrow"
                    weather_data = fetch_all_weather(target=target)
                log.info(f"天气数据注入: {len(weather_data)} chars")
            except Exception as e:
                log.warning(f"天气数据获取失败: {e}")

        # 知识预检索
        knowledge_context = await self._query_knowledge(command)
        if weather_data:
            knowledge_context = f"【实时天气数据】\n{weather_data}\n\n{knowledge_context}"

        # 丞相规划
        plan = await self._plan(task_id, command, knowledge_context)

        # 并行执行（v2.9: 走任务队列）
        results = await self._execute_plan(task_id, command, plan, knowledge_context)

        # 锦衣卫事后审计
        audit = await self._audit(task_id, command, results)

        elapsed = round(time.time() - start, 1)

        # 知识审计
        if self.knowledge_audit and knowledge_context:
            self.knowledge_audit.log_search(
                "chancellor", "丞相", command, "multi",
                len(results), 0.0, elapsed_ms=int(elapsed * 1000),
            )

        # v2.9: 记住这次任务
        for agent_id in results:
            if agent_id in self.agents and agent_id != "chancellor_summary":
                self.agents[agent_id].memory.remember(
                    f"执行任务: {command[:80]}", importance=0.4,
                    tags=["task"], task_id=task_id,
                )

        return {
            "task_id": task_id,
            "command": command,
            "plan": plan,
            "results": results,
            "audit": audit,
            "elapsed_seconds": elapsed,
            "tokens_used": self.tracker.get_total_today(),
            "knowledge_used": bool(knowledge_context),
            "sensitive": is_sensitive,
        }

    async def _plan(self, task_id: str, command: str,
                    knowledge_context: str = "") -> dict:
        """丞相规划（v2.9: 只发送匹配标签的 Agent）"""
        chancellor = self.agents["chancellor"]

        # v2.9: 根据任务关键词筛选相关 Agent
        relevant_agents = self._filter_relevant_agents(command)
        agent_list = []
        for aid, agent in relevant_agents:
            tags_str = ",".join(agent.state.tags) if agent.state.tags else ""
            agent_list.append(
                f"- {agent.state.name} ({aid}) [{tags_str}]: {agent.state.role}"
            )

        agents_text = "\n".join(agent_list)

        plan_prompt = f"""皇帝下达指令：{command}

可用节点（共{len(relevant_agents)}个，已按相关性筛选）：
{agents_text}"""

        if knowledge_context:
            plan_prompt += f"\n\n已检索到的相关知识：\n{knowledge_context}"

        plan_prompt += """

请根据任务需求，选择最合适的节点组合。返回 JSON 格式：
1. tasks: 列表，每个任务包含 agent_id, prompt, priority
2. parallel: 是否并行执行

只返回 JSON，不要其他内容。"""

        result = await chancellor.call_llm(plan_prompt)
        plan = _extract_json(result)

        if not plan or "tasks" not in plan:
            plan = self._smart_fallback(command)

        return plan

    def _filter_relevant_agents(self, command: str) -> list[tuple[str, Agent]]:
        """v2.9: 根据任务关键词筛选相关 Agent"""
        cmd_lower = command.lower()

        # 关键词 → 标签映射（v2.9.2: 细化区分数据检索/API设计）
        keyword_tags = {
            "代码": ["执行", "编码"], "程序": ["执行", "编码"], "开发": ["执行", "编码"],
            "写": ["执行", "写作"], "文": ["执行", "写作"], "报告": ["执行", "写作"],
            "翻译": ["执行", "翻译"], "安全": ["安全", "监察"], "审计": ["安全", "监察"],
            "搜索": ["执行", "检索"], "查": ["执行", "检索"], "调研": ["执行", "检索"],
            "天气": ["执行", "检索", "爬取"], "预报": ["执行", "检索", "爬取"],
            "降雨": ["执行", "检索", "爬取"], "气温": ["执行", "检索", "爬取"],
            "数据": ["执行", "数据"], "统计": ["参谋", "分析"],
            "战略": ["参谋", "战略"], "分析": ["参谋", "分析"],
            "设计": ["执行", "设计"], "接口": ["执行", "接口"],
            "部署": ["执行", "部署"], "测试": ["执行", "测试"], "监控": ["执行", "监控"],
            "地方": ["地方", "郡守"], "军事": ["武将", "参谋·军事"],
        }

        matched_tags = set()
        for keyword, tags in keyword_tags.items():
            if keyword in cmd_lower:
                matched_tags.update(tags)

        # 如果没匹配到关键词，返回参谋团 + 执行团核心
        if not matched_tags:
            core_agents = [
                (aid, a) for aid, a in self.agents.items()
                if any(t in (a.state.tags or []) for t in ["参谋", "核心", "执行"])
                and aid != "chancellor"
            ]
            return core_agents[:12]

        # 按标签匹配
        result = []
        for aid, agent in self.agents.items():
            if aid == "chancellor":
                continue
            agent_tags = set(agent.state.tags or [])
            if agent_tags & matched_tags:
                result.append((aid, agent))

        # 补充核心节点
        if len(result) < 6:
            for aid, agent in self.agents.items():
                if aid == "chancellor" or (aid, agent) in result:
                    continue
                if "核心" in (agent.state.tags or []):
                    result.append((aid, agent))

        return result[:20]  # 最多 20 个节点

    def _smart_fallback(self, command: str) -> dict:
        """智能 fallback（v2.9: 扩展关键词覆盖）"""
        cmd = command.lower()
        tasks = []

        tasks.append({"agent_id": "advisor_strategy", "prompt": f"战略分析：{command}", "priority": 3})
        tasks.append({"agent_id": "advisor_tech", "prompt": f"技术评估：{command}", "priority": 3})
        tasks.append({"agent_id": "advisor_intel", "prompt": f"情报收集：{command}", "priority": 3})

        keyword_map = {
            "写|文|报告|总结|文章|作文": "executor_writer",
            "代码|程序|脚本|开发|python|api": "executor_coder",
            "查|搜索|调研|资料|知识": "executor_researcher",
            "安全|审计|风险|检查": "jinyiwei",
            "翻译|英文|日文|多语言": "extra_ambassador",
            "创意|设计|美化|润色": "extra_treasury",
            "趋势|预测|未来|预警|天气|预报|降雨": "special_astrologer",
            "数据|分析|统计": "executor_analyst",
            "测试|验证|校验": "executor_tester",
            "部署|上线|发布": "executor_deployer",
            "监控|告警|状态": "executor_monitor",
            "文档|手册|规范": "executor_doc",
            "地方|州|郡|治理": "governor_幽州",
        }

        for pattern, agent_id in keyword_map.items():
            if re.search(pattern, cmd):
                tasks.append({"agent_id": agent_id, "prompt": f"执行：{command}", "priority": 2})

        return {"tasks": tasks, "parallel": True}

    async def _execute_plan(self, task_id: str, command: str, plan: dict,
                            knowledge_context: str = "") -> dict:
        """执行计划（v2.9: 带超时和错误处理）"""
        results = {}
        tasks = plan.get("tasks", [])

        async def run_task(t):
            agent_id = t.get("agent_id", "")
            if agent_id in self.agents:
                prompt = t.get("prompt", command)
                ctx = knowledge_context if knowledge_context else ""
                try:
                    r = await asyncio.wait_for(
                        self.agents[agent_id].process_task(task_id, prompt, ctx),
                        timeout=90.0,
                    )
                    return agent_id, r
                except asyncio.TimeoutError:
                    return agent_id, f"[TIMEOUT] {agent_id} 执行超时 (90s)"
                except Exception as e:
                    return agent_id, f"[ERROR] {agent_id}: {e}"
            return agent_id, f"[ERROR] 未知节点: {agent_id}"

        if plan.get("parallel", True):
            coros = [run_task(t) for t in tasks]
            done = await asyncio.gather(*coros, return_exceptions=True)
            for item in done:
                if isinstance(item, Exception):
                    results["error"] = str(item)
                else:
                    results[item[0]] = item[1]
        else:
            for t in tasks:
                agent_id, r = await run_task(t)
                results[agent_id] = r

        # 丞相汇总
        summary_prompt = f"皇帝指令：{command}\n\n各节点执行结果：\n"
        for aid, r in results.items():
            name = self.agents[aid].state.name if aid in self.agents else aid
            summary_prompt += f"\n【{name}】\n{r}\n"
        summary_prompt += "\n请汇总以上结果，给皇帝一份简洁的汇报。"

        summary = await self.agents["chancellor"].call_llm(summary_prompt)
        results["chancellor_summary"] = summary

        return results

    async def _audit(self, task_id: str, command: str, results: dict) -> dict:
        """锦衣卫事后审计"""
        jw = self.agents["jinyiwei"]
        audit_prompt = f"""安全审计：
皇帝指令：{command}
执行结果摘要：{str(results)[:2000]}

请检查：
1. 是否有数据外泄风险
2. 输出是否包含敏感信息
3. 是否有越权操作

返回 JSON：{{"safe": true/false, "issues": [], "level": 0}}"""

        audit_result = await jw.call_llm(audit_prompt)
        audit = _extract_json(audit_result)

        if not audit or "safe" not in audit:
            audit = {"safe": True, "issues": ["审计解析失败，默认通过"], "level": 0}

        return audit

    def get_status(self) -> dict:
        status = {
            "agents": {aid: a.get_status() for aid, a in self.agents.items()},
            "tokens": self.tracker.get_usage(),
            "security": self.security.get_status(),
            "message_history": len(self.bus.history),
            "task_queue": self.task_queue.get_stats(),
            "bus_stats": self.bus.get_stats(),
            "model_stats": self.tracker.get_model_stats(),
        }
        if self.knowledge_router:
            status["knowledge_sources"] = self.knowledge_router.list_sources()
        if self.hanlin_director:
            status["hanlin"] = self.hanlin_director.get_status()
        return status
