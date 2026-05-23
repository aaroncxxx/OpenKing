"""帝国架构 v3.2 - 多模态能力深化
突破文本边界：图像/音频/视频处理 + 实时流 + 生成式多模态 + 跨模态 RAG
多模态 Agent 集群 + 跨模态语义对齐 + 向量检索
"""
import asyncio
import base64
import hashlib
import json
import math
import os
import struct
import tempfile
import urllib.request
from dataclasses import dataclass, field
from typing import AsyncGenerator, Callable, Optional

from core.logger import get_logger

log = get_logger("multimodal")


# ──────────────── 数据结构 ────────────────

@dataclass
class MultimodalInput:
    """多模态输入"""
    modality: str       # text, image, audio, video
    content: str        # 文本内容或文件路径
    mime_type: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class MultimodalOutput:
    """多模态输出"""
    modality: str
    content: str        # 文本内容或文件路径
    description: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class VideoFrame:
    """视频帧数据"""
    index: int
    timestamp: float        # 秒
    image_path: str
    description: str = ""
    is_keyframe: bool = False


@dataclass
class StreamChunk:
    """流式处理块"""
    chunk_id: int
    data: bytes
    timestamp: float
    is_final: bool = False
    transcription: str = ""
    translation: str = ""


@dataclass
class EmbeddingVector:
    """向量嵌入"""
    id: str
    vector: list[float]
    modality: str           # text / image
    content_ref: str        # 原始内容或文件路径
    metadata: dict = field(default_factory=dict)


# ──────────────── MiMo Omni 客户端（向后兼容）────────────────

class MiMoOmniClient:
    """MiMo Omni 多模态 API 客户端"""

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or os.environ.get("MIMO_API_KEY", "")
        self.base_url = (base_url or os.environ.get(
            "MIMO_API_ENDPOINT", "https://api.xiaomimimo.com/v1"
        )).rstrip("/")

    def _request(self, body: dict, timeout: int = 60) -> dict:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    def analyze_image(self, image_path: str, prompt: str = "描述这张图片") -> str:
        """图像分析"""
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        ext = os.path.splitext(image_path)[1].lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".gif": "image/gif", ".webp": "image/webp"}.get(ext, "image/jpeg")

        data = self._request({
            "model": "mimo-v2.5-omni",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_data}"}},
                ],
            }],
            "max_tokens": 2048,
        })
        return data["choices"][0]["message"]["content"]

    def transcribe_audio(self, audio_path: str) -> str:
        """音频转录"""
        with open(audio_path, "rb") as f:
            audio_data = base64.b64encode(f.read()).decode()

        ext = os.path.splitext(audio_path)[1].lower()
        mime = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
                ".flac": "audio/flac"}.get(ext, "audio/mpeg")

        data = self._request({
            "model": "mimo-v2.5-omni",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "转录这段音频的内容"},
                    {"type": "audio_url", "audio_url": {"url": f"data:{mime};base64,{audio_data}"}},
                ],
            }],
            "max_tokens": 4096,
        }, timeout=120)
        return data["choices"][0]["message"]["content"]

    def generate_text(self, prompt: str, system: str = "") -> str:
        """文本生成（通用 LLM）"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        data = self._request({
            "model": "mimo-v2.5-pro",
            "messages": messages,
            "max_tokens": 4096,
        })
        return data["choices"][0]["message"]["content"]

    def get_embedding(self, text: str) -> list[float]:
        """获取文本嵌入向量"""
        data = self._request({
            "model": "mimo-embedding",
            "input": text,
        })
        return data["data"][0]["embedding"]

    def get_image_embedding(self, image_path: str) -> list[float]:
        """获取图像嵌入向量"""
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()
        ext = os.path.splitext(image_path)[1].lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".gif": "image/gif", ".webp": "image/webp"}.get(ext, "image/jpeg")
        data = self._request({
            "model": "mimo-embedding",
            "input": [{"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_data}"}}],
        })
        return data["data"][0]["embedding"]


# ──────────────── 多模态路由器（向后兼容）────────────────

class MultimodalRouter:
    """多模态路由器 - 根据输入类型自动选择处理方式"""

    def __init__(self, omni_client: MiMoOmniClient = None):
        self.omni = omni_client or MiMoOmniClient()

    def process(self, inputs: list[MultimodalInput],
                instruction: str = "") -> list[MultimodalOutput]:
        """处理多模态输入"""
        outputs = []
        for inp in inputs:
            if inp.modality == "text":
                result = self._process_text(inp, instruction)
            elif inp.modality == "image":
                result = self._process_image(inp, instruction)
            elif inp.modality == "audio":
                result = self._process_audio(inp, instruction)
            elif inp.modality == "video":
                result = self._process_video(inp, instruction)
            else:
                result = MultimodalOutput(
                    modality="text",
                    content=f"[不支持的模态: {inp.modality}]",
                )
            outputs.append(result)
        return outputs

    def _process_text(self, inp: MultimodalInput, instruction: str) -> MultimodalOutput:
        prompt = f"{instruction}\n\n{inp.content}" if instruction else inp.content
        result = self.omni.generate_text(prompt)
        return MultimodalOutput(modality="text", content=result)

    def _process_image(self, inp: MultimodalInput, instruction: str) -> MultimodalOutput:
        prompt = instruction or "详细描述这张图片的内容，包括文字、物体、场景"
        result = self.omni.analyze_image(inp.content, prompt)
        return MultimodalOutput(modality="text", content=result, description="图像分析结果")

    def _process_audio(self, inp: MultimodalInput, instruction: str) -> MultimodalOutput:
        result = self.omni.transcribe_audio(inp.content)
        if instruction:
            analysis = self.omni.generate_text(f"{instruction}\n\n音频转录内容：\n{result}")
            return MultimodalOutput(modality="text", content=analysis, description="音频分析结果")
        return MultimodalOutput(modality="text", content=result, description="音频转录结果")

    def _process_video(self, inp: MultimodalInput, instruction: str) -> MultimodalOutput:
        """视频处理 - 使用 VideoProcessor"""
        processor = VideoProcessor(self.omni)
        summary = processor.summarize_video(inp.content, instruction)
        return MultimodalOutput(
            modality="text", content=summary, description="视频分析结果"
        )


# ──────────────── 视频处理器（v3.2 新增）────────────────

class VideoProcessor:
    """视频处理器 - 关键帧提取 + 内容理解 + 摘要生成"""

    def __init__(self, omni_client: MiMoOmniClient = None, temp_dir: str = None):
        self.omni = omni_client or MiMoOmniClient()
        self.temp_dir = temp_dir or tempfile.gettempdir()
        os.makedirs(self.temp_dir, exist_ok=True)

    def extract_keyframes(self, video_path: str, interval: float = 2.0,
                          max_frames: int = 30) -> list[VideoFrame]:
        """基于 ffmpeg 提取视频关键帧

        Args:
            video_path: 视频文件路径
            interval: 帧提取间隔（秒）
            max_frames: 最大帧数
        Returns:
            关键帧列表
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        # 获取视频时长
        duration = self._get_duration(video_path)
        if duration <= 0:
            raise ValueError(f"无法获取视频时长: {video_path}")

        # 计算提取时间点
        timestamps = []
        t = 0.0
        while t < duration and len(timestamps) < max_frames:
            timestamps.append(t)
            t += interval

        # 使用 ffmpeg 提取帧
        frames = []
        video_hash = hashlib.md5(video_path.encode()).hexdigest()[:8]
        for idx, ts in enumerate(timestamps):
            out_path = os.path.join(self.temp_dir, f"frame_{video_hash}_{idx:04d}.jpg")
            cmd = (
                f'ffmpeg -y -ss {ts:.3f} -i "{video_path}" '
                f'-frames:v 1 -q:v 2 "{out_path}" 2>/dev/null'
            )
            ret = os.system(cmd)
            if ret == 0 and os.path.exists(out_path):
                frames.append(VideoFrame(
                    index=idx,
                    timestamp=ts,
                    image_path=out_path,
                    is_keyframe=(idx == 0 or idx == len(timestamps) - 1),
                ))
        log.info(f"提取 {len(frames)}/{len(timestamps)} 帧 from {video_path}")
        return frames

    def analyze_frames(self, frames: list[VideoFrame],
                       prompt: str = "描述这一帧视频画面的内容") -> list[VideoFrame]:
        """调用 MiMo Omni 分析关键帧"""
        for frame in frames:
            if os.path.exists(frame.image_path):
                frame.description = self.omni.analyze_image(frame.image_path, prompt)
                log.debug(f"帧 {frame.index} @{frame.timestamp:.1f}s 分析完成")
        return frames

    def summarize_video(self, video_path: str, instruction: str = "",
                        interval: float = 3.0) -> str:
        """生成视频摘要

        Args:
            video_path: 视频文件路径
            instruction: 自定义指令
            interval: 帧提取间隔
        Returns:
            视频摘要文本
        """
        frames = self.extract_keyframes(video_path, interval=interval)
        if not frames:
            return "[错误: 无法提取视频帧]"

        frames = self.analyze_frames(frames)

        # 组装帧描述
        frame_descriptions = []
        for f in frames:
            if f.description:
                frame_descriptions.append(
                    f"[{f.timestamp:.1f}s] {f.description}"
                )

        if not frame_descriptions:
            return "[错误: 视频帧分析失败]"

        summary_prompt = instruction or "根据以下视频帧描述，生成一段完整的视频内容摘要"
        full_prompt = (
            f"{summary_prompt}\n\n"
            f"视频时长: {frames[-1].timestamp:.1f}秒\n"
            f"共 {len(frames)} 个关键帧:\n\n"
            + "\n\n".join(frame_descriptions)
        )
        return self.omni.generate_text(full_prompt)

    def _get_duration(self, video_path: str) -> float:
        """用 ffprobe 获取视频时长"""
        cmd = (
            f'ffprobe -v error -show_entries format=duration '
            f'-of default=noprint_wrappers=1:nokey=1 "{video_path}" 2>/dev/null'
        )
        try:
            import subprocess
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def cleanup(self, frames: list[VideoFrame]):
        """清理临时帧文件"""
        for frame in frames:
            try:
                if os.path.exists(frame.image_path):
                    os.remove(frame.image_path)
            except OSError:
                pass


