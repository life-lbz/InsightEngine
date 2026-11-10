"""统一异常处理（生产级增强：信息脱敏）。"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from observability.logger import get_logger

logger = get_logger(__name__)

# 异常响应中禁止出现的关键字
SENSITIVE_KEYWORDS = [
    "traceback", "mysql", "password", "secret", "api_key",
    "connection", "sqlalchemy", "pymilvus", "redis",
    "file://", "http://127.0.0.1", "localhost",
]


def _sanitize_error_message(msg: str) -> str:
    """脱敏错误信息，移除敏感关键字。

    入参：
        msg：原始错误信息

    返回：
        脱敏后的安全信息
    """
    lower_msg = msg.lower()
    for keyword in SENSITIVE_KEYWORDS:
        if keyword.lower() in lower_msg:
            return "服务内部错误，请稍后重试"
    return msg


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理未捕获异常：返回通用提示，详细错误写入日志。

    入参：
        request：FastAPI 请求对象
        exc：异常对象

    返回：
        JSONResponse：通用错误响应（不泄露内部信息）
    """
    trace_id = getattr(request.state, "trace_id", "unknown")

    # 完整异常信息写入结构化日志
    logger.error(
        "unhandled_exception",
        trace_id=trace_id,
        error_type=type(exc).__name__,
        error_message=str(exc),
        path=str(request.url.path),
        method=request.method,
    )

    # 返回脱敏的通用提示
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "服务暂时不可用，请稍后重试",
            "trace_id": trace_id,
        },
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理参数校验异常。"""
    trace_id = getattr(request.state, "trace_id", "unknown")
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": _sanitize_error_message(str(exc)),
            "trace_id": trace_id,
        },
    )