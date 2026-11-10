FROM python:3.11-slim AS base

# 安装系统依赖：libgomp1 用于 BGE 模型推理
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# 创建日志目录并授权
RUN mkdir -p /var/log/insight_engine && chown -R appuser:appuser /var/log/insight_engine

WORKDIR /app

# 安装 PyTorch CPU 版本（FlagEmbedding 依赖 torch）
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

RUN chown -R appuser:appuser /app

# 预下载模型文件（构建时缓存）
RUN python -c "from FlagEmbedding import BGEM3FlagModel; BGEM3FlagModel('./models/bge-m3', use_fp16=True)" || true
RUN python -c "from FlagEmbedding import FlagReranker; FlagReranker('./models/bge-reranker-large', use_fp16=True)" || true

USER appuser

EXPOSE 8000

# 日志目录挂载点
VOLUME ["/var/log/insight_engine"]

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD python scripts/healthcheck.py --json | python -c "import sys,json; exit(0 if all(r['status']=='healthy' for r in json.load(sys.stdin)) else 1)"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
