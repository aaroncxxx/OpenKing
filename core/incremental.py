"""帝国架构 v3.1 - 增量更新机制
只传递变化的信息而非完整结果，减少通信开销
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional
from core.logger import get_logger

log = get_logger("incremental")


@dataclass
class Delta:
    """增量差异"""
    delta_id: str
    base_hash: str
    target_hash: str
    operations: list[dict]  # [{op: "add"|"remove"|"replace", path: "...", value: ...}]
    timestamp: float = field(default_factory=time.time)
    bytes_saved: int = 0


class IncrementalUpdater:
    """增量更新器 - 只传递变化部分"""

    def __init__(self):
        self._snapshot_cache: dict[str, str] = {}  # agent_id → last snapshot hash
        self._delta_log: list[Delta] = []
        self._stats = {"deltas": 0, "bytes_saved": 0, "full_updates": 0}

    def compute_delta(self, agent_id: str, old_data: dict, new_data: dict) -> Delta:
        """计算两个数据之间的差异"""
        old_json = json.dumps(old_data, sort_keys=True, ensure_ascii=False)
        new_json = json.dumps(new_data, sort_keys=True, ensure_ascii=False)

        old_hash = hashlib.md5(old_json.encode()).hexdigest()[:12]
        new_hash = hashlib.md5(new_json.encode()).hexdigest()[:12]

        if old_hash == new_hash:
            return Delta(
                delta_id=f"delta_{int(time.time()*1000)}",
                base_hash=old_hash, target_hash=new_hash,
                operations=[], bytes_saved=0,
            )

        # 递归 diff
        operations = self._diff_objects(old_data, new_data, "")

        # 计算节省的字节数
        delta_size = len(json.dumps(operations, ensure_ascii=False))
        full_size = len(new_json)
        bytes_saved = max(0, full_size - delta_size)

        delta = Delta(
            delta_id=f"delta_{int(time.time()*1000)}",
            base_hash=old_hash, target_hash=new_hash,
            operations=operations,
            bytes_saved=bytes_saved,
        )

        self._delta_log.append(delta)
        self._stats["deltas"] += 1
        self._stats["bytes_saved"] += bytes_saved

        self._snapshot_cache[agent_id] = new_hash
        return delta

    def _diff_objects(self, old, new, path: str) -> list[dict]:
        """递归计算差异"""
        ops = []

        if isinstance(old, dict) and isinstance(new, dict):
            # 新增和修改
            for key, value in new.items():
                full_path = f"{path}.{key}" if path else key
                if key not in old:
                    ops.append({"op": "add", "path": full_path, "value": value})
                elif old[key] != value:
                    if isinstance(old[key], (dict, list)) and isinstance(value, (dict, list)):
                        ops.extend(self._diff_objects(old[key], value, full_path))
                    else:
                        ops.append({"op": "replace", "path": full_path, "value": value})
            # 删除
            for key in old:
                if key not in new:
                    full_path = f"{path}.{key}" if path else key
                    ops.append({"op": "remove", "path": full_path})

        elif isinstance(old, list) and isinstance(new, list):
            # 列表 diff（简单实现：全量替换或按索引 diff）
            max_len = max(len(old), len(new))
            for i in range(max_len):
                full_path = f"{path}[{i}]"
                if i >= len(old):
                    ops.append({"op": "add", "path": full_path, "value": new[i]})
                elif i >= len(new):
                    ops.append({"op": "remove", "path": full_path})
                elif old[i] != new[i]:
                    if isinstance(old[i], (dict, list)) and isinstance(new[i], (dict, list)):
                        ops.extend(self._diff_objects(old[i], new[i], full_path))
                    else:
                        ops.append({"op": "replace", "path": full_path, "value": new[i]})
        else:
            if old != new:
                ops.append({"op": "replace", "path": path, "value": new})

        return ops

    def apply_delta(self, base_data: dict, delta: Delta) -> dict:
        """应用增量更新"""
        import copy
        result = copy.deepcopy(base_data)

        for op in delta.operations:
            path = op["path"]
            parts = self._parse_path(path)

            if op["op"] == "add":
                self._set_nested(result, parts, op["value"])
            elif op["op"] == "replace":
                self._set_nested(result, parts, op["value"])
            elif op["op"] == "remove":
                self._remove_nested(result, parts)

        return result

    def _parse_path(self, path: str) -> list:
        """解析 JSON path"""
        parts = []
        for part in path.split("."):
            if "[" in part:
                key, idx = part.split("[")
                idx = int(idx.rstrip("]"))
                parts.append(key)
                parts.append(idx)
            else:
                parts.append(part)
        return parts

    def _set_nested(self, data, parts, value):
        current = data
        for part in parts[:-1]:
            if isinstance(part, int):
                current = current[part]
            else:
                current = current[part]
        last = parts[-1]
        if isinstance(last, int):
            while len(current) <= last:
                current.append(None)
            current[last] = value
        else:
            current[last] = value

    def _remove_nested(self, data, parts):
        current = data
        for part in parts[:-1]:
            if isinstance(part, int):
                current = current[part]
            else:
                current = current[part]
        last = parts[-1]
        if isinstance(last, int) and isinstance(current, list):
            if last < len(current):
                current.pop(last)
        elif isinstance(last, str) and isinstance(current, dict):
            current.pop(last, None)

    def should_use_delta(self, agent_id: str, new_data: dict) -> bool:
        """判断是否应该使用增量更新"""
        if agent_id not in self._snapshot_cache:
            return False  # 首次更新，用全量

        new_json = json.dumps(new_data, sort_keys=True, ensure_ascii=False)
        # 如果数据量小（< 500 bytes），直接全量
        if len(new_json) < 500:
            return False

        return True

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "cache_size": len(self._snapshot_cache),
            "avg_bytes_saved": (
                self._stats["bytes_saved"] / max(1, self._stats["deltas"])
            ),
        }