# ──────────────── 实时流处理器（v3.2 新增）────────────────

class RealtimeStreamProcessor:
    """实时流处理器 - 音频流转写 + 实时翻译

    支持两种接口模式:
    1. 异步生成器 (async for chunk in process_stream(...))
    2. 回调函数 (process_stream(..., on_chunk=callback))
    """

    def __init__(self, omni_client: MiMoOmniClient = None,
                 chunk_duration: float = 3.0,
                 source_lang: str = "zh",
                 target_lang: str = "en"):
        self.omni = omni_client or MiMoOmniClient()
        self.chunk_duration = chunk_duration  # 每块音频时长（秒）
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._buffer = bytearray()
        self._chunk_id = 0
        self._sample_rate = 16000  # 默认 16kHz

    async def process_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        translate: bool = False,
        on_chunk: Optional[Callable] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """处理实时音频流

        Args:
            audio_stream: 异步音频数据生成器（PCM/WAV 格式）
            translate: 是否同时翻译
            on_chunk: 可选回调函数
        Yields:
            StreamChunk 包含转录和可选翻译
        """
        chunk_bytes = int(self.chunk_duration * self._sample_rate * 2)  # 16-bit samples

        async for audio_data in audio_stream:
            self._buffer.extend(audio_data)

            while len(self._buffer) >= chunk_bytes:
                chunk_data = bytes(self._buffer[:chunk_bytes])
                self._buffer = self._buffer[chunk_bytes:]

                chunk = await self._process_chunk(chunk_data, translate)
                if on_chunk:
                    on_chunk(chunk)
                yield chunk

        # 处理剩余数据
        if self._buffer:
            chunk = await self._process_chunk(bytes(self._buffer), translate)
            chunk.is_final = True
            if on_chunk:
                on_chunk(chunk)
            yield chunk

    async def _process_chunk(self, audio_data: bytes,
                             translate: bool) -> StreamChunk:
        """处理单个音频块"""
        self._chunk_id += 1

        # 保存临时文件
        tmp_path = os.path.join(
            tempfile.gettempdir(),
            f"stream_chunk_{self._chunk_id:06d}.wav"
        )
        try:
            self._write_wav(tmp_path, audio_data)
            transcription = self.omni.transcribe_audio(tmp_path)
        except Exception as e:
            log.error(f"转录块 {self._chunk_id} 失败: {e}")
            transcription = ""
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        translation = ""
        if translate and transcription:
            translation = self._translate(transcription)

        chunk = StreamChunk(
            chunk_id=self._chunk_id,
            data=audio_data,
            timestamp=self._chunk_id * self.chunk_duration,
            transcription=transcription,
            translation=translation,
        )
        return chunk

    def _translate(self, text: str) -> str:
        """翻译文本"""
        prompt = (
            f"将以下{self.source_lang}文本翻译为{self.target_lang}，"
            f"只输出翻译结果，不要解释:\n\n{text}"
        )
        try:
            return self.omni.generate_text(prompt)
        except Exception as e:
            log.error(f"翻译失败: {e}")
            return ""

    def _write_wav(self, path: str, pcm_data: bytes):
        """将 PCM 数据写入 WAV 文件"""
        import wave
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self._sample_rate)
            wf.writeframes(pcm_data)

    def set_sample_rate(self, rate: int):
        """设置采样率"""
        self._sample_rate = rate

    def reset(self):
        """重置处理器状态"""
        self._buffer.clear()
        self._chunk_id = 0


