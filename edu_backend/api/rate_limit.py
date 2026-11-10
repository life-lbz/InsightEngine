"""基于内存滑动窗口的 API 限流中间件（读写分级 + 系统接口豁免）。"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config.settings import get_settings

# 完全豁免限流的系统路径（健康检查、API 文档、监控指标）
EXEMPT_PATHS: frozenset[str] = frozenset({
    "/api/v1/admin/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/metrics",
})

# WebSocket 握手路径：连接建立后长驻，不应反复计数
WS_PATHS: frozenset[str] = frozenset({
    "/api/v1/agent/stream",
    "/api/v1/stream",
})


class RateLimitMiddleware(BaseHTTPMiddleware):
    """滑动窗口限流：按客户端 IP 限制每分钟请求数。

    策略：
        - 读请求（GET/HEAD）配额 = 基础配额 × read_multiplier，适配前端轮询
        - 写请求（POST/PUT/DELETE/PATCH）使用基础配额
        - 系统路径与 WebSocket 握手豁免
    """

    def __init__(self, app, requests_per_minute: int = 300, read_multiplier: int = 3):
        super().__init__(app)
        self.limit = requests_per_minute
        self.read_limit = requests_per_minute * max(read_multiplier, 1)
        # 读写独立窗口：读轮询不挤占写配额，反之亦然
        self._read_windows: dict[str, list[float]] = defaultdict(list)
        self._write_windows: dict[str, list[float]] = defaultdict(list)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if path in EXEMPT_PATHS or path in WS_PATHS:
            return await call_next(request)

        is_read = request.method in ("GET", "HEAD")
        limit = self.read_limit if is_read else self.limit

        client_ip = request.client.host if request.client else "unknown"
        windows = self._read_windows if is_read else self._write_windows
        now = time.monotonic()
        window = windows[client_ip]
        window[:] = [t for t in window if now - t < 60]
        if len(window) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"请求过于频繁，{limit} 次/分钟上限（"
                    f"{'读' if is_read else '写'}请求）"
                },
                headers={"Retry-After": "60"},
            )
        window.append(now)
        return await call_next(request)


def setup_rate_limit(app) -> None:
    """注册限流中间件到 FastAPI 应用。"""
    settings = get_settings()
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.api_rate_limit_per_minute,
        read_multiplier=settings.api_rate_limit_read_multiplier,
    )
