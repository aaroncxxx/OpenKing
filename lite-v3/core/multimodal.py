"""帝国架构 v3.1 - 多模态能力增强
突破文本边界：图像/音频/视频处理
多模态 Agent 集群 + 跨模态语义对齐
"""
import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Optional
from core.logger import get_logger

log = get_logger("multimodal")


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


class MiMoOmniClient:
    """MiMo Omni 多模态 API 客户端"""

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or os.environ.get("MIMO_API_KEY", "")
        self.base_url = (base_url or os.environ.get(
            "MIMO_API_ENDPOINT", "https://api.xiaomimimo.com/v1"
        )).rstrip("/")

    def analyze_image(self, image_path: str, prompt: str = "描述这张图片") -> str:
        """图像分析"""
        import base64
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        ext = os.path.splitext(image_path)[1].lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".gif": "image/gif", ".webp": "image/webp"}.get(ext, "image/jpeg")

        url = f"{self.base_url}/chat/completions"
        body = json.dumps({
            "model": "mimo-v2.5-omni",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_data}"}},
                ],
            }],
            "max_tokens": 2048,
        }).encode()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())

        return data["choices"][0]["message"]["content"]

    def transcribe_audio(self, audio_path: str) -> str:
        """音频转录"""
        import base64
        with open(audio_path, "rb") as f:
            audio_data = base64.b64encode(f.read()).decode()

        ext = os.path.splitext(audio_path)[1].lower()
        mime = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
                ".flac": "audio/flac"}.get(ext, "audio/mpeg")

        url = f"{self.base_url}/chat/completions"
        body = json.dumps({
            "model": "mimo-v2.5-omni",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "转录这段音频的内容"},
                    {"type": "audio_url", "audio_url": {"url": f"data:{mime};base64,{audio_data}"}},
                ],
            }],
            "max_tokens": 4096,
        }).encode()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())

        return data["choices"][0]["message"]["content"]

    def generate_text(self, prompt: str, system: str = "") -> str:
        """文本生成（通用 LLM）"""
        url = f"{self.base_url}/chat/completions"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = json.dumps({
            "model": "mimo-v2.5-pro",
            "messages": messages,
            "max_tokens": 4096,
        }).encode()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())

        return data["choices"][0]["message"]["content"]


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
            # 转录后再用指令处理
            analysis = self.omni.generate_text(f"{instruction}\n\n音频转录内容：\n{result}")
            return MultimodalOutput(modality="text", content=analysis, description="音频分析结果")
        return MultimodalOutput(modality="text", content=result, description="音频转录结果")


# ──────────────── 多模态 Agent 专业集群 ────────────────

MULTIMODAL_AGENTS = {
    "painter": {
        "id": "painter", "name": "画师", "role": "执行·图像",
        "tags": ["执行", "图像", "多模态"],
        "system_prompt": "你是帝国画师营的画师，擅长图像分析、图表生成、视觉设计。"
                        "能够理解图片内容、生成数据可视化图表、设计 UI 原型。",
        "capabilities": ["image_analysis", "chart_generation", "ui_design"],
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
}


def get_multimodal_agents() -> dict:
    """获取多模态 Agent 定义"""
    return MULTIMODAL_AGENTS.copy()
