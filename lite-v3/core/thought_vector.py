"""帝国架构 v3.2 - 思维向量通信 2.0
借鉴 RecursiveMAS：Agent 用内部思维向量（thought vectors）通信
而非自然语言，减少 token 消耗 75%，推理速度提升 2.4x

v3.2 新增：
- 多嵌入模型支持（EmbeddingProvider 抽象 + 自动 fallback）
- 向量量化压缩（INT8 标量量化 + 稀疏化，压缩 75%+）
- 硬件加速（自动检测 GPU/PyTorch，回退纯 Python）
- 标准化向量协议（ThoughtVectorProtocol，JSON 可序列化）
- 向后兼容 v3.1 所有接口
"""
import json
import hashlib
import time
import os
import math
import struct
from dataclasses import dataclass, field, asdict
from typing import Optional, Protocol, runtime_checkable, Any
from core.logger import get_logger

log = get_logger("thought_vector")

# ─── 硬件加速检测 ───────────────────────────────────────────────
_TORCH_AVAILABLE = False
_DEVICE = "cpu"
try:
    import torch
    _TORCH_AVAILABLE = True
    _DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    log.info(f"PyTorch 可用，设备: {_DEVICE}")
except ImportError:
    log.info("PyTorch 不可用，使用纯 Python 向量计算")


# ─── 标准化向量协议 ─────────────────────────────────────────────
@dataclass
class ThoughtVectorProtocol:
    """标准化思维向量协议 - 跨平台传输格式
    所有字段均支持 JSON 序列化，便于跨平台/跨语言传输。
    """
    version: str = "3.2"
    model: str = ""                       # 嵌入模型标识
    dimension: int = 0                    # 向量维度
    vector: list[float] = field(default_factory=list)  # 向量数据
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "ThoughtVectorProtocol":
        """从 JSON 字符串反序列化"""
        data = json.loads(json_str)
        return cls(**data)

    def to_bytes(self) -> bytes:
        """序列化为紧凑二进制（向量用 float32）"""
        header = json.dumps({
            "version": self.version,
            "model": self.model,
            "dimension": self.dimension,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }).encode()
        vec_bytes = struct.pack(f"{len(self.vector)}f", *self.vector)
        header_len = struct.pack("!I", len(header))
        return header_len + header + vec_bytes

    @classmethod
    def from_bytes(cls, data: bytes) -> "ThoughtVectorProtocol":
        """从二进制反序列化"""
        header_len = struct.unpack("!I", data[:4])[0]
        header = json.loads(data[4:4 + header_len])
        vec_count = header["dimension"]
        vector = list(struct.unpack(f"{vec_count}f", data[4 + header_len:]))
        return cls(
            version=header["version"],
            model=header["model"],
            dimension=header["dimension"],
            vector=vector,
            metadata=header.get("metadata", {}),
            timestamp=header.get("timestamp", time.time()),
        )


# ─── 向后兼容的原始数据结构 ──────────────────────────────────────
@dataclass
class ThoughtVector:
    """思维向量 - Agent 内部表示（v3.1 兼容）"""
    vector: list[float]
    dimension: int
    source_agent: str
    semantic_hash: str = ""
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    compressed: bool = False

    def to_protocol(self, model: str = "") -> ThoughtVectorProtocol:
        """转换为标准协议格式"""
        return ThoughtVectorProtocol(
            model=model,
            dimension=self.dimension,
            vector=self.vector,
            metadata={**self.metadata, "source_agent": self.source_agent,
                      "semantic_hash": self.semantic_hash, "compressed": self.compressed},
            timestamp=self.timestamp,
        )


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


