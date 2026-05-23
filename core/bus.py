"""帝国架构 v3.0 - 消息总线"""
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class MessageType(Enum):
    COMMAND = "command"
    RESULT = "result"
    QUERY = "query"
    RESPONSE = "response"
    EVENT = "event"
    BROADCAST = "broadcast"
    DIRECT = "direct"


@dataclass
class Message:
    msg_id: str
    sender: str
    receiver: str
    msg_type: MessageType
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


class MessageBus:
    """消息总线 v3.0 - 带 Agent 间直接通信"""

    def __init__(self, max_history: int = 2000):
        self.history: deque[Message] = deque(maxlen=max_history)
        self._subscribers: dict[str, list[Callable]] = {}
        self._queues: dict[str, deque[Message]] = {}
        self._stats = {"sent": 0, "received": 0}
        self._lock = threading.Lock()

    def register(self, agent_id: str):
        with self._lock:
            if agent_id not in self._subscribers:
                self._subscribers[agent_id] = []
                self._queues[agent_id] = deque(maxlen=100)

    def send(self, msg: Message):
        with self._lock:
            self.history.append(msg)
            self._stats["sent"] += 1
            if msg.receiver in self._queues:
                self._queues[msg.receiver].append(msg)
            for callback in self._subscribers.get(msg.receiver, []):
                try:
                    callback(msg)
                except Exception:
                    pass

    def send_direct(self, sender: str, receiver: str, content: str, msg_type: MessageType = MessageType.DIRECT):
        msg = Message(
            msg_id=f"msg_{int(time.time()*1000)}",
            sender=sender, receiver=receiver,
            msg_type=msg_type, content=content,
        )
        self.send(msg)

    def subscribe(self, agent_id: str, callback: Callable):
        with self._lock:
            self._subscribers.setdefault(agent_id, []).append(callback)

    def get_messages(self, agent_id: str, limit: int = 10) -> list[Message]:
        queue = self._queues.get(agent_id, deque())
        return list(queue)[-limit:]

    def get_history(self, limit: int = 20) -> list[Message]:
        return list(self.history)[-limit:]

    def get_stats(self) -> dict:
        return {
            "sent": self._stats["sent"],
            "received": self._stats["received"],
            "queue_depth": {aid: len(q) for aid, q in self._queues.items() if q},
        }
