"""入库进度追踪器：支持单文件失败跳过与断点续传。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text

from config.settings import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)

class IngestionTracker:
    """入库进度追踪器。

    功能：
        - 记录每个文件的处理状态（pending/processing/completed/failed）
        - 断点续传：重跑时跳过已完成文件
        - 失败文件记录错误信息，不中断整体流程
    """

    def __init__(self) -> None:
        """初始化追踪器，创建 SQLAlchemy 引擎。"""
        settings = get_settings()
        self.engine = create_engine(
            settings.mysql_sync_uri,
            **settings.mysql_engine_kwargs,
        )

    def get_pending_files(self, kb_version: str) -> list[dict[str, Any]]:
        """获取待处理的文件列表。

        入参：
            kb_version：知识库版本

        返回：
            待处理（pending/failed）文件记录列表
        """
        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT file_path, file_hash FROM ingestion_progress "
                    "WHERE kb_version = :ver AND status IN ('pending', 'failed') "
                    "ORDER BY id"
                ),
                {"ver": kb_version},
            )
            return [
                {"file_path": row[0], "file_hash": row[1]}
                for row in result.fetchall()
            ]

    def mark_processing(self, file_path: str, kb_version: str) -> None:
        """标记文件为处理中。"""
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE ingestion_progress SET status = 'processing' "
                    "WHERE file_path = :path AND kb_version = :ver"
                ),
                {"path": file_path, "ver": kb_version},
            )

    def mark_completed(
        self,
        file_path: str,
        kb_version: str,
        chunk_count: int,
    ) -> None:
        """标记文件为已完成。"""
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE ingestion_progress "
                    "SET status = 'completed', chunk_count = :count, "
                    "processed_at = :now, error_msg = NULL "
                    "WHERE file_path = :path AND kb_version = :ver"
                ),
                {
                    "path": file_path,
                    "ver": kb_version,
                    "count": chunk_count,
                    "now": datetime.now(),
                },
            )
        logger.info(
            "file_ingested",
            file=file_path,
            kb_version=kb_version,
            chunks=chunk_count,
        )

    def mark_failed(
        self,
        file_path: str,
        kb_version: str,
        error_msg: str,
    ) -> None:
        """标记文件为失败，记录错误信息。"""
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE ingestion_progress "
                    "SET status = 'failed', error_msg = :err, "
                    "processed_at = :now "
                    "WHERE file_path = :path AND kb_version = :ver"
                ),
                {
                    "path": file_path,
                    "ver": kb_version,
                    "err": error_msg[:1000],
                    "now": datetime.now(),
                },
            )
        logger.warning(
            "file_ingestion_failed",
            file=file_path,
            kb_version=kb_version,
            error=error_msg,
        )

    def register_file(
        self,
        file_path: str,
        file_hash: str,
        kb_version: str,
    ) -> None:
        """注册文件到进度表（如果不存在）。"""
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT IGNORE INTO ingestion_progress "
                    "(file_path, file_hash, kb_version, status) "
                    "VALUES (:path, :hash, :ver, 'pending')"
                ),
                {
                    "path": file_path,
                    "hash": file_hash,
                    "ver": kb_version,
                },
            )

    def get_summary(self, kb_version: str) -> dict[str, int]:
        """获取入库汇总信息。

        入参：
            kb_version：知识库版本

        返回：
            {"total": int, "completed": int, "failed": int, "pending": int}
        """
        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT status, COUNT(*) as cnt "
                    "FROM ingestion_progress "
                    "WHERE kb_version = :ver "
                    "GROUP BY status"
                ),
                {"ver": kb_version},
            )
            counts = {row[0]: row[1] for row in result.fetchall()}

        return {
            "total": sum(counts.values()),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0),
            "pending": counts.get("pending", 0) + counts.get("processing", 0),
        }