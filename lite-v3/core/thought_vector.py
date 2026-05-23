"""帝国架构 v3.1 - 思维向量通信机制
借鉴 RecursiveMAS：Agent 用内部思维向量（thought vectors）通信
而非自然语言，减少 token 消耗 75%，推理速度提升 2.4x
"""
import json
import hashlib
import time
import os
from dataclasses import dataclass, field
from typing import Optional
from core.logger import get_logger

log = get_logger("thought_vector")


@dataclass
class ThoughtVector:
    """思维向量 - Agent 内部表示"""
    vector: list[float]
    dimension: int
    source_agent: str
    semantic_hash: str = ""
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    compressed: bool = False


@dataclass
class VectorMessage:
    """向量化消息（替代自然语言消息）"""
    msg_id: str
    sender: str
    receiver: str
    thought_vector: ThoughtVector
    intent_type: str = "query"  # query/command/result/event
    confidence: float = 1.0
    token_saved: int = 0  # 节省的 token 数


class EmbeddingClient:
    """MiMo Embedding 接口客户端"""

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or os.environ.get("MIMO_API_KEY", "")
        self.base_url = (base_url or os.environ.get("MIMO_API_ENDPOINT", "https://api.xiaomimimo.com/v1")).rstrip("/")
        self._cache: dict[str, list[float]] = {}
        self._cache_max = 1000

    def embed(self, text: str) -> list[float]:
        """获取文本的 embedding 向量"""
        # 缓存
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        import urllib.request
        url = f"{self.base_url}/embeddings"
        body = json.dumps({
            "model": "text-embedding-3-small",
            "input": text[:8000],  # 截断保护
        }).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            vector = data["data"][0]["embedding"]

            # 缓存管理
            if len(self._cache) >= self._cache_max:
                oldest = list(self._cache.keys())[:self._cache_max // 2]
                for k in oldest:
                    del self._cache[k]
            self._cache[cache_key] = vector

            return vector
        except Exception as e:
            log.error(f"Embedding 失败: {e}")
            return []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量 embedding"""
        results = []
        for text in texts:
            results.append(self.embed(text))
        return results

    def similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        """余弦相似度"""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class ThoughtVectorCompressor:
    """思维向量压缩器 - 减少通信开销"""

    def __init__(self, target_dim: int = 256):
        self.target_dim = target_dim

    def compress(self, vector: list[float]) -> list[float]:
        """降维压缩（随机投影）"""
        if len(vector) <= self.target_dim:
            return vector

        # 使用确定性哈希作为投影矩阵（避免存储随机矩阵）
        compressed = [0.0] * self.target_dim
        for i, val in enumerate(vector):
            bucket = i % self.target_dim
            # 交替加减实现近似正交投影
            if (i // self.target_dim) % 2 == 0:
                compressed[bucket] += val
            else:
                compressed[bucket] -= val

        # 归一化
        norm = sum(x * x for x in compressed) ** 0.5
        if norm > 0:
            compressed = [x / norm for x in compressed]

        return compressed

    def decompress_hint(self, compressed: list[float], original_dim: int) -> list[float]:
        """近似还原（有损，仅用于可视化）"""
        if len(compressed) >= original_dim:
            return compressed
        # 零填充
        return compressed + [0.0] * (original_dim - len(compressed))


class ThoughtVectorBus:
    """思维向量总线 - Agent 间直接用向量通信"""

    def __init__(self, embedding_client: EmbeddingClient = None):
        self.embedding = embedding_client or EmbeddingClient()
        self.compressor = ThoughtVectorCompressor()
        self._message_log: list[VectorMessage] = []
        self._semantic_cache: dict[str, ThoughtVector] = {}
        self._stats = {"messages": 0, "tokens_saved": 0, "compression_ratio": 0}

    def encode_thought(self, text: str, agent_id: str, intent: str = "query") -> ThoughtVector:
        """将自然语言编码为思维向量"""
        vector = self.embedding.embed(text)
        if not vector:
            return ThoughtVector(
                vector=[], dimension=0, source_agent=agent_id,
                semantic_hash="", metadata={"fallback": True},
            )

        compressed = self.compressor.compress(vector)
        semantic_hash = hashlib.md5(str(compressed[:16]).encode()).hexdigest()[:12]

        return ThoughtVector(
            vector=compressed,
            dimension=len(compressed),
            source_agent=agent_id,
            semantic_hash=semantic_hash,
            metadata={"original_dim": len(vector), "intent": intent},
            compressed=True,
        )

    def send_thought(self, sender: str, receiver: str, text: str,
                     intent: str = "query") -> VectorMessage:
        """发送思维向量消息"""
        original_tokens = len(text) // 2  # 粗估 token 数

        tv = self.encode_thought(text, sender, intent)

        # 压缩后的 token 消耗（向量用 float 表示，远少于自然语言）
        compressed_tokens = len(tv.vector) * 2  # 每个 float 约 2 token
        tokens_saved = max(0, original_tokens - compressed_tokens)

        msg = VectorMessage(
            msg_id=f"tv_{int(time.time()*1000)}",
            sender=sender, receiver=receiver,
            thought_vector=tv,
            intent_type=intent,
            token_saved=tokens_saved,
        )

        self._message_log.append(msg)
        self._stats["messages"] += 1
        self._stats["tokens_saved"] += tokens_saved

        log.debug(f"向量通信: {sender}→{receiver} [{intent}] "
                  f"dim={tv.dimension} saved={tokens_saved} tokens")

        return msg

    def find_similar_thoughts(self, query_vector: ThoughtVector,
                              top_k: int = 5) -> list[tuple[VectorMessage, float]]:
        """语义检索：找到最相似的历史思维"""
        if not query_vector.vector:
            return []

        results = []
        for msg in self._message_log:
            if msg.thought_vector.vector:
                sim = self.embedding.similarity(query_vector.vector, msg.thought_vector.vector)
                results.append((msg, sim))

        results.sort(key=lambda x: -x[1])
        return results[:top_k]

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "log_size": len(self._message_log),
            "avg_tokens_saved": (
                self._stats["tokens_saved"] / max(1, self._stats["messages"])
            ),
        }
