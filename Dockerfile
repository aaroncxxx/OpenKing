# Empire Architecture v3.1 - Docker
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
HEALTHCHECK --interval=30s --timeout=10s \
    CMD python3 -c "from chancellor import Chancellor; c = Chancellor(); print('OK')" || exit 1

# 默认启动 CLI
CMD ["python3", "main.py"]