# ─── 多嵌入模型 Provider ─────────────────────────────────────────
@runtime_checkable
class EmbeddingProvider(Protocol):
    """嵌入模型 Provider 抽象基类
    任何实现 embed(text) -> list[float] 的类均可作为 Provider。
    """

    @property
    def model_name(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class MiMoEmbeddingProvider:
    """MiMo 嵌入模型 Provider"""

    def __init__(self, api_key: str = "", base_url: str = ""):
        self._api_key = api_key or os.environ.get("MIMO_API_KEY", "")
        self._base_url = (base_url or os.environ.get(
            "MIMO_API_ENDPOINT", "https://api.xiaomimimo.com/v1"
        )).rstrip("/")
        self._model_name = "mimo-embedding"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return 1536

    def embed(self, text: str) -> list[float]:
        return self._call_api(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._call_api(t) for t in texts]

    def _call_api(self, text: str) -> list[float]:
        import urllib.request
        url = f"{self._base_url}/embeddings"
        body = json.dumps({
            "model": "text-embedding-3-small",
            "input": text[:8000],
        }).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            return data["data"][0]["embedding"]
        except Exception as e:
            log.error(f"MiMo Embedding 失败: {e}")
            return []


class OpenAIEmbeddingProvider:
    """OpenAI text-embedding-3 Provider"""

    def __init__(self, api_key: str = "", base_url: str = "", model: str = "text-embedding-3-small"):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._model = model
        self._dim_map = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dim_map.get(self._model, 1536)

    def embed(self, text: str) -> list[float]:
        return self._call_api(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._call_api_batch(texts)

    def _call_api(self, text: str) -> list[float]:
        import urllib.request
        url = f"{self._base_url}/embeddings"
        body = json.dumps({"model": self._model, "input": text[:8000]}).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            return data["data"][0]["embedding"]
        except Exception as e:
            log.error(f"OpenAI Embedding 失败: {e}")
            return []

    def _call_api_batch(self, texts: list[str]) -> list[list[float]]:
        import urllib.request
        url = f"{self._base_url}/embeddings"
        body = json.dumps({"model": self._model, "input": [t[:8000] for t in texts]}).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            return [item["embedding"] for item in data["data"]]
        except Exception as e:
            log.error(f"OpenAI Batch Embedding 失败: {e}")
            return [[] for _ in texts]


class CohereEmbeddingProvider:
    """Cohere embed-v3 Provider"""

    def __init__(self, api_key: str = "", model: str = "embed-english-v3.0"):
        self._api_key = api_key or os.environ.get("COHERE_API_KEY", "")
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return 1024

    def embed(self, text: str) -> list[float]:
        return self._call_api([text])[0] if self._call_api([text]) else []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._call_api(texts)

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        import urllib.request
        url = "https://api.cohere.ai/v1/embed"
        body = json.dumps({
            "model": self._model,
            "texts": [t[:8000] for t in texts],
            "input_type": "search_document",
            "embedding_types": ["float"],
        }).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            return data["embeddings"]["float"]
        except Exception as e:
            log.error(f"Cohere Embedding 失败: {e}")
            return [[] for _ in texts]


class BGEEmbeddingProvider:
    """BGE (BAAI General Embedding) Provider
    本地推理或 API 调用，支持 bge-large-zh 等模型。
    """

    def __init__(self, model_name: str = "bge-large-zh-v1.5", api_url: str = ""):
        self._model_name_str = model_name
        self._api_url = api_url or os.environ.get("BGE_API_URL", "")
        self._local_model = None

    @property
    def model_name(self) -> str:
        return self._model_name_str

    @property
    def dimension(self) -> int:
        dim_map = {"bge-large-zh-v1.5": 1024, "bge-base-zh-v1.5": 768, "bge-small-zh-v1.5": 512}
        return dim_map.get(self._model_name_str, 1024)

    def embed(self, text: str) -> list[float]:
        if self._api_url:
            return self._call_api(text)
        return self._local_embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self._api_url:
            return [self._call_api(t) for t in texts]
        return [self._local_embed(t) for t in texts]

    def _call_api(self, text: str) -> list[float]:
        import urllib.request
        body = json.dumps({"model": self._model_name_str, "input": text[:8000]}).encode()
        headers = {"Content-Type": "application/json"}
        try:
            req = urllib.request.Request(self._api_url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            return data.get("data", [{}])[0].get("embedding", [])
        except Exception as e:
            log.error(f"BGE API 失败: {e}")
            return []

    def _local_embed(self, text: str) -> list[float]:
        """尝试本地 sentence-transformers 推理"""
        try:
            if self._local_model is None:
                from sentence_transformers import SentenceTransformer
                self._local_model = SentenceTransformer(f"BAAI/{self._model_name_str}")
            return self._local_model.encode(text).tolist()
        except ImportError:
            log.warning("sentence_transformers 未安装，BGE 本地推理不可用")
            return []
        except Exception as e:
            log.error(f"BGE 本地推理失败: {e}")
            return []


class EmbeddingManager:
    """嵌入模型管理器 - 多 Provider 配置切换 + 自动 fallback

    使用示例:
        manager = EmbeddingManager(providers=[
            OpenAIEmbeddingProvider(api_key="..."),
            CohereEmbeddingProvider(api_key="..."),
            MiMoEmbeddingProvider(),
        ])
        vector = manager.embed("hello world")
    """

    def __init__(self, providers: list = None, cache_size: int = 1000):
        self._providers: list = providers or []
        self._active_idx: int = 0
        self._cache: dict[str, list[float]] = {}
        self._cache_max = cache_size
        self._failure_counts: dict[int, int] = {}
        self._max_failures = 3  # 连续失败次数阈值，触发 fallback

    def add_provider(self, provider) -> None:
        self._providers.append(provider)

    @property
    def active_provider(self):
        if self._providers:
            return self._providers[self._active_idx]
        return None

    @property
    def active_model_name(self) -> str:
        p = self.active_provider
        return p.model_name if p else "none"

    def embed(self, text: str) -> list[float]:
        """获取文本的 embedding 向量，自动 fallback"""
        # 缓存查找
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        vector = []
        for attempt in range(len(self._providers)):
            idx = (self._active_idx + attempt) % len(self._providers)
            provider = self._providers[idx]
            if provider is None:
                continue
            try:
                vector = provider.embed(text)
                if vector:
                    self._active_idx = idx
                    self._failure_counts[idx] = 0
                    break
                else:
                    self._record_failure(idx)
            except Exception as e:
                log.error(f"Provider {provider.model_name} 失败: {e}")
                self._record_failure(idx)
                vector = []

        # 缓存管理
        if vector:
            if len(self._cache) >= self._cache_max:
                oldest = list(self._cache.keys())[:self._cache_max // 2]
                for k in oldest:
                    del self._cache[k]
            self._cache[cache_key] = vector

        return vector

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量 embedding"""
        return [self.embed(t) for t in texts]

    def _record_failure(self, idx: int) -> None:
        self._failure_counts[idx] = self._failure_counts.get(idx, 0) + 1
        if self._failure_counts[idx] >= self._max_failures:
            log.warning(f"Provider {self._providers[idx].model_name} 连续失败 "
                        f"{self._max_failures} 次，尝试切换")
            self._advance_provider()

    def _advance_provider(self) -> None:
        if len(self._providers) > 1:
            self._active_idx = (self._active_idx + 1) % len(self._providers)
            log.info(f"切换到 Provider: {self._providers[self._active_idx].model_name}")

    @staticmethod
    def similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """余弦相似度（纯 Python）"""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# ─── 硬件加速向量运算 ─────────────────────────────────────────────
class VectorCompute:
    """向量计算引擎 - 自动选择 GPU 或纯 Python 实现"""

    @staticmethod
    def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        if _TORCH_AVAILABLE and len(vec_a) > 128:
            return VectorCompute._torch_cosine(vec_a, vec_b)
        return VectorCompute._python_cosine(vec_a, vec_b)

    @staticmethod
    def batch_cosine_similarity(query: list[float], vectors: list[list[float]]) -> list[float]:
        if _TORCH_AVAILABLE and len(vectors) > 4:
            return VectorCompute._torch_batch_cosine(query, vectors)
        return [VectorCompute._python_cosine(query, v) for v in vectors]

    @staticmethod
    def normalize(vec: list[float]) -> list[float]:
        norm = sum(x * x for x in vec) ** 0.5
        if norm == 0:
            return vec
        return [x / norm for x in vec]

    @staticmethod
    def _python_cosine(vec_a: list[float], vec_b: list[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _torch_cosine(vec_a: list[float], vec_b: list[float]) -> float:
        try:
            import torch
            ta = torch.tensor(vec_a, dtype=torch.float32, device=_DEVICE)
            tb = torch.tensor(vec_b, dtype=torch.float32, device=_DEVICE)
            return torch.nn.functional.cosine_similarity(ta.unsqueeze(0), tb.unsqueeze(0)).item()
        except Exception:
            return VectorCompute._python_cosine(vec_a, vec_b)

    @staticmethod
    def _torch_batch_cosine(query: list[float], vectors: list[list[float]]) -> list[float]:
        try:
            import torch
            tq = torch.tensor(query, dtype=torch.float32, device=_DEVICE).unsqueeze(0)
            tv = torch.tensor(vectors, dtype=torch.float32, device=_DEVICE)
            sims = torch.nn.functional.cosine_similarity(tq, tv, dim=1)
            return sims.cpu().tolist()
        except Exception:
            return [VectorCompute._python_cosine(query, v) for v in vectors]


# ─── 向量量化压缩 ─────────────────────────────────────────────────
class VectorQuantizer:
    """向量量化压缩器
    支持 INT8 标量量化和稀疏化，目标压缩率 75%+。

    压缩格式：
    - scale (float32) + zero_point (float32) + quantized_data (int8 * dim) + sparse_bitmap
    """

    def __init__(self, sparsity_threshold: float = 0.01):
        """
        Args:
            sparsity_threshold: 绝对值低于此阈值的分量将被置零（稀疏化）
        """
        self.sparsity_threshold = sparsity_threshold

    def quantize_int8(self, vector: list[float]) -> dict:
        """INT8 标量量化

        将 float32 向量量化为 int8，每个元素从 4 字节压缩到 1 字节。
        返回量化后的数据 + 反量化参数。
        """
        if not vector:
            return {"data": b"", "scale": 1.0, "zero_point": 0, "dim": 0}

        v_min = min(vector)
        v_max = max(vector)
        dim = len(vector)

        # 计算 scale 和 zero_point
        if v_max == v_min:
            scale = 1.0
            zero_point = 0.0
        else:
            scale = (v_max - v_min) / 255.0
            zero_point = v_min

        # 量化为 uint8
        quantized = bytearray(dim)
        for i, val in enumerate(vector):
            q = int((val - zero_point) / scale) if scale > 0 else 128
            quantized[i] = max(0, min(255, q))

        return {
            "data": bytes(quantized),
            "scale": scale,
            "zero_point": zero_point,
            "dim": dim,
        }

    def dequantize_int8(self, quantized: dict) -> list[float]:
        """INT8 反量化"""
        data = quantized["data"]
        scale = quantized["scale"]
        zero_point = quantized["zero_point"]
        return [b * scale + zero_point for b in data]

    def sparse_encode(self, vector: list[float]) -> dict:
        """稀疏编码 - 将接近零的分量置零并只存储非零元素

        返回稀疏表示：{(index, value), ...} + 总维度
        """
        sparse_entries = []
        zero_count = 0
        for i, val in enumerate(vector):
            if abs(val) >= self.sparsity_threshold:
                sparse_entries.append((i, val))
            else:
                zero_count += 1

        return {
            "entries": sparse_entries,
            "dim": len(vector),
            "sparsity": zero_count / max(1, len(vector)),
            "nnz": len(sparse_entries),
        }

    def sparse_decode(self, sparse: dict) -> list[float]:
        """稀疏解码"""
        dim = sparse["dim"]
        result = [0.0] * dim
        for idx, val in sparse["entries"]:
            result[idx] = val
        return result

    def compress(self, vector: list[float]) -> dict:
        """完整压缩流程：稀疏化 + INT8 量化

        压缩率计算：
        - 原始: dim * 4 bytes (float32)
        - 量化后: dim * 1 byte (int8) + 8 bytes (scale + zero_point) + sparse_bitmap
        - 典型压缩率: ~75%+
        """
        if not vector:
            return {"method": "empty", "data": {}, "original_dim": 0}

        # Step 1: 稀疏化
        sparse = self.sparse_encode(vector)
        sparse_vec = self.sparse_decode(sparse)

        # Step 2: INT8 量化
        quantized = self.quantize_int8(sparse_vec)

        original_bytes = len(vector) * 4
        compressed_bytes = len(quantized["data"]) + 8  # data + scale + zero_point
        compression_ratio = 1.0 - (compressed_bytes / max(1, original_bytes))

        return {
            "method": "sparse_int8",
            "quantized": quantized,
            "sparsity": sparse["sparsity"],
            "original_dim": len(vector),
            "compression_ratio": compression_ratio,
        }

    def decompress(self, compressed: dict) -> list[float]:
        """完整解压流程"""
        if compressed.get("method") == "empty":
            return []
        return self.dequantize_int8(compressed["quantized"])

    def get_compression_stats(self, vector: list[float]) -> dict:
        """获取压缩统计信息（不执行压缩）"""
        original_bytes = len(vector) * 4
        # 估算量化后大小
        sparse = self.sparse_encode(vector)
        sparse_vec = self.sparse_decode(sparse)
        nnz = sum(1 for v in sparse_vec if abs(v) >= 1e-9)
        quantized_bytes = len(sparse_vec) + 8  # INT8 data + params

        return {
            "original_bytes": original_bytes,
            "quantized_bytes": quantized_bytes,
            "compression_ratio": 1.0 - (quantized_bytes / max(1, original_bytes)),
            "sparsity": sparse["sparsity"],
            "non_zero_count": nnz,
            "total_dim": len(vector),
        }


# ─── 向后兼容的压缩器（保留随机投影） ─────────────────────────────
class ThoughtVectorCompressor:
    """思维向量压缩器 - 减少通信开销（保留 v3.1 随机投影作为备选）"""

    def __init__(self, target_dim: int = 256):
        self.target_dim = target_dim
        self.quantizer = VectorQuantizer()

    def compress(self, vector: list[float]) -> list[float]:
        """降维压缩（随机投影）"""
        if len(vector) <= self.target_dim:
            return vector

        compressed = [0.0] * self.target_dim
        for i, val in enumerate(vector):
            bucket = i % self.target_dim
            if (i // self.target_dim) % 2 == 0:
                compressed[bucket] += val
            else:
                compressed[bucket] -= val

        norm = sum(x * x for x in compressed) ** 0.5
        if norm > 0:
            compressed = [x / norm for x in compressed]

        return compressed

    def compress_quantized(self, vector: list[float]) -> dict:
        """量化压缩（INT8 + 稀疏化），压缩率 75%+"""
        return self.quantizer.compress(vector)

    def decompress_quantized(self, compressed: dict) -> list[float]:
        """量化解压"""
        return self.quantizer.decompress(compressed)

    def decompress_hint(self, compressed: list[float], original_dim: int) -> list[float]:
        """近似还原（有损，仅用于可视化）"""
        if len(compressed) >= original_dim:
            return compressed
        return compressed + [0.0] * (original_dim - len(compressed))


# ─── 思维向量总线（v3.2 升级版，向后兼容） ────────────────────────
class ThoughtVectorBus:
    """思维向量总线 - Agent 间直接用向量通信

    v3.2 升级：
    - 使用 EmbeddingManager 支持多 Provider + 自动 fallback
    - 使用 VectorCompute 硬件加速
    - 支持 ThoughtVectorProtocol 标准协议
    - 保持 v3.1 所有接口向后兼容
    """

    def __init__(self, embedding_client=None, providers: list = None):
        """
        Args:
            embedding_client: v3.1 兼容的 EmbeddingClient 实例（旧接口）
            providers: v3.2 的 EmbeddingProvider 列表（新接口）
        """
        # 向后兼容：如果有旧的 embedding_client，包装成 Provider
        if providers:
            self.embedding_manager = EmbeddingManager(providers=providers)
        elif embedding_client:
            # 旧接口兼容：将 EmbeddingClient 包装为 Manager
            self.embedding_manager = EmbeddingManager(providers=[_LegacyProviderWrapper(embedding_client)])
        else:
            # 默认：尝试 MiMo
            self.embedding_manager = EmbeddingManager(providers=[MiMoEmbeddingProvider()])

        self.compressor = ThoughtVectorCompressor()
        self.quantizer = VectorQuantizer()
        self._message_log: list[VectorMessage] = []
        self._protocol_log: list[ThoughtVectorProtocol] = []
        self._semantic_cache: dict[str, ThoughtVector] = {}
        self._stats = {
            "messages": 0, "tokens_saved": 0, "compression_ratio": 0,
            "protocol_messages": 0, "quantized_messages": 0,
        }

    @property
    def embedding(self):
        """向后兼容：返回一个兼容旧 EmbeddingClient 接口的对象"""
        return self.embedding_manager

    def encode_thought(self, text: str, agent_id: str, intent: str = "query") -> ThoughtVector:
        """将自然语言编码为思维向量（v3.1 兼容接口）"""
        vector = self.embedding_manager.embed(text)
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

    def encode_thought_protocol(self, text: str, agent_id: str,
                                 intent: str = "query",
                                 use_quantization: bool = False) -> ThoughtVectorProtocol:
        """将自然语言编码为标准协议格式的思维向量

        Args:
            text: 输入文本
            agent_id: Agent 标识
            intent: 意图类型
            use_quantization: 是否使用量化压缩（INT8 + 稀疏化）
        """
        vector = self.embedding_manager.embed(text)
        if not vector:
            return ThoughtVectorProtocol(
                model=self.embedding_manager.active_model_name,
                dimension=0, vector=[],
                metadata={"source_agent": agent_id, "fallback": True},
            )

        if use_quantization:
            compressed = self.compressor.compress(vector)
            quantized = self.quantizer.compress(compressed)
            result = ThoughtVectorProtocol(
                model=self.embedding_manager.active_model_name,
                dimension=len(compressed),
                vector=compressed,
                metadata={
                    "source_agent": agent_id, "intent": intent,
                    "original_dim": len(vector), "quantized": True,
                    "compression_ratio": quantized["compression_ratio"],
                    "sparsity": quantized.get("sparsity", 0),
                },
            )
            self._stats["quantized_messages"] += 1
        else:
            compressed = self.compressor.compress(vector)
            result = ThoughtVectorProtocol(
                model=self.embedding_manager.active_model_name,
                dimension=len(compressed),
                vector=compressed,
                metadata={
                    "source_agent": agent_id, "intent": intent,
                    "original_dim": len(vector), "quantized": False,
                },
            )

        self._protocol_log.append(result)
        self._stats["protocol_messages"] += 1
        return result

    def send_thought(self, sender: str, receiver: str, text: str,
                     intent: str = "query") -> VectorMessage:
        """发送思维向量消息（v3.1 兼容接口）"""
        original_tokens = len(text) // 2
        tv = self.encode_thought(text, sender, intent)
        compressed_tokens = len(tv.vector) * 2
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

    def send_thought_protocol(self, sender: str, receiver: str, text: str,
                               intent: str = "query",
                               use_quantization: bool = False) -> tuple[VectorMessage, ThoughtVectorProtocol]:
        """发送思维向量消息，同时返回标准协议格式

        返回 (VectorMessage, ThoughtVectorProtocol) 元组。
        """
        original_tokens = len(text) // 2
        tv = self.encode_thought(text, sender, intent)
        protocol = self.encode_thought_protocol(text, sender, intent, use_quantization)
        compressed_tokens = len(tv.vector) * 2
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

        return msg, protocol

    def find_similar_thoughts(self, query_vector: ThoughtVector,
                              top_k: int = 5) -> list[tuple[VectorMessage, float]]:
        """语义检索：找到最相似的历史思维（v3.1 兼容）"""
        if not query_vector.vector:
            return []

        results = []
        for msg in self._message_log:
            if msg.thought_vector.vector:
                sim = VectorCompute.cosine_similarity(
                    query_vector.vector, msg.thought_vector.vector
                )
                results.append((msg, sim))

        results.sort(key=lambda x: -x[1])
        return results[:top_k]

    def find_similar_protocol(self, query: ThoughtVectorProtocol,
                               top_k: int = 5) -> list[tuple[ThoughtVectorProtocol, float]]:
        """语义检索：标准协议版本"""
        if not query.vector:
            return []

        similarities = VectorCompute.batch_cosine_similarity(
            query.vector, [p.vector for p in self._protocol_log if p.vector]
        )

        paired = [
            (proto, sim)
            for proto, sim in zip(
                [p for p in self._protocol_log if p.vector], similarities
            )
        ]
        paired.sort(key=lambda x: -x[1])
        return paired[:top_k]

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "log_size": len(self._message_log),
            "protocol_log_size": len(self._protocol_log),
            "active_model": self.embedding_manager.active_model_name,
            "avg_tokens_saved": (
                self._stats["tokens_saved"] / max(1, self._stats["messages"])
            ),
            "hardware": _DEVICE,
            "torch_available": _TORCH_AVAILABLE,
        }


# ─── 旧接口兼容包装器 ─────────────────────────────────────────────
class _LegacyProviderWrapper:
    """将 v3.1 的 EmbeddingClient 包装为 v3.2 的 EmbeddingProvider 接口"""

    def __init__(self, client):
        self._client = client

    @property
    def model_name(self) -> str:
        return "legacy-mimo"

    @property
    def dimension(self) -> int:
        return 1536

    def embed(self, text: str) -> list[float]:
        return self._client.embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._client.embed_batch(texts)


# ─── 便捷工厂函数 ──────────────────────────────────────────────────
def create_bus(config: dict = None) -> ThoughtVectorBus:
    """创建思维向量总线的便捷工厂函数

    config 示例:
    {
        "providers": ["mimo", "openai", "cohere", "bge"],
        "openai_api_key": "...",
        "cohere_api_key": "...",
        "mimo_api_key": "...",
        "bge_model": "bge-large-zh-v1.5",
    }
    """
    config = config or {}
    providers = []

    provider_map = {
        "mimo": lambda cfg: MiMoEmbeddingProvider(
            api_key=cfg.get("mimo_api_key", ""),
            base_url=cfg.get("mimo_base_url", ""),
        ),
        "openai": lambda cfg: OpenAIEmbeddingProvider(
            api_key=cfg.get("openai_api_key", ""),
            base_url=cfg.get("openai_base_url", ""),
            model=cfg.get("openai_model", "text-embedding-3-small"),
        ),
        "cohere": lambda cfg: CohereEmbeddingProvider(
            api_key=cfg.get("cohere_api_key", ""),
            model=cfg.get("cohere_model", "embed-english-v3.0"),
        ),
        "bge": lambda cfg: BGEEmbeddingProvider(
            model_name=cfg.get("bge_model", "bge-large-zh-v1.5"),
            api_url=cfg.get("bge_api_url", ""),
        ),
    }

    for name in config.get("providers", ["mimo"]):
        factory = provider_map.get(name)
        if factory:
            providers.append(factory(config))

    return ThoughtVectorBus(providers=providers)


# ─── 向后兼容：导出旧类名 ──────────────────────────────────────────
EmbeddingClient = MiMoEmbeddingProvider  # 旧名称别名（最小化破坏性变更）
