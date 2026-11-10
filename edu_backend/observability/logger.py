"""结构化日志配置：基于 structlog 输出 JSON 格式日志。

使用方式：
    from observability.logger import get_logger
    logger = get_logger(__name__)
    logger.info("rag_pipeline_complete", intent="KNOWLEDGE_QUERY", duration_ms=3200)
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any

import structlog


def configure_logging(
    log_level: str | None = None,
    log_dir: str | None = None,
    json_output: bool | None = None,
) -> None:
    """配置全局结构化日志。

    入参：
        log_level：日志级别（DEBUG/INFO/WARN/ERROR），默认从 settings 读取
        log_dir：日志文件目录，默认从 settings 读取
        json_output：是否输出 JSON 格式（生产环境推荐 True），默认从 settings 读取

    边界条件：
        - log_dir 不存在时自动创建
        - 日志按天滚动，保留 30 天
    """
    try:
        from config.settings import get_settings
        settings = get_settings()
        log_level = log_level or settings.log_level
        log_dir = log_dir or settings.log_dir
        json_output = json_output if json_output is not None else settings.log_json_output
    except Exception:
        log_level = log_level or "INFO"
        log_dir = log_dir or "/var/log/insight_engine"
        json_output = json_output if json_output is not None else True

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 配置标准 logging 作为底层
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    # 文件处理器：按天滚动，注册到 root logger
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_path / "insight_engine.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(file_handler)

    # structlog 配置
    # merge_contextvars 会自动注入 bind_request_context 绑定的 trace_id/session_id
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer(ensure_ascii=False))
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """获取结构化 logger 实例。

    入参：
        name：模块名称（通常传 __name__）

    返回：
        structlog BoundLogger 实例
    """
    return structlog.get_logger(name)


def bind_request_context(trace_id: str, session_id: str = "") -> None:
    """绑定请求级上下文（trace_id、session_id），后续日志自动携带。

    入参：
        trace_id：分布式链路追踪 ID
        session_id：学员会话 ID
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    if session_id:
        structlog.contextvars.bind_contextvars(session_id=session_id)