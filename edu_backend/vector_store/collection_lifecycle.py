"""Collection 生命周期管理：自动归档与清理旧版本。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pymilvus import utility, Collection

from config.settings import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)


class CollectionLifecycleManager:
    """Collection 生命周期管理器。

    策略：
        - 活跃版本：保持 loaded 状态，支持快速检索
        - 非活跃版本（7天内）：release 内存索引，保留磁盘数据
        - 过期版本（30天后）：自动删除 Collection
    """

    def __init__(self) -> None:
        """初始化生命周期管理器。"""
        settings = get_settings()
        self.archive_after_days = settings.collection_archive_after_days
        self.delete_after_days = settings.collection_delete_after_days

    def archive_old_collections(self, active_versions: dict[str, str]) -> dict[str, Any]:
        """归档非活跃版本的 Collection（release 内存索引）。

        入参：
            active_versions：各课程的活跃版本 {"course_id": "kb_version"}

        返回：
            {"archived": [...], "skipped": [...]}
        """
        all_collections = utility.list_collections()
        active_collection_names = set()

        # 收集活跃版本的 collection 名称
        for course_id, kb_version in active_versions.items():
            for prefix in ["edu_doc_hybrid", "edu_faq_hybrid", "edu_question_hybrid"]:
                active_collection_names.add(f"{prefix}_{kb_version}")

        archived: list[str] = []
        skipped: list[str] = []

        for name in all_collections:
            if not name.startswith(("edu_doc_hybrid", "edu_faq_hybrid", "edu_question_hybrid")):
                continue
            if name in active_collection_names:
                skipped.append(name)
                continue

            try:
                col = Collection(name)
                # 检查是否已 release
                # release 释放内存中的索引
                col.release()
                archived.append(name)
                logger.info("collection_archived", collection=name)
            except Exception as exc:
                logger.warning("collection_archive_failed", collection=name, error=str(exc))

        logger.info(
            "archive_complete",
            archived_count=len(archived),
            skipped_count=len(skipped),
        )
        return {"archived": archived, "skipped": skipped}

    def delete_expired_collections(self) -> dict[str, Any]:
        """删除过期的 Collection（超过 delete_after_days 天）。

        返回：
            {"deleted": [...], "errors": [...]}
        """
        cutoff = datetime.now() - timedelta(days=self.delete_after_days)
        all_collections = utility.list_collections()

        deleted: list[str] = []
        errors: list[str] = []

        for name in all_collections:
            if not name.startswith(("edu_doc_hybrid", "edu_faq_hybrid", "edu_question_hybrid")):
                continue
            try:
                col = Collection(name)
                desc = col.describe()
                # 查询 kb_versions 表判断 Collection 是否过期
                with self.engine.connect() as conn:
                    row = conn.execute(
                        text(
                            "SELECT created_at, is_active FROM kb_versions "
                            "WHERE collection_name = :name ORDER BY created_at DESC LIMIT 1"
                        ),
                        {"name": name},
                    ).fetchone()
                    if row is None:
                        continue
                    created_at = row[0]
                    is_active = row[1]
                    # 仅删除非活跃且超过 delete_after_days 的 Collection
                    if is_active or created_at > cutoff:
                        continue
                col.drop()
                deleted.append(name)
            except Exception as exc:
                errors.append(f"{name}: {exc}")

        logger.info("delete_expired_complete", deleted=len(deleted), errors=len(errors))
        return {"deleted": deleted, "errors": errors}

    def preload_active_collections(self, active_versions: dict[str, str]) -> None:
        """预热活跃版本的 Collection（load 到内存）。

        入参：
            active_versions：各课程的活跃版本
        """
        for course_id, kb_version in active_versions.items():
            for prefix in ["edu_doc_hybrid", "edu_faq_hybrid", "edu_question_hybrid"]:
                name = f"{prefix}_{kb_version}"
                try:
                    col = Collection(name)
                    col.load()
                    logger.info("collection_preloaded", collection=name)
                except Exception as exc:
                    logger.warning("collection_preload_failed", collection=name, error=str(exc))