# ──────────────── 多模态 RAG（v3.2 新增）────────────────

class MultimodalRAG:
    """多模态 RAG - 跨模态向量检索

    支持:
    - 用文本搜索图像（图像 embedding 索引）
    - 用图像搜索文本
    - 基于向量相似度的跨模态检索
    """

    def __init__(self, omni_client: MiMoOmniClient = None):
        self.omni = omni_client or MiMoOmniClient()
        self._index: list[EmbeddingVector] = []
        self._dimension: int = 0

    def add_text(self, text: str, doc_id: str = None, **metadata) -> str:
        """添加文本文档到索引

        Args:
            text: 文本内容
            doc_id: 文档 ID（自动生成如不指定）
        Returns:
            文档 ID
        """
        doc_id = doc_id or f"text_{hashlib.md5(text.encode()).hexdigest()[:12]}"
        vector = self.omni.get_embedding(text)
        if not self._dimension:
            self._dimension = len(vector)
        self._index.append(EmbeddingVector(
            id=doc_id,
            vector=vector,
            modality="text",
            content_ref=text,
            metadata=metadata,
        ))
        log.info(f"已索引文本: {doc_id} (dim={len(vector)})")
        return doc_id

    def add_image(self, image_path: str, description: str = "",
                  doc_id: str = None, **metadata) -> str:
        """添加图像到索引

        Args:
            image_path: 图像文件路径
            description: 图像描述（可选，用于辅助检索）
            doc_id: 文档 ID
        Returns:
            文档 ID
        """
        doc_id = doc_id or f"img_{hashlib.md5(image_path.encode()).hexdigest()[:12]}"
        vector = self.omni.get_image_embedding(image_path)
        if not self._dimension:
            self._dimension = len(vector)
        meta = {"description": description, **metadata}
        self._index.append(EmbeddingVector(
            id=doc_id,
            vector=vector,
            modality="image",
            content_ref=image_path,
            metadata=meta,
        ))
        log.info(f"已索引图像: {doc_id} (dim={len(vector)})")
        return doc_id

    def search_by_text(self, query: str, top_k: int = 5,
                       modality_filter: Optional[str] = None) -> list[tuple[EmbeddingVector, float]]:
        """用文本搜索（可限制返回模态）

        Args:
            query: 查询文本
            top_k: 返回数量
            modality_filter: 可选过滤 "text" 或 "image"
        Returns:
            [(embedding, score), ...] 按相似度降序
        """
        query_vec = self.omni.get_embedding(query)
        return self._search(query_vec, top_k, modality_filter)

    def search_by_image(self, image_path: str, top_k: int = 5,
                        modality_filter: Optional[str] = None) -> list[tuple[EmbeddingVector, float]]:
        """用图像搜索

        Args:
            image_path: 查询图像路径
            top_k: 返回数量
            modality_filter: 可选过滤 "text" 或 "image"
        Returns:
            [(embedding, score), ...] 按相似度降序
        """
        query_vec = self.omni.get_image_embedding(image_path)
        return self._search(query_vec, top_k, modality_filter)

    def _search(self, query_vec: list[float], top_k: int,
                modality_filter: Optional[str]) -> list[tuple[EmbeddingVector, float]]:
        """向量相似度搜索"""
        results = []
        for entry in self._index:
            if modality_filter and entry.modality != modality_filter:
                continue
            score = self._cosine_similarity(query_vec, entry.vector)
            results.append((entry, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """计算余弦相似度"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def save_index(self, path: str):
        """保存索引到文件"""
        data = {
            "dimension": self._dimension,
            "entries": [
                {
                    "id": e.id,
                    "vector": e.vector,
                    "modality": e.modality,
                    "content_ref": e.content_ref,
                    "metadata": e.metadata,
                }
                for e in self._index
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info(f"索引已保存: {path} ({len(self._index)} 条)")

    def load_index(self, path: str):
        """从文件加载索引"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._dimension = data.get("dimension", 0)
        self._index = [
            EmbeddingVector(**entry) for entry in data.get("entries", [])
        ]
        log.info(f"索引已加载: {path} ({len(self._index)} 条)")

    @property
    def size(self) -> int:
        return len(self._index)


# ──────────────── 生成式多模态工具（v3.2 新增）────────────────

class ImageGenerator:
    """图像生成器 - 调用 DALL-E / MiMo 图像生成 API"""

    def __init__(self, api_key: str = None, base_url: str = None,
                 provider: str = "mimo"):
        self.api_key = api_key or os.environ.get("MIMO_API_KEY", "")
        self.base_url = (base_url or os.environ.get(
            "MIMO_API_ENDPOINT", "https://api.xiaomimimo.com/v1"
        )).rstrip("/")
        self.provider = provider  # "mimo" or "openai"

    def generate(self, prompt: str, size: str = "1024x1024",
                 style: str = "vivid", output_path: str = None) -> str:
        """生成图像

        Args:
            prompt: 图像描述
            size: 图像尺寸
            style: 风格
            output_path: 输出路径（不指定则自动命名）
        Returns:
            生成的图像文件路径
        """
        if self.provider == "openai":
            return self._generate_openai(prompt, size, style, output_path)
        return self._generate_mimo(prompt, size, style, output_path)

    def _generate_mimo(self, prompt: str, size: str, style: str,
                       output_path: str) -> str:
        """MiMo 图像生成"""
        url = f"{self.base_url}/images/generations"
        body = json.dumps({
            "model": "mimo-image-gen",
            "prompt": prompt,
            "size": size,
            "style": style,
            "n": 1,
        }).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())

        image_url = data["data"][0]["url"]
        if not output_path:
            output_path = os.path.join(
                tempfile.gettempdir(),
                f"gen_{hashlib.md5(prompt.encode()).hexdigest()[:8]}.png"
            )
        urllib.request.urlretrieve(image_url, output_path)
        log.info(f"图像已生成: {output_path}")
        return output_path

    def _generate_openai(self, prompt: str, size: str, style: str,
                         output_path: str) -> str:
        """OpenAI DALL-E 图像生成"""
        url = f"{self.base_url}/images/generations"
        body = json.dumps({
            "model": "dall-e-3",
            "prompt": prompt,
            "size": size,
            "style": style,
            "n": 1,
            "response_format": "url",
        }).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())

        image_url = data["data"][0]["url"]
        if not output_path:
            output_path = os.path.join(
                tempfile.gettempdir(),
                f"gen_{hashlib.md5(prompt.encode()).hexdigest()[:8]}.png"
            )
        urllib.request.urlretrieve(image_url, output_path)
        log.info(f"图像已生成 (DALL-E): {output_path}")
        return output_path


