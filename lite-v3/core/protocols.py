"""帝国架构 v3.1 - 协议标准化（MCP + A2A）
MCP: Model Context Protocol - 工具/模型/资源统一调用
A2A: Agent-to-Agent - 跨平台 Agent 互联互通
"""
import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Optional
from core.logger import get_logger

log = get_logger("protocol")


# ════════════════════════════════════════════
# MCP (Model Context Protocol) 实现
# ════════════════════════════════════════════

@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: dict  # JSON Schema
    handler: Optional[Callable] = None


@dataclass
class MCPResource:
    """MCP 资源定义"""
    uri: str
    name: str
    description: str
    mime_type: str = "text/plain"


@dataclass
class MCPPrompt:
    """MCP Prompt 模板"""
    name: str
    description: str
    arguments: list[dict] = field(default_factory=list)


class MCPServer:
    """MCP Server - 标准化工具/资源/Prompt 接口

    兼容 MCP 规范：https://spec.modelcontextprotocol.io
    """

    def __init__(self, name: str = "empire-architecture", version: str = "3.1.0"):
        self.name = name
        self.version = version
        self.tools: dict[str, MCPTool] = {}
        self.resources: dict[str, MCPResource] = {}
        self.prompts: dict[str, MCPPrompt] = {}

    def register_tool(self, tool: MCPTool):
        """注册 MCP 工具"""
        self.tools[tool.name] = tool
        log.info(f"MCP 工具注册: {tool.name}")

    def register_resource(self, resource: MCPResource):
        """注册 MCP 资源"""
        self.resources[resource.uri] = resource

    def register_prompt(self, prompt: MCPPrompt):
        """注册 MCP Prompt"""
        self.prompts[prompt.name] = prompt

    def list_tools(self) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
            for t in self.tools.values()
        ]

    def list_resources(self) -> list[dict]:
        return [
            {"uri": r.uri, "name": r.name, "description": r.description, "mimeType": r.mime_type}
            for r in self.resources.values()
        ]

    def list_prompts(self) -> list[dict]:
        return [
            {"name": p.name, "description": p.description, "arguments": p.arguments}
            for p in self.prompts.values()
        ]

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """调用 MCP 工具"""
        if name not in self.tools:
            return {"error": f"未知工具: {name}"}

        tool = self.tools[name]
        if not tool.handler:
            return {"error": f"工具 {name} 无处理器"}

        try:
            result = tool.handler(**arguments)
            return {"content": [{"type": "text", "text": str(result)}]}
        except Exception as e:
            return {"error": str(e)}

    def get_server_info(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"subscribe": True, "listChanged": True},
                "prompts": {"listChanged": True},
            },
        }


class MCPClient:
    """MCP Client - 连接外部 MCP Server"""

    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")
        self._tools_cache: list[dict] = []

    def discover_tools(self) -> list[dict]:
        """发现远程 MCP Server 的工具"""
        try:
            req = urllib.request.Request(f"{self.server_url}/tools")
            with urllib.request.urlopen(req, timeout=10) as resp:
                self._tools_cache = json.loads(resp.read())
            return self._tools_cache
        except Exception as e:
            log.error(f"MCP 工具发现失败: {e}")
            return []

    async def call_remote_tool(self, name: str, arguments: dict) -> dict:
        """调用远程 MCP 工具"""
        body = json.dumps({"name": name, "arguments": arguments}).encode()
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(
            f"{self.server_url}/tools/call", data=body, headers=headers
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())


# ════════════════════════════════════════════
# A2A (Agent-to-Agent) 协议实现
# ════════════════════════════════════════════

@dataclass
class A2AAgentCard:
    """A2A Agent Card - 描述 Agent 能力（兼容 A2A 规范）"""
    name: str
    description: str
    url: str
    version: str = "1.0"
    capabilities: list[str] = field(default_factory=list)
    input_modes: list[str] = field(default_factory=lambda: ["text"])
    output_modes: list[str] = field(default_factory=lambda: ["text"])
    authentication: dict = field(default_factory=dict)


