"""标准化入库 CLI 工具。

用法：
    # 全量入库
    python scripts/ingest_data.py full --input ./courseware --course default_course

    # 增量入库（仅处理新增/变更文件）
    python scripts/ingest_data.py incremental --input ./courseware

    # 仅校验不入库
    python scripts/ingest_data.py validate --input ./courseware

    # 指定知识库版本
    python scripts/ingest_data.py full --input ./courseware --kb-version kb_20260815_v2

    # Dry-Run 预检
    python scripts/ingest_data.py full --input ./courseware --dry-run
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

# 将项目根目录（edu_backend）加入模块搜索路径，支持直接运行脚本
# 必须在任何 config/ingestion/observability 导入之前执行
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_settings
from ingestion.file_registry import FileRegistry, compute_file_hash
from ingestion.ingestion_tracker import IngestionTracker
from ingestion.quality_checker import ChunkQualityChecker
from ingestion.sanitizer import sanitize_chunks
from ingestion.validator import validate_file_type, validate_table_columns
from observability.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def discover_files(input_dir: Path) -> list[Path]:
    """扫描目录下所有支持类型的文件。

    入参：
        input_dir：输入目录

    返回：
        文件路径列表（已过滤白名单后缀）
    """
    from ingestion.validator import ALLOWED_EXTENSIONS
    files: list[Path] = []
    for f in input_dir.rglob("*"):
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
            files.append(f)
    return sorted(files)


def process_file(
    file_path: Path,
    kb_version: str,
    dry_run: bool = False,
) -> int:
    """处理单个文件：加载 → 校验 → 分块 → 质量检查 → 脱敏 → 入库。

    入参：
        file_path：文件路径
        kb_version：知识库版本
        dry_run：是否仅预检不入库

    返回：
        成功入库的 chunk 数（dry_run 模式下返回预计 chunk 数）
    """
    settings = get_settings()

    # 1. 文件类型校验
    type_result = validate_file_type(file_path)
    if not type_result.valid:
        logger.warning("file_validation_failed", file=str(file_path), errors=type_result.errors)
        return 0

    # 2. 加载文件（使用原方案 Loader）
    from ingestion.loader_registry import get_loader
    loader = get_loader(file_path.suffix.lower())
    if loader is None:
        logger.warning("no_loader_found", file=str(file_path), ext=file_path.suffix)
        return 0

    start_time = time.perf_counter()
    chunks = loader.load(file_path)

    if not chunks:
        logger.warning("file_empty_chunks", file=str(file_path))
        return 0

    # 3. 质量检查
    checker = ChunkQualityChecker(
        min_chars=settings.min_chunk_chars,
        dedup_jaccard_threshold=settings.chunk_dedup_jaccard_threshold,
    )
    chunks = checker.check_batch(chunks)

    # 4. 脱敏
    chunks = sanitize_chunks(chunks)

    # 5. 写入 Milvus（非 dry_run 时）
    if not dry_run:
        from vector_store.milvus_client import get_milvus_store
        store = get_milvus_store()
        # 为每个 chunk 设置 kb_version
        for chunk in chunks:
            chunk["kb_version"] = kb_version
        store.add_documents(
            collection_name=f"edu_doc_hybrid_{kb_version}",
            chunks=chunks,
            batch_size=settings.embedding_batch_size,
        )

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    logger.info(
        "file_processed",
        file=str(file_path),
        chunks=len(chunks),
        elapsed_ms=elapsed_ms,
        dry_run=dry_run,
    )
    return len(chunks)


def run_full_ingest(
    input_dir: Path,
    course_id: str,
    kb_version: str,
    dry_run: bool,
) -> None:
    """全量入库。

    入参：
        input_dir：输入目录
        course_id：课程 ID
        kb_version：知识库版本
        dry_run：是否仅预检
    """
    files = discover_files(input_dir)
    logger.info("full_ingest_start", file_count=len(files), course_id=course_id, kb_version=kb_version)

    registry = FileRegistry()
    tracker = IngestionTracker()

    total_chunks = 0
    success_count = 0
    fail_count = 0

    for file_path in files:
        try:
            # 注册文件（dry-run 模式下不修改数据库状态）
            file_hash = compute_file_hash(file_path)
            if not dry_run:
                tracker.register_file(str(file_path), file_hash, kb_version)
                tracker.mark_processing(str(file_path), kb_version)

            # 处理文件
            chunk_count = process_file(file_path, kb_version, dry_run)
            total_chunks += chunk_count

            if not dry_run:
                tracker.mark_completed(str(file_path), kb_version, chunk_count)
                registry.register_file(str(file_path), file_hash, kb_version, chunk_count)

            success_count += 1
        except Exception as exc:
            fail_count += 1
            if not dry_run:
                tracker.mark_failed(str(file_path), kb_version, str(exc))
            logger.error("file_processing_error", file=str(file_path), error=str(exc))

    summary = tracker.get_summary(kb_version) if not dry_run else {}
    logger.info(
        "full_ingest_complete",
        total_files=len(files),
        success=success_count,
        failed=fail_count,
        total_chunks=total_chunks,
        summary=summary,
    )


def run_incremental_ingest(
    input_dir: Path,
    kb_version: str,
    dry_run: bool,
) -> None:
    """增量入库：仅处理新增/变更文件。

    入参：
        input_dir：输入目录
        kb_version：知识库版本
        dry_run：是否仅预检
    """
    files = discover_files(input_dir)
    registry = FileRegistry()
    tracker = IngestionTracker()

    pending_files: list[Path] = []
    for file_path in files:
        should_ingest, _ = registry.should_ingest(file_path, kb_version)
        if should_ingest:
            pending_files.append(file_path)

    logger.info(
        "incremental_ingest_start",
        total_files=len(files),
        pending_files=len(pending_files),
        kb_version=kb_version,
    )

    if not pending_files:
        logger.info("no_new_files_to_ingest")
        return

    total_chunks = 0
    for file_path in pending_files:
        try:
            file_hash = compute_file_hash(file_path)
            if not dry_run:
                tracker.register_file(str(file_path), file_hash, kb_version)
                tracker.mark_processing(str(file_path), kb_version)
            chunk_count = process_file(file_path, kb_version, dry_run)
            total_chunks += chunk_count
            if not dry_run:
                tracker.mark_completed(str(file_path), kb_version, chunk_count)
                registry.register_file(str(file_path), file_hash, kb_version, chunk_count)
        except Exception as exc:
            if not dry_run:
                tracker.mark_failed(str(file_path), kb_version, str(exc))
            logger.error("incremental_file_error", file=str(file_path), error=str(exc))

    logger.info(
        "incremental_ingest_complete",
        processed=len(pending_files),
        total_chunks=total_chunks,
    )


def run_validate_only(input_dir: Path) -> None:
    """仅校验文件，不入库。

    入参：
        input_dir：输入目录
    """
    files = discover_files(input_dir)
    logger.info("validation_start", file_count=len(files))

    valid_count = 0
    invalid_count = 0

    for file_path in files:
        result = validate_file_type(file_path)
        if result.valid:
            valid_count += 1
            print(f"  ✓ {file_path}")
        else:
            invalid_count += 1
            print(f"  ✗ {file_path}")
            for err in result.errors:
                print(f"      {err}")

    print(f"\n校验完成：{valid_count} 通过，{invalid_count} 失败")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="教育答疑 RAG 数据入库工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # full 子命令
    full_parser = subparsers.add_parser("full", help="全量入库")
    full_parser.add_argument("--input", required=True, help="输入目录")
    full_parser.add_argument("--course", default="default_course", help="课程 ID")
    full_parser.add_argument("--kb-version", default="kb_manual_v1", help="知识库版本")
    full_parser.add_argument("--dry-run", action="store_true", help="仅预检不入库")

    # incremental 子命令
    incr_parser = subparsers.add_parser("incremental", help="增量入库")
    incr_parser.add_argument("--input", required=True, help="输入目录")
    incr_parser.add_argument("--kb-version", default="kb_manual_v1", help="知识库版本")
    incr_parser.add_argument("--dry-run", action="store_true", help="仅预检不入库")

    # validate 子命令
    val_parser = subparsers.add_parser("validate", help="仅校验")
    val_parser.add_argument("--input", required=True, help="输入目录")

    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.is_dir():
        print(f"错误：输入目录不存在: {input_dir}")
        sys.exit(1)

    if args.command == "full":
        run_full_ingest(input_dir, args.course, args.kb_version, args.dry_run)
    elif args.command == "incremental":
        run_incremental_ingest(input_dir, args.kb_version, args.dry_run)
    elif args.command == "validate":
        run_validate_only(input_dir)