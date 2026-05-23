"""帝国架构 v3.0 - Token 追踪（SQLite WAL + 线程安全）"""
import sqlite3
import os
import time
import threading
from collections import defaultdict
from core.logger import get_logger

log = get_logger("tokens")


class TokenTracker:
    """Token 追踪器 v3.0 - 多模型成本追踪"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tokens.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
        self._model_stats = defaultdict(lambda: {"calls": 0, "input": 0, "output": 0, "cost": 0.0})

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    model TEXT DEFAULT '',
                    cost REAL DEFAULT 0,
                    timestamp REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON token_usage(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent ON token_usage(agent_id)")

    def log_usage(self, agent_id: str, input_tokens: int, output_tokens: int,
                  model: str = "", cost: float = 0.0):
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO token_usage (agent_id, input_tokens, output_tokens, model, cost, timestamp) VALUES (?,?,?,?,?,?)",
                    (agent_id, input_tokens, output_tokens, model, cost, time.time()),
                )
            stats = self._model_stats[model or "unknown"]
            stats["calls"] += 1
            stats["input"] += input_tokens
            stats["output"] += output_tokens
            stats["cost"] += cost

    def check_budget(self, agent_id: str, max_daily: int = 100000) -> bool:
        return self.get_total_today() < max_daily

    def get_usage(self) -> dict:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                today_start = time.time() - (time.time() % 86400)
                rows = conn.execute(
                    "SELECT agent_id, SUM(input_tokens), SUM(output_tokens) FROM token_usage WHERE timestamp > ? GROUP BY agent_id",
                    (today_start,),
                ).fetchall()
                return {r[0]: {"input": r[1] or 0, "output": r[2] or 0} for r in rows}

    def get_total_today(self) -> int:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                today_start = time.time() - (time.time() % 86400)
                row = conn.execute(
                    "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) FROM token_usage WHERE timestamp > ?",
                    (today_start,),
                ).fetchone()
                return row[0]

    def get_model_stats(self) -> dict:
        return dict(self._model_stats)

    def get_cost_summary(self) -> dict:
        """v3.0: 获取成本摘要"""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                today_start = time.time() - (time.time() % 86400)
                rows = conn.execute(
                    "SELECT model, SUM(cost), SUM(input_tokens), SUM(output_tokens), COUNT(*) FROM token_usage WHERE timestamp > ? GROUP BY model",
                    (today_start,),
                ).fetchall()
                return {
                    r[0]: {"cost": r[1] or 0, "input": r[2] or 0, "output": r[3] or 0, "calls": r[4]}
                    for r in rows
                }
