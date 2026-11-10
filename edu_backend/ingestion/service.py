"""入库服务：将 CLI 管线封装为可被 API 调用的函数。

提供单文件处理、全量/增量入库、进度查询、文档管理能力。
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from config.settings import get_settings
from ingestion.file_registry import FileRegistry, compute_file_hash
from ingestion.ingestion_tracker import IngestionTracker
from ingestion.loader_registry import get_loader
from ingestion.quality_checker import ChunkQualityChecker
from ingestion.sanitizer import sanitize_chunks
from ingestion.validator import ALLOWED_EXTENSIONS, validate_file_type
from observability.logger import get_logger

logger = get_logger(__name__)


def process_single_file(
    file_path: Path,
    kb_version: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """处理单个文件：加载 → 校验 → 分块 → 质量检查 → 脱敏 → 入库。

    入参：
        file_path：文件路径
        kb_version：知识库版本
        dry_run：仅预检不入库

    返回：
        {"file_path": str, "chunks": int, "elapsed_ms": int, "error": str | None}
    """
    settings = get_settings()
    start = time.perf_counter()
    result: dict[str, Any] = {
        "file_path": str(file_path),
        "chunks": 0,
        "elapsed_ms": 0,
        "error": None,
    }

    type_result = validate_file_type(file_path)
    if not type_result.valid:
        result["error"] = "; ".join(type_result.errors)
        return result

    loader = get_loader(file_path.suffix.lower())
    if loader is None:
        result["error"] = f"不支持的文件类型: {file_path.suffix}"
        return result

    chunks = loader.load(file_path)
    if not chunks:
        result["error"] = "文件内容为空"
        return result

    checker = ChunkQualityChecker(
        min_chars=settings.min_chunk_chars,
        dedup_jaccard_threshold=settings.chunk_dedup_jaccard_threshold,
    )
    chunks = checker.check_batch(chunks)
    chunks = [c for c in chunks if c.get("quality_score", 0) > 0]

    if not chunks:
        result["error"] = "所有 chunk 质量检查未通过"
        return result

    chunks = sanitize_chunks(chunks)

    if not dry_run:
        from vector_store.milvus_client import get_milvus_store

        file_hash = compute_file_hash(file_path)
        store = get_milvus_store()
        collection_name = f"edu_doc_hybrid_{kb_version}"
        for chunk in chunks:
            chunk["kb_version"] = kb_version
            chunk["file_hash"] = file_hash
        store.add_documents(
            collection_name=collection_name,
            chunks=chunks,
            batch_size=settings.embedding_batch_size,
        )

    result["chunks"] = len(chunks)
    result["elapsed_ms"] = int((time.perf_counter() - start) * 1000)
    return result


def run_full_ingestion(
    input_dir: Path,
    course_id: str,
    kb_version: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """全量入库。

    返回：
        {"total_files": int, "success": int, "failed": int, "total_chunks": int, "errors": list}
    """
    files = [
        f
        for f in sorted(input_dir.rglob("*"))
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS
    ]

    registry = FileRegistry()
    tracker = IngestionTracker()

    total_chunks = 0
    success_count = 0
    fail_count = 0
    errors: list[str] = []

    for file_path in files:
        try:
            file_hash = compute_file_hash(file_path)
            if not dry_run:
                tracker.register_file(str(file_path), file_hash, kb_version)
                tracker.mark_processing(str(file_path), kb_version)

            r = process_single_file(file_path, kb_version, dry_run)
            total_chunks += r["chunks"]

            if r["error"]:
                raise RuntimeError(r["error"])

            if not dry_run:
                tracker.mark_completed(str(file_path), kb_version, r["chunks"])
                registry.register_file(str(file_path), file_hash, kb_version, r["chunks"])
            success_count += 1
        except Exception as exc:
            fail_count += 1
            errors.append(f"{file_path.name}: {exc}")
            if not dry_run:
                tracker.mark_failed(str(file_path), kb_version, str(exc))
            logger.error("ingest_file_error", file=str(file_path), error=str(exc))

    summary = tracker.get_summary(kb_version) if not dry_run else {}
    return {
        "total_files": len(files),
        "success": success_count,
        "failed": fail_count,
        "total_chunks": total_chunks,
        "errors": errors,
        "summary": summary,
    }


def run_incremental_ingestion(
    input_dir: Path,
    kb_version: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """增量入库：仅处理新增/变更文件。"""
    files = [
        f
        for f in sorted(input_dir.rglob("*"))
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS
    ]
    registry = FileRegistry()
    tracker = IngestionTracker()

    pending: list[Path] = []
    for f in files:
        should, _ = registry.should_ingest(f, kb_version)
        if should:
            pending.append(f)

    if not pending:
        return {"total_files": 0, "success": 0, "failed": 0, "total_chunks": 0, "errors": []}

    total_chunks = 0
    success_count = 0
    fail_count = 0
    errors: list[str] = []

    for file_path in pending:
        try:
            file_hash = compute_file_hash(file_path)
            if not dry_run:
                tracker.register_file(str(file_path), file_hash, kb_version)
                tracker.mark_processing(str(file_path), kb_version)
            r = process_single_file(file_path, kb_version, dry_run)
            total_chunks += r["chunks"]
            if r["error"]:
                raise RuntimeError(r["error"])
            if not dry_run:
                tracker.mark_completed(str(file_path), kb_version, r["chunks"])
                registry.register_file(str(file_path), file_hash, kb_version, r["chunks"])
            success_count += 1
        except Exception as exc:
            fail_count += 1
            errors.append(f"{file_path.name}: {exc}")
            if not dry_run:
                tracker.mark_failed(str(file_path), kb_version, str(exc))
            logger.error("incremental_file_error", file=str(file_path), error=str(exc))

    return {
        "total_files": len(pending),
        "success": success_count,
        "failed": fail_count,
        "total_chunks": total_chunks,
        "errors": errors,
    }


def get_ingestion_progress(kb_version: str) -> dict[str, Any]:
    """获取入库进度。"""
    tracker = IngestionTracker()
    summary = tracker.get_summary(kb_version)

    from sqlalchemy import create_engine, text

    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT file_path, file_hash, kb_version, status, chunk_count, "
                "error_msg, created_at, processed_at FROM ingestion_progress "
                "WHERE kb_version = :kbv ORDER BY created_at DESC LIMIT 100"
            ),
            {"kbv": kb_version},
        )
        items = [
            {
                "file_path": r[0],
                "file_hash": r[1],
                "kb_version": r[2],
                "status": r[3],
                "chunk_count": r[4],
                "error_msg": r[5],
                "created_at": str(r[6]) if r[6] else "",
                "processed_at": str(r[7]) if r[7] else "",
            }
            for r in rows
        ]
    engine.dispose()
    return {"summary": summary, "items": items}


def get_documents(
    page: int = 1,
    page_size: int = 20,
    kb_version: str | None = None,
) -> dict[str, Any]:
    """从 file_registry 表查询文档列表。"""
    from sqlalchemy import create_engine, text

    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    offset = (page - 1) * page_size

    where_clause = "WHERE kb_version = :kbv" if kb_version else ""
    params: dict[str, Any] = {"lim": page_size, "off": offset}
    if kb_version:
        params["kbv"] = kb_version

    with engine.connect() as conn:
        result = conn.execute(
            text(
                f"SELECT file_path, file_hash, kb_version, chunk_count, ingested_at "
                f"FROM file_registry {where_clause} "
                f"ORDER BY ingested_at DESC LIMIT :lim OFFSET :off"
            ),
            params,
        )
        docs = [
            {
                "file_path": r[0],
                "file_hash": r[1],
                "kb_version": r[2],
                "chunk_count": r[3],
                "ingested_at": str(r[4]) if r[4] else "",
            }
            for r in result
        ]
        count_result = conn.execute(
            text(f"SELECT COUNT(*) FROM file_registry {where_clause}"), params
        )
        total = count_result.scalar() or 0
    engine.dispose()
    return {"documents": docs, "total": total}


def delete_document(file_hash: str, kb_version: str) -> bool:
    """从 Milvus 和 file_registry 删除文档。"""
    from sqlalchemy import create_engine, text
    from vector_store.milvus_client import get_milvus_store

    collection_name = f"edu_doc_hybrid_{kb_version}"
    store = get_milvus_store()
    expr = f'file_hash == "{file_hash}"'
    store.delete_by_expr(collection_name, expr)

    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM file_registry WHERE file_hash = :fh AND kb_version = :kbv"
            ),
            {"fh": file_hash, "kbv": kb_version},
        )
    engine.dispose()
    logger.info("document_deleted", file_hash=file_hash, kb_version=kb_version)
    return True


async def run_ingestion_background(
    input_dir: Path,
    course_id: str,
    kb_version: str,
    mode: str = "full",
) -> dict[str, Any]:
    """异步执行入库（供 API 端点调用，避免阻塞请求）。"""
    if mode == "incremental":
        result = run_incremental_ingestion(input_dir, kb_version)
    else:
        result = run_full_ingestion(input_dir, course_id, kb_version)
    return result
