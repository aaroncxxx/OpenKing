"""帝国架构 v3.1 - 部署架构（Docker + 轻量版 + 边缘部署）"""
import json
import os
from core.logger import get_logger

log = get_logger("deploy")


def generate_dockerfile(output_path: str = None) -> str:
    """生成 Dockerfile"""
    if output_path is None:
        output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Dockerfile")

    dockerfile = """# Empire Architecture v3.1 - Docker
FROM python:3.11-slim

WORKDIR /app

# 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY . .

# 环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 端口（Dashboard）
EXPOSE 8501

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s \\
    CMD python3 -c "from chancellor import Chancellor; c = Chancellor(); print('OK')" || exit 1

# 默认启动 CLI
CMD ["python3", "main.py"]
"""

    with open(output_path, "w") as f:
        f.write(dockerfile)
    log.info(f"Dockerfile 生成: {output_path}")
    return dockerfile


def generate_docker_compose(output_path: str = None) -> str:
    """生成 docker-compose.yml"""
    if output_path is None:
        output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docker-compose.yml")

    compose = """# Empire Architecture v3.1 - Docker Compose
version: '3.8'

services:
  # 主服务 - 帝国 CLI
  empire:
    build: .
    container_name: empire-cli
    restart: unless-stopped
    environment:
      - MIMO_API_KEY=${MIMO_API_KEY}
      - MIMO_API_ENDPOINT=${MIMO_API_ENDPOINT:-https://api.xiaomimimo.com/v1}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - CLAUDE_API_KEY=${CLAUDE_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./data:/app/data
      - ./config.json:/app/config.json
    stdin_open: true
    tty: true

  # Dashboard - Streamlit 可视化大屏
  dashboard:
    build: .
    container_name: empire-dashboard
    restart: unless-stopped
    command: streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0
    environment:
      - MIMO_API_KEY=${MIMO_API_KEY}
      - MIMO_API_ENDPOINT=${MIMO_API_ENDPOINT:-https://api.xiaomimimo.com/v1}
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
      - ./config.json:/app/config.json

  # Ollama - 本地模型（可选）
  ollama:
    image: ollama/ollama:latest
    container_name: empire-ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

volumes:
  ollama_data:
"""

    with open(output_path, "w") as f:
        f.write(compose)
    log.info(f"docker-compose.yml 生成: {output_path}")
    return compose


def generate_requirements(output_path: str = None) -> str:
    """生成 requirements.txt"""
    if output_path is None:
        output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "requirements.txt")

    requirements = """# Empire Architecture v3.1 - Dependencies
streamlit>=1.28.0
"""

    with open(output_path, "w") as f:
        f.write(requirements)
    return requirements


def generate_k8s_manifests(output_dir: str = None) -> dict:
    """生成 Kubernetes 部署清单"""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "k8s")
    os.makedirs(output_dir, exist_ok=True)

    # Deployment
    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "empire-architecture", "labels": {"app": "empire"}},
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": "empire"}},
            "template": {
                "metadata": {"labels": {"app": "empire"}},
                "spec": {
                    "containers": [{
                        "name": "empire",
                        "image": "empire-architecture:latest",
                        "ports": [{"containerPort": 8501}],
                        "env": [
                            {"name": "MIMO_API_KEY", "valueFrom": {
                                "secretKeyRef": {"name": "empire-secrets", "key": "mimo-api-key"}
                            }},
                        ],
                        "resources": {
                            "requests": {"cpu": "500m", "memory": "512Mi"},
                            "limits": {"cpu": "2000m", "memory": "2Gi"},
                        },
                        "livenessProbe": {
                            "exec": {"command": ["python3", "-c", "print('OK)"]},
                            "periodSeconds": 30,
                        },
                    }],
                },
            },
        },
    }

    # Service
    service = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": "empire-service"},
        "spec": {
            "selector": {"app": "empire"},
            "ports": [{"port": 8501, "targetPort": 8501}],
            "type": "ClusterIP",
        },
    }

    # HPA
    hpa = {
        "apiVersion": "autoscaling/v2",
        "kind": "HorizontalPodAutoscaler",
        "metadata": {"name": "empire-hpa"},
        "spec": {
            "scaleTargetRef": {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "name": "empire-architecture",
            },
            "minReplicas": 1,
            "maxReplicas": 5,
            "metrics": [{
                "type": "Resource",
                "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 70}},
            }],
        },
    }

    files = {
        "deployment.json": deployment,
        "service.json": service,
        "hpa.json": hpa,
    }

    for filename, content in files.items():
        path = os.path.join(output_dir, filename)
        with open(path, "w") as f:
            json.dump(content, f, indent=2)

    log.info(f"K8s 清单生成: {output_dir}/")
    return files


def generate_lite_version(output_dir: str = None) -> str:
    """生成轻量版（边缘设备用）"""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lite-edge")
    os.makedirs(output_dir, exist_ok=True)

    lite_main = '''#!/usr/bin/env python3
"""帝国架构 v3.1 - 轻量版（边缘设备）
保留核心功能，去除重型依赖
"""
import asyncio
import json
import sys
import os
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))

# 最小化配置
API_KEY = os.environ.get("MIMO_API_KEY", "")
API_URL = os.environ.get("MIMO_API_ENDPOINT", "https://api.xiaomimimo.com/v1")

def call_llm(prompt: str, system: str = "") -> str:
    url = f"{API_URL.rstrip(\\'\\'\\/\\'\\')}/chat/completions"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({"model": "mimo-v2.5-pro", "messages": messages, "max_tokens": 2048}).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]

async def main():
    print("🏛️ Empire Architecture v3.1 Lite (Edge)")
    print(f"模型: mimo-v2.5-pro | API: {API_URL}")
    print()

    while True:
        try:
            cmd = input("👑 > ").strip()
            if cmd in ("exit", "quit", "q"):
                break
            if not cmd:
                continue
            result = call_llm(cmd, "你是帝国架构的丞相，简洁高效地回答皇帝的指令。")
            print(f"\\n📊 {result}\\n")
        except (KeyboardInterrupt, EOFError):
            break

if __name__ == "__main__":
    asyncio.run(main())
'''

    with open(os.path.join(output_dir, "main.py"), "w") as f:
        f.write(lite_main)

    log.info(f"轻量版生成: {output_dir}/")
    return output_dir


def generate_all_deploy_files(base_dir: str = None):
    """生成所有部署文件"""
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(__file__))

    generate_dockerfile(os.path.join(base_dir, "Dockerfile"))
    generate_docker_compose(os.path.join(base_dir, "docker-compose.yml"))
    generate_requirements(os.path.join(base_dir, "requirements.txt"))
    generate_k8s_manifests(os.path.join(base_dir, "k8s"))
    generate_lite_version(os.path.join(base_dir, "lite-edge"))

    log.info("所有部署文件生成完成")
