"""帝国架构 v3.0 - 配置加载（平滑升级 v2.x）"""
import json
import os
import time
import threading
from pathlib import Path
from core.logger import get_logger

log = get_logger("config")

_config_cache = None
_config_mtime = 0
_lock = threading.Lock()

DEFAULT_CONFIG = {
    "version": "3.0.0",
    "llm": {
        "timeout_seconds": 60,
        "max_budget_daily": 100000,
    },
    "models": {
        "mimo": {
            "provider": "mimo",
            "name": "mimo-v2.5-pro",
            "base_url": "https://api.xiaomimimo.com/v1",
            "max_tokens": 4096,
            "temperature": 0.7,
            "cost_per_1k_input": 0.05,
            "cost_per_1k_output": 0.1,
        },
        "deepseek": {
            "provider": "deepseek",
            "name": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "max_tokens": 4096,
            "temperature": 0.7,
            "cost_per_1k_input": 0.001,
            "cost_per_1k_output": 0.002,
        },
        "claude": {
            "provider": "anthropic",
            "name": "claude-sonnet-4-20250514",
            "base_url": "https://api.anthropic.com/v1",
            "max_tokens": 4096,
            "temperature": 0.7,
            "cost_per_1k_input": 0.003,
            "cost_per_1k_output": 0.015,
        },
        "gpt4": {
            "provider": "openai",
            "name": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
            "max_tokens": 4096,
            "temperature": 0.7,
            "cost_per_1k_input": 0.005,
            "cost_per_1k_output": 0.015,
        },
        "ollama": {
            "provider": "ollama",
            "name": "llama3",
            "base_url": "http://localhost:11434/v1",
            "max_tokens": 2048,
            "temperature": 0.5,
            "cost_per_1k_input": 0,
            "cost_per_1k_output": 0,
        },
    },
    "evolution": {
        "enabled": True,
        "eval_interval_tasks": 10,
        "promotion_threshold": 1.3,
        "demotion_threshold": 0.7,
        "max_history": 100,
    },
    "plugins": {
        "enabled": True,
        "clawhub_integration": True,
        "custom_agents_dir": "plugins/agents",
    },
    "realtime": {
        "enabled": False,
        "monitor_interval_seconds": 300,
        "webhooks": [],
    },
    "dashboard": {
        "enabled": True,
        "port": 8501,
        "theme": "dark",
    },
}


def load_empire_config(config_path: str = None) -> dict:
    """加载帝国配置（v2.x 兼容 + v3.0 扩展）"""
    global _config_cache, _config_mtime

    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

    try:
        mtime = os.path.getmtime(config_path)
    except FileNotFoundError:
        log.warning(f"配置文件不存在: {config_path}，使用默认配置")
        return DEFAULT_CONFIG.copy()

    with _lock:
        if _config_cache and _config_mtime == mtime:
            return _config_cache

        with open(config_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)

        # 平滑升级：合并 v2.x 配置到 v3.0 默认配置
        config = _merge_config(DEFAULT_CONFIG, user_config)
        config["_config_path"] = config_path
        config["_loaded_at"] = time.time()

        _config_cache = config
        _config_mtime = mtime
        log.info(f"配置加载完成: v{config.get('version', '2.x')}")
        return config


def _merge_config(default: dict, user: dict) -> dict:
    """深度合并配置（用户配置优先，缺失字段用默认值填充）"""
    result = default.copy()
    for key, value in user.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value
    return result


def load_llm_credentials() -> dict | None:
    """加载 LLM 凭据（从环境变量）"""
    api_key = os.environ.get("MIMO_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("MIMO_API_ENDPOINT", "https://api.xiaomimimo.com/v1")

    if not api_key:
        log.warning("未找到 LLM API Key（设置 MIMO_API_KEY 或 OPENAI_API_KEY）")
        return None

    return {"api_key": api_key, "base_url": base_url}


def get_model_config(model_alias: str = None) -> dict:
    """获取模型配置"""
    config = load_empire_config()
    models = config.get("models", {})

    if model_alias and model_alias in models:
        return models[model_alias]

    return models.get("mimo", DEFAULT_CONFIG["models"]["mimo"])


def reload_config():
    """强制重新加载配置"""
    global _config_cache, _config_mtime
    with _lock:
        _config_cache = None
        _config_mtime = 0
    return load_empire_config()