@dataclass
class A2ATask:
    """A2A 任务"""
    task_id: str
    status: str = "submitted"  # submitted, working, completed, failed
    messages: list[dict] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class A2AServer:
    """A2A Server - 让 Empire Agent 可被外部 Agent 调用

    兼容 A2A 规范：https://github.com/google/A2A
    """

    def __init__(self, agent_card: A2AAgentCard):
        self.agent_card = agent_card
        self.tasks: dict[str, A2ATask] = {}
        self._task_handler: Optional[Callable] = None

    def set_task_handler(self, handler: Callable):
        """设置任务处理器"""
        self._task_handler = handler

    def get_agent_card(self) -> dict:
        return {
            "name": self.agent_card.name,
            "description": self.agent_card.description,
            "url": self.agent_card.url,
            "version": self.agent_card.version,
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
                "stateTransitionHistory": True,
            },
            "defaultInputModes": self.agent_card.input_modes,
            "defaultOutputModes": self.agent_card.output_modes,
            "skills": [
                {"id": cap, "name": cap, "description": f"能力: {cap}"}
                for cap in self.agent_card.capabilities
            ],
        }

    async def handle_task(self, task_request: dict) -> dict:
        """处理 A2A 任务"""
        task_id = task_request.get("id", f"a2a_{int(time.time()*1000)}")
        message = task_request.get("message", {})

        task = A2ATask(
            task_id=task_id,
            status="working",
            messages=[message],
        )
        self.tasks[task_id] = task

        if self._task_handler:
            try:
                result = await self._task_handler(message)
                task.status = "completed"
                task.artifacts = [{"parts": [{"type": "text", "text": str(result)}]}]
            except Exception as e:
                task.status = "failed"
                task.metadata["error"] = str(e)
        else:
            task.status = "completed"
            task.artifacts = [{"parts": [{"type": "text", "text": "无处理器"}]}]

        return {
            "id": task_id,
            "status": task.status,
            "artifacts": task.artifacts,
        }


class A2AClient:
    """A2A Client - 调用外部 Agent"""

    def __init__(self):
        self._known_agents: dict[str, A2AAgentCard] = {}

    def discover_agent(self, url: str) -> Optional[A2AAgentCard]:
        """发现远程 Agent"""
        try:
            well_known_url = f"{url.rstrip('/')}/.well-known/agent.json"
            req = urllib.request.Request(well_known_url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            card = A2AAgentCard(
                name=data.get("name", ""),
                description=data.get("description", ""),
                url=url,
                version=data.get("version", "1.0"),
                capabilities=[s["id"] for s in data.get("skills", [])],
            )
            self._known_agents[url] = card
            log.info(f"A2A Agent 发现: {card.name} @ {url}")
            return card
        except Exception as e:
            log.error(f"A2A Agent 发现失败: {url}: {e}")
            return None

    async def send_task(self, agent_url: str, message: str) -> dict:
        """向远程 Agent 发送任务"""
        task_id = f"a2a_{int(time.time()*1000)}"
        body = json.dumps({
            "id": task_id,
            "message": {"role": "user", "parts": [{"type": "text", "text": message}]},
        }).encode()
        headers = {"Content-Type": "application/json"}

        req = urllib.request.Request(
            f"{agent_url.rstrip('/')}/tasks/send", data=body, headers=headers
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())

    def list_known_agents(self) -> list[dict]:
        return [
            {"name": c.name, "url": c.url, "capabilities": c.capabilities}
            for c in self._known_agents.values()
        ]


# ════════════════════════════════════════════
# 标准 API 接口
# ════════════════════════════════════════════

class EmpireAPI:
    """Empire Architecture 标准 API 接口

    提供 RESTful API，允许第三方基于 Empire 构建应用
    """

    def __init__(self, chancellor):
        self.chancellor = chancellor
        self.mcp_server = MCPServer()
        self.a2a_server = None
        self._register_default_tools()

    def _register_default_tools(self):
        """注册默认 MCP 工具"""
        self.mcp_server.register_tool(MCPTool(
            name="empire_execute",
            description="在帝国架构中执行任务",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "任务指令"},
                    "autonomous": {"type": "boolean", "description": "是否自治模式", "default": False},
                },
                "required": ["command"],
            },
        ))

        self.mcp_server.register_tool(MCPTool(
            name="empire_status",
            description="获取帝国状态",
            input_schema={"type": "object", "properties": {}},
        ))

        self.mcp_server.register_tool(MCPTool(
            name="empire_agents",
            description="列出所有 Agent",
            input_schema={"type": "object", "properties": {}},
        ))

    def setup_a2a(self, public_url: str):
        """设置 A2A 服务"""
        card = A2AAgentCard(
            name="Empire Architecture",
            description="基于三公九卿制的 AI 多智能体协作系统",
            url=public_url,
            version="3.1.0",
            capabilities=[
                "task_execution", "knowledge_retrieval",
                "weather_analysis", "stock_analysis",
                "multimodal_processing",
            ],
        )
        self.a2a_server = A2AServer(card)

    def get_openapi_spec(self) -> dict:
        """生成 OpenAPI 规格"""
        return {
            "openapi": "3.0.0",
            "info": {
                "title": "Empire Architecture API",
                "version": "3.1.0",
                "description": "基于三公九卿制的 AI 多智能体协作系统 API",
            },
            "paths": {
                "/api/execute": {
                    "post": {
                        "summary": "执行任务",
                        "requestBody": {
                            "content": {"application/json": {"schema": {
                                "type": "object",
                                "properties": {
                                    "command": {"type": "string"},
                                    "autonomous": {"type": "boolean"},
                                },
                            }}},
                        },
                    },
                },
                "/api/status": {"get": {"summary": "帝国状态"}},
                "/api/agents": {"get": {"summary": "节点列表"}},
                "/api/tokens": {"get": {"summary": "Token 使用"}},
                "/api/evolution": {"get": {"summary": "进化状态"}},
            },
        }
