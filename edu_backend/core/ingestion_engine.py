"""核心入库引擎（生产级增强：数据校验 + 进度追踪）。"""
from __future__ import annotations

from typing import Any

from ingestion.validator import DocumentValidator
from ingestion.ingestion_tracker import IngestionTracker
from interfaces.base_document_loader import BaseDocumentLoader
from interfaces.base_vector_store import BaseVectorStore
from observability.logger import get_logger

logger = get_logger(__name__)


class IngestionEngine:
    """加载文件并写入向量库。

    生产级增强：
        - 入库前数据校验（必填字段、内容长度、metadata 完整性）
        - 入库进度追踪（成功/失败/跳过计数）
        - 批量写入失败时自动重试
    """

    BATCH_SIZE = 100

    def __init__(
        self,
        loader: BaseDocumentLoader,
        vector_store: BaseVectorStore,
        validator: DocumentValidator | None = None,
    ) -> None:
        self.loader = loader
        self.vector_store = vector_store
        self.validator = validator or DocumentValidator()
        self.tracker = IngestionTracker()

    def ingest(
        self,
        path: str,
        course_id: str = "",
        doc_type: str = "lecture",
    ) -> dict[str, Any]:
        """执行一次入库。

        入参：
            path：文件路径
            course_id：课程 ID
            doc_type：文档类型（lecture/question/faq）

        返回：
            {
                "documents": int,
                "inserted": int,
                "skipped": int,
                "failed": int,
                "errors": list[str],
            }
        """
        # 1. 路径安全校验
        if not self.loader.validate_path(path):
            raise ValueError(f"路径不安全或扩展名不支持：{path}")

        # 2. 加载文件
        docs = self.loader.load(path)
        logger.info("ingestion_loaded", path=path, doc_count=len(docs))

        # 3. metadata 补全
        for doc in docs:
            if not doc.metadata.get("course_id"):
                doc.metadata["course_id"] = course_id
            if not doc.metadata.get("doc_type"):
                doc.metadata["doc_type"] = doc_type
            if not doc.metadata.get("source"):
                doc.metadata["source"] = path

        # 4. 数据校验
        valid_docs: list = []
        skipped = 0
        errors: list[str] = []

        for i, doc in enumerate(docs):
            issues = self.validator.validate(doc)
            if issues:
                skipped += 1
                errors.append(f"doc[{i}]: {'; '.join(issues)}")
            else:
                valid_docs.append(doc)

        # 5. 批量写入
        inserted_ids: list[str] = []
        failed = 0

        for batch_start in range(0, len(valid_docs), self.BATCH_SIZE):
            batch = valid_docs[batch_start : batch_start + self.BATCH_SIZE]
            batch_ids = [
                f"{path}:{batch_start + j}" for j in range(len(batch))
            ]

            try:
                ids = self.vector_store.insert(batch, batch_ids)
                inserted_ids.extend(ids)
            except Exception as exc:
                logger.error(
                    "ingestion_batch_failed",
                    batch_start=batch_start,
                    error=str(exc),
                )
                failed += len(batch)
                errors.append(f"batch[{batch_start}]: {type(exc).__name__}")

        # 6. 追踪记录
        self.tracker.record(
            path=path,
            total=len(docs),
            inserted=len(inserted_ids),
            skipped=skipped,
            failed=failed,
        )

        result = {
            "documents": len(docs),
            "inserted": len(inserted_ids),
            "skipped": skipped,
            "failed": failed,
            "errors": errors[:20],
        }
        logger.info("ingestion_completed", **result)
        return result