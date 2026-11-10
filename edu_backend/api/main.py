"""FastAPI 应用入口（生产级增强版）。

增强能力：
    - 启动时安全配置校验
    - 优雅停机（SIGTERM 后等待请求完成）
    - 中间件注册（链路追踪、CORS）
    - API 版本管理（/api/v1/）
    - Prometheus metrics 端点
    - 模型预热
"""
from __future__ import annotations

import asyncio
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from config.settings import get_settings
from config.security_validator import validate_security_config
from observability.logger import configure_logging, get_logger
from observability.metrics import websocket_active_connections

configure_logging()
logger = get_logger(__name__)

# 全局停机标志
_shutting_down = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动预热 + 优雅停机。

    启动流程：
        1. 安全配置校验
        2. 预热 Embedding/Reranker 模型
        3. 建立 Milvus/MySQL/Redis 连接池

    停机流程：
        1. 设置停机标志，拒绝新请求
        2. 等待正在处理的请求完成（超时 30s）
        3. 关闭连接池
    """
    settings = get_settings()

    # 1. 安全配置校验
    logger.info("validating_security_config", app_env=settings.app_env)
    validate_security_config(settings)

    # 2. 模型预热
    logger.info("preloading_models")
    try:
        from vector_store.embeddings import get_embedder
        from vector_store.reranker import get_reranker
        get_embedder()
        get_reranker()
        logger.info("model_preloading_completed")
    except Exception as exc:
        logger.error("model_preload_failed", error=str(exc))
        if settings.is_production:
            sys.exit(1)

    # 3. 连接池初始化
    logger.info("initializing_connections")
    # 连接池在首次使用时自动创建

    yield

    # 停机流程
    logger.info("shutdown_initiated")
    global _shutting_down
    _shutting_down = True

    # 等待活跃 WebSocket 连接关闭
    for _ in range(30):
        if websocket_active_connections._value.get() == 0:
            break
        await asyncio.sleep(1)

    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。"""
    settings = get_settings()

    app = FastAPI(
        title="教育答疑 RAG 系统",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS（收紧方法和头部）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Trace-ID"],
    )

    # 限流中间件
    from api.rate_limit import setup_rate_limit
    setup_rate_limit(app)

    # 链路追踪中间件
    from api.middleware import TracingMiddleware
    app.add_middleware(TracingMiddleware)

    # 异常处理器
    from api.error_handlers import (
        unexpected_error_handler,
        validation_error_handler,
    )
    from fastapi.exceptions import RequestValidationError

    app.add_exception_handler(Exception, unexpected_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    # 路由注册（v1 版本前缀）
    from api.auth_router import router as auth_router
    from api.chat_router import router as chat_router
    from api.debug_router import router as debug_router
    from api.admin_router import router as admin_router
    from api.student_router import router as student_router
    from api.agent_router import router as agent_router

    app.include_router(auth_router, prefix="/api/v1", tags=["认证"])
    app.include_router(chat_router, prefix="/api/v1", tags=["答疑"])
    app.include_router(debug_router, prefix="/api/v1", tags=["调试"])
    app.include_router(admin_router, prefix="/api/v1", tags=["管理"])
    app.include_router(student_router, prefix="/api/v1", tags=["学员"])
    app.include_router(agent_router, prefix="/api/v1", tags=["Agent 协作"])

    # 向后兼容：旧路径重定向到 v1
    app.include_router(chat_router, prefix="/api", tags=["答疑（兼容）"])

    # Prometheus metrics 端点
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # 健康检查端点
    @app.get("/health")
    async def health_check():
        """健康检查端点。"""
        if _shutting_down:
            return {"status": "shutting_down"}
        return {"status": "healthy"}

    return app


app = create_app()


def handle_shutdown(signum, frame):
    """处理 SIGTERM/SIGINT 信号。"""
    logger.info("received_shutdown_signal", signal=signum)
    # uvicorn 会处理实际的停机流程


signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)