class AudioGenerator:
    """音频生成器 - TTS 文本转语音"""

    def __init__(self, omni_client: MiMoOmniClient = None):
        self.omni = omni_client or MiMoOmniClient()

    def generate_speech(self, text: str, voice: str = "default",
                        speed: float = 1.0, output_path: str = None) -> str:
        """文本转语音

        Args:
            text: 要合成的文本
            voice: 语音角色
            speed: 语速
            output_path: 输出路径
        Returns:
            音频文件路径
        """
        if not output_path:
            output_path = os.path.join(
                tempfile.gettempdir(),
                f"tts_{hashlib.md5(text.encode()).hexdigest()[:8]}.wav"
            )

        url = f"{self.omni.base_url}/audio/speech"
        body = json.dumps({
            "model": "mimo-tts",
            "input": text,
            "voice": voice,
            "speed": speed,
            "response_format": "wav",
        }).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.omni.api_key}",
        }
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(output_path, "wb") as f:
                f.write(resp.read())

        log.info(f"语音已生成: {output_path}")
        return output_path


# ──────────────── 多模态 Agent 专业集群（v3.2 扩展）────────────────

MULTIMODAL_AGENTS = {
    "painter": {
        "id": "painter", "name": "画师", "role": "执行·图像",
        "tags": ["执行", "图像", "多模态", "生成"],
        "system_prompt": (
            "你是帝国画师营的画师，擅长图像分析、图表生成、视觉设计和图像生成。"
            "能够理解图片内容、生成数据可视化图表、设计 UI 原型，"
            "也能根据文字描述创作图像（调用 DALL-E/MiMo 图像生成）。"
        ),
        "capabilities": [
            "image_analysis", "chart_generation", "ui_design",
            "image_generation",  # v3.2 新增
        ],
    },
    "musician": {
        "id": "musician", "name": "乐师", "role": "执行·音频",
        "tags": ["执行", "音频", "多模态"],
        "system_prompt": "你是帝国乐坊的乐师，擅长音频处理、语音转录、音乐分析。"
                        "能够转录语音、分析音频特征、生成语音合成指令。",
        "capabilities": ["audio_transcription", "audio_analysis", "tts"],
    },
    "translator_mm": {
        "id": "translator_mm", "name": "译官", "role": "执行·跨模态",
        "tags": ["执行", "翻译", "多模态"],
        "system_prompt": "你是帝国鸿胪寺译馆的译官，擅长跨模态语义对齐。"
                        "能够将图像描述转为文字、将文字转为图像提示词、多语言翻译。",
        "capabilities": ["cross_modal_alignment", "translation", "captioning"],
    },
    # v3.2 新增: 钦天监 - 视频分析 Agent
    "astrologer": {
        "id": "astrologer", "name": "钦天监", "role": "执行·视频",
        "tags": ["执行", "视频", "多模态", "分析"],
        "system_prompt": (
            "你是帝国钦天监的天官，擅长视频内容分析与理解。"
            "能够提取视频关键帧、分析视频内容、生成视频摘要，"
            "如同观测天象般洞察视频中的每一帧画面。"
        ),
        "capabilities": [
            "video_keyframe_extraction",
            "video_content_analysis",
            "video_summarization",
        ],
    },
    # v3.2 新增: 内容生成器 - 音频生成 Agent
    "content_generator": {
        "id": "content_generator", "name": "造物使", "role": "执行·生成",
        "tags": ["执行", "生成", "TTS", "音频", "多模态"],
        "system_prompt": (
            "你是帝国造物局的造物使，擅长音频内容生成。"
            "能够将文字转化为语音、生成不同风格的音频内容，"
            "是帝国多模态生成能力的核心执行者。"
        ),
        "capabilities": [
            "text_to_speech",
            "audio_generation",
            "voice_style_control",
        ],
    },
}


def get_multimodal_agents() -> dict:
    """获取多模态 Agent 定义（v3.2: 新增钦天监、造物使）"""
    return MULTIMODAL_AGENTS.copy()
