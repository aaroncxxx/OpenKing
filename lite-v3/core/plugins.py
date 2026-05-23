"""帝国架构 v3.0 - 插件系统（热插拔 + ClawHub + 自定义 Agent）"""
import json
import os
import importlib.util
import sys
from pathlib import Path
from core.logger import get_logger

log = get_logger("plugins")


class PluginManager:
    """插件管理器 v3.0 - 热插拔 Agent"""

    def __init__(self, plugins_dir: str = None):
        if plugins_dir is None:
            plugins_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")
        self.plugins_dir = plugins_dir
        os.makedirs(plugins_dir, exist_ok=True)
        self.loaded_plugins: dict[str, dict] = {}
        self.custom_agents: dict[str, type] = {}

    def discover_plugins(self) -> list[dict]:
        """发现所有可用插件"""
        plugins = []
        if not os.path.exists(self.plugins_dir):
            return plugins

        for item in os.listdir(self.plugins_dir):
            plugin_dir = os.path.join(self.plugins_dir, item)
            manifest_path = os.path.join(plugin_dir, "manifest.json")
            if os.path.isfile(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    manifest["_dir"] = plugin_dir
                    manifest["_id"] = item
                    plugins.append(manifest)
                except Exception as e:
                    log.warning(f"插件清单读取失败: {item}: {e}")

        return plugins

    def load_plugin(self, plugin_id: str) -> bool:
        """加载单个插件"""
        plugin_dir = os.path.join(self.plugins_dir, plugin_id)
        manifest_path = os.path.join(plugin_dir, "manifest.json")
        main_path = os.path.join(plugin_dir, "main.py")

        if not os.path.exists(main_path):
            log.warning(f"插件入口不存在: {main_path}")
            return False

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            # 动态加载插件模块
            spec = importlib.util.spec_from_file_location(f"plugin_{plugin_id}", main_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"plugin_{plugin_id}"] = module
            spec.loader.exec_module(module)

            # 注册 Agent 类
            if hasattr(module, "register"):
                agents = module.register()
                if isinstance(agents, dict):
                    self.custom_agents.update(agents)

            self.loaded_plugins[plugin_id] = manifest
            log.info(f"插件加载成功: {plugin_id} v{manifest.get('version', '?')}")
            return True

        except Exception as e:
            log.error(f"插件加载失败: {plugin_id}: {e}")
            return False

    def unload_plugin(self, plugin_id: str) -> bool:
        """卸载插件"""
        if plugin_id in self.loaded_plugins:
            del self.loaded_plugins[plugin_id]
            # 移除自定义 Agent
            to_remove = [k for k in self.custom_agents if k.startswith(f"{plugin_id}.")]
            for k in to_remove:
                del self.custom_agents[k]
            log.info(f"插件卸载: {plugin_id}")
            return True
        return False

    def get_custom_agent(self, agent_key: str) -> type | None:
        return self.custom_agents.get(agent_key)

    def list_plugins(self) -> list[dict]:
        return [
            {"id": pid, "name": p.get("name", pid), "version": p.get("version", "?"),
             "description": p.get("description", ""), "loaded": pid in self.loaded_plugins}
            for pid, p in self.loaded_plugins.items()
        ]

    def install_from_clawhub(self, slug: str) -> bool:
        """从 ClawHub 安装技能插件"""
        try:
            import subprocess
            result = subprocess.run(
                ["clawhub", "install", slug, "--dir", self.plugins_dir],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                log.info(f"ClawHub 安装成功: {slug}")
                return True
            else:
                log.error(f"ClawHub 安装失败: {result.stderr}")
                return False
        except Exception as e:
            log.error(f"ClawHub 安装异常: {e}")
            return False
