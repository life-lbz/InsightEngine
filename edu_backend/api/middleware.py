"""API 中间件：链路追踪、请求日志。"""
from __future__ import annotations

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from observability.logger import bind_request_context, get_logger
from observability.metrics import rag_request_duration

logger = get_logger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """链路追踪中间件。

    功能：
        - 为每个请求生成 trace_id（UUID）
        - 注入到 request.state 供后续使用
        - 绑定到 structlog contextvars
        - 记录请求开始/完成日志
    """

    async def dispatch(self, request: Request, call_next):
        # 生成或复用 trace_id
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        request.state.trace_id = trace_id

        # 绑定日志上下文
        session_id = request.headers.get("X-Session-ID", "")
        bind_request_context(trace_id, session_id)

        start_time = time.perf_counter()

        # 记录请求开始
        logger.info(
            "request_started",
            method=request.method,
            path=str(request.url.path),
            trace_id=trace_id,
        )

        response = await call_next(request)

        # 记录请求完成
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            "request_completed",
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            trace_id=trace_id,
        )

        # 添加 trace_id 到响应头
        response.headers["X-Trace-ID"] = trace_id

        return response