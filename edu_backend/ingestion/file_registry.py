"""文件注册表：基于 SHA-256 哈希实现增量同步。"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from config.settings import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class FileRecord:
    """文件注册记录。

    属性：
        file_path：文件路径
        file_hash：文件 SHA-256 哈希
        kb_version：知识库版本
        chunk_count：已入库 chunk 数
    """

    file_path: str
    file_hash: str
    kb_version: str
    chunk_count: int


def compute_file_hash(file_path: Path) -> str:
    """计算文件 SHA-256 哈希。

    入参：
        file_path：文件路径

    返回：
        十六进制哈希字符串
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            sha256.update(block)
    return sha256.hexdigest()


class FileRegistry:
    """文件注册表管理器：判断文件是否需要入库。"""

    def __init__(self) -> None:
        """初始化文件注册表，创建 SQLAlchemy 引擎。"""
        settings = get_settings()
        self.engine = create_engine(
            settings.mysql_sync_uri,
            **settings.mysql_engine_kwargs,
        )

    def get_existing_record(
        self,
        file_path: str,
        kb_version: str,
    ) -> FileRecord | None:
        """查询文件是否已入库。

        入参：
            file_path：文件路径
            kb_version：知识库版本

        返回：
            已有记录的 FileRecord，或 None（未入库）
        """
        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT file_path, file_hash, kb_version, chunk_count "
                    "FROM file_registry "
                    "WHERE file_path = :path AND kb_version = :ver"
                ),
                {"path": file_path, "ver": kb_version},
            )
            row = result.fetchone()

        if row is None:
            return None
        return FileRecord(
            file_path=row[0],
            file_hash=row[1],
            kb_version=row[2],
            chunk_count=row[3],
        )

    def should_ingest(
        self,
        file_path: Path,
        kb_version: str,
    ) -> tuple[bool, str | None]:
        """判断文件是否需要入库。

        入参：
            file_path：文件路径
            kb_version：知识库版本

        返回：
            (是否需要入库, 现有哈希或 None)
            - (True, None)：新文件，需要入库
            - (True, old_hash)：文件已变更，需要重新入库
            - (False, current_hash)：文件未变更，跳过
        """
        path_str = str(file_path)
        record = self.get_existing_record(path_str, kb_version)

        if record is None:
            return True, None

        current_hash = compute_file_hash(file_path)
        if current_hash == record.file_hash:
            logger.info(
                "file_skipped_unchanged",
                file=path_str,
                kb_version=kb_version,
            )
            return False, record.file_hash

        return True, record.file_hash

    def register_file(
        self,
        file_path: str,
        file_hash: str,
        kb_version: str,
        chunk_count: int,
    ) -> None:
        """注册或更新文件记录。

        入参：
            file_path：文件路径
            file_hash：文件哈希
            kb_version：知识库版本
            chunk_count：chunk 数量
        """
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO file_registry (file_path, file_hash, kb_version, chunk_count) "
                    "VALUES (:path, :hash, :ver, :count) "
                    "ON DUPLICATE KEY UPDATE file_hash = :hash, chunk_count = :count, "
                    "ingested_at = CURRENT_TIMESTAMP"
                ),
                {
                    "path": file_path,
                    "hash": file_hash,
                    "ver": kb_version,
                    "count": chunk_count,
                },
            )

    def delete_by_kb_version(self, kb_version: str) -> int:
        """删除指定版本的所有文件记录。

        入参：
            kb_version：知识库版本

        返回：
            删除的记录数
        """
        with self.engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM file_registry WHERE kb_version = :ver"),
                {"ver": kb_version},
            )
            return result.rowcount