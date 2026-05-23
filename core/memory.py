"""帝国架构 v3.0 - Agent 记忆系统"""
import json
import os
import time
from collections import deque
from core.logger import get_logger

log = get_logger("memory")


class AgentMemory:
    """Agent 记忆 v3.0 - 短期 + 长期 + 任务评估"""

    def __init__(self, agent_id: str, data_dir: str = None):
        self.agent_id = agent_id
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "memory")
        os.makedirs(data_dir, exist_ok=True)
        self._path = os.path.join(data_dir, f"{agent_id}.json")
        self.short_term: deque[dict] = deque(maxlen=20)
        self.long_term: list[dict] = []
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.long_term = data.get("long_term", [])
            except Exception:
                pass

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump({"long_term": self.long_term[-200:]}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def remember(self, text: str, importance: float = 0.5, tags: list = None, task_id: str = ""):
        entry = {
            "text": text, "importance": importance,
            "tags": tags or [], "task_id": task_id,
            "time": time.time(),
        }
        self.short_term.append(entry)
        if importance >= 0.6:
            self.long_term.append(entry)
            self._save()

    def recall_recent(self, n: int = 5) -> list[str]:
        return [m["text"] for m in list(self.short_term)[-n:]]

    def recall_important(self, n: int = 3) -> list[str]:
        sorted_mem = sorted(self.long_term, key=lambda x: x.get("importance", 0), reverse=True)
        return [m["text"] for m in sorted_mem[:n]]

    def get_context_window(self, max_chars: int = 1500) -> str:
        parts = []
        for m in list(self.short_term)[-5:]:
            parts.append(m["text"])
        text = "\n".join(parts)
        return text[:max_chars] if text else ""

    def get_stats(self) -> dict:
        return {"short_term": len(self.short_term), "long_term": len(self.long_term)}
