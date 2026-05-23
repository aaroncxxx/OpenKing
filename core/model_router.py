"""帝国架构 v3.0 - 多模型路由器（MIMO / DeepSeek / Claude / GPT-4 / Ollama）"""
import json
import os
import urllib.request
import urllib.error
from core.logger import get_logger
from core.config import load_empire_config, get_model_config

log = get_logger("model_router")

# v3.0: 任务类型 → 最优模型映射
TASK_MODEL_MAP = {
    # 代码类 → DeepSeek 便宜好用
    "code": ["deepseek", "mimo", "gpt4"],
    "coding": ["deepseek", "mimo", "gpt4"],
    "编程": ["deepseek", "mimo", "gpt4"],
    "代码": ["deepseek", "mimo", "gpt4"],

    # 分析类 → MIMO 或 Claude
    "analysis": ["mimo", "claude", "gpt4"],
    "分析": ["mimo", "claude", "gpt4"],
    "战略": ["claude", "mimo", "gpt4"],

    # 创意类 → Claude
    "creative": ["claude", "gpt4", "mimo"],
    "写作": ["claude", "mimo", "gpt4"],
    "创意": ["claude", "gpt4", "mimo"],

    # 翻译类 → 任意
    "translate": ["mimo", "deepseek", "claude"],
    "翻译": ["mimo", "deepseek", "claude"],

    # 检索/摘要 → DeepSeek 便宜
    "search": ["deepseek", "mimo"],
    "检索": ["deepseek", "mimo"],
    "摘要": ["deepseek", "mimo"],

    # 安全审计 → Claude 严谨
    "security": ["claude", "mimo", "gpt4"],
    "安全": ["claude", "mimo", "gpt4"],
}

# Agent 角色 → 优先模型
ROLE_MODEL_MAP = {
    "丞相": "mimo",
    "三公": "mimo",
    "参谋": "mimo",
    "执行": "deepseek",
    "监察": "deepseek",
    "翰林": "mimo",
    "武将": "deepseek",
    "郡守": "deepseek",
    "锦衣卫": "claude",
}


def select_model(agent_role: str, task_prompt: str = "", task_type: str = "") -> dict:
    """v3.0: 智能模型选择（多模型 + 任务类型 + 角色）"""
    config = load_empire_config()
    models = config.get("models", {})

    # 1. 按任务类型选模型
    if task_type and task_type in TASK_MODEL_MAP:
        for model_alias in TASK_MODEL_MAP[task_type]:
            if model_alias in models:
                model = models[model_alias].copy()
                model["alias"] = model_alias
                log.debug(f"任务类型路由: {task_type} → {model['name']}")
                return model

    # 2. 按关键词选模型
    task_lower = task_prompt.lower()
    for keywords, candidates in TASK_MODEL_MAP.items():
        if keywords in task_lower:
            for model_alias in candidates:
                if model_alias in models:
                    model = models[model_alias].copy()
                    model["alias"] = model_alias
                    log.debug(f"关键词路由: {keywords} → {model['name']}")
                    return model

    # 3. 按角色选模型
    for role_prefix, model_alias in ROLE_MODEL_MAP.items():
        if role_prefix in agent_role:
            if model_alias in models:
                model = models[model_alias].copy()
                model["alias"] = model_alias
                log.debug(f"角色路由: {agent_role} → {model['name']}")
                return model

    # 4. 默认 MIMO
    model = models.get("mimo", get_model_config("mimo")).copy()
    model["alias"] = "mimo"
    return model


def call_llm_api(model_config: dict, messages: list[dict], api_key: str,
                 timeout: int = 60) -> dict:
    """v3.0: 统一 LLM 调用（支持 MIMO/DeepSeek/Claude/GPT-4/Ollama）"""
    provider = model_config.get("provider", "mimo")
    base_url = model_config.get("base_url", "")
    model_name = model_config.get("name", "mimo-v2.5-pro")
    max_tokens = model_config.get("max_tokens", 4096)
    temperature = model_config.get("temperature", 0.7)

    if provider == "anthropic":
        return _call_anthropic(base_url, model_name, messages, api_key, max_tokens, temperature, timeout)
    else:
        return _call_openai_compatible(base_url, model_name, messages, api_key, max_tokens, temperature, timeout)


def _call_openai_compatible(base_url: str, model: str, messages: list[dict],
                            api_key: str, max_tokens: int, temperature: float, timeout: int) -> dict:
    """OpenAI 兼容接口（MIMO/DeepSeek/GPT-4/Ollama）"""
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": model, "messages": messages,
        "max_tokens": max_tokens, "temperature": temperature,
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())

    usage = data.get("usage", {})
    return {
        "content": data["choices"][0]["message"]["content"],
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "model": model,
    }


def _call_anthropic(base_url: str, model: str, messages: list[dict],
                    api_key: str, max_tokens: int, temperature: float, timeout: int) -> dict:
    """Anthropic Claude 接口"""
    url = base_url.rstrip("/") + "/messages"

    # 转换消息格式
    system_text = ""
    claude_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_text += msg["content"] + "\n"
        else:
            claude_messages.append(msg)

    body = json.dumps({
        "model": model, "messages": claude_messages,
        "max_tokens": max_tokens, "temperature": temperature,
        "system": system_text.strip(),
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())

    usage = data.get("usage", {})
    return {
        "content": data["content"][0]["text"],
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "model": model,
    }


def get_available_models() -> dict:
    """获取所有可用模型"""
    config = load_empire_config()
    return config.get("models", {})
