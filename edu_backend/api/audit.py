"""操作审计：记录管理接口的所有调用。"""
from __future__ import annotations

import hashlib
import time
from typing import Any

from sqlalchemy import create_engine, text
from fastapi import Request, Response

from config.settings import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)


class AuditLogger:
    """操作审计日志记录器。

    记录内容：
        - operator_id：操作者 ID
        - action：操作类型（create/update/delete/ingest/export）
        - resource：操作资源（course/kb_version/config）
        - request_body_hash：请求体 hash（不含明文）
        - response_status：响应状态码
        - ip：请求 IP
        - trace_id：链路追踪 ID
    """

    def __init__(self) -> None:
        """初始化审计日志记录器。"""
        settings = get_settings()
        self.engine = create_engine(
            settings.mysql_sync_uri,
            **settings.mysql_engine_kwargs,
        )

    def log(
        self,
        operator_id: str,
        action: str,
        resource: str,
        request_body: str,
        response_status: int,
        ip: str,
        trace_id: str = "",
        user_agent: str = "",
    ) -> None:
        """记录操作审计日志。

        入参：
            operator_id：操作者 ID
            action：操作类型
            resource：操作资源
            request_body：请求体原文（将仅记录 hash）
            response_status：响应状态码
            ip：请求 IP
            trace_id：链路追踪 ID
            user_agent：User-Agent
        """
        # 仅记录请求体 hash，不记录明文
        body_hash = hashlib.sha256(
            request_body.encode("utf-8")
        ).hexdigest()[:16] if request_body else None

        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO audit_logs "
                        "(operator_id, action, resource, request_body_hash, "
                        "response_status, ip, user_agent, trace_id) "
                        "VALUES (:oid, :act, :res, :bh, :rs, :ip, :ua, :tid)"
                    ),
                    {
                        "oid": operator_id,
                        "act": action,
                        "res": resource,
                        "bh": body_hash,
                        "rs": response_status,
                        "ip": ip,
                        "ua": user_agent[:256] if user_agent else None,
                        "tid": trace_id,
                    },
                )
        except Exception as exc:
            logger.warning("audit_log_write_failed", error=str(exc))


_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """返回审计日志记录器单例。"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger