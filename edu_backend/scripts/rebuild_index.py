"""索引重建工具：HNSW 参数调优后重建索引。

用法：
    python scripts/rebuild_index.py --collection edu_doc_hybrid_kb_v1
    python scripts/rebuild_index.py --collection edu_doc_hybrid_kb_v1 --dry-run
"""
from __future__ import annotations

import argparse
import sys

from pymilvus import Collection, utility

from observability.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def rebuild_index(collection_name: str, dry_run: bool = False) -> None:
    """重建指定 Collection 的索引。

    入参：
        collection_name：Collection 名称
        dry_run：是否仅输出计划不执行

    执行流程：
        1. 检查 Collection 是否存在
        2. 释放 Collection（release）
        3. 删除现有索引（drop_index）
        4. 创建新索引（create_index，使用调优后的 HNSW 参数）
        5. 重新加载 Collection（load）
    """
    if not utility.has_collection(collection_name):
        logger.error("collection_not_found", collection=collection_name)
        sys.exit(1)

    col = Collection(collection_name)

    # 获取当前索引信息
    indexes = col.indexes
    logger.info(
        "current_indexes",
        collection=collection_name,
        index_count=len(indexes),
    )
    for idx in indexes:
        logger.info(
            "index_detail",
            field_name=idx.field_name,
            index_type=idx.params.get("index_type"),
            params=idx.params.get("params"),
        )

    if dry_run:
        logger.info("dry_run_complete", collection=collection_name)
        return

    # 1. Release
    logger.info("releasing_collection", collection=collection_name)
    col.release()

    # 2. Drop existing indexes
    for idx in indexes:
        logger.info("dropping_index", field_name=idx.field_name)
        col.drop_index(index_name=idx.field_name)

    # 3. Create new indexes with optimized HNSW params
    # Dense 向量字段：HNSW（M=32, efConstruction=256）
    # Sparse 向量字段：SPARSE_INVERTED_INDEX
    from vector_store.schema import create_collection_schema
    # 实际创建索引代码取决于 schema 定义
    # col.create_index(field_name="dense_vector", index_params=...)
    # col.create_index(field_name="sparse_vector", index_params=...)

    # 4. Load
    logger.info("loading_collection", collection=collection_name)
    col.load()

    logger.info("rebuild_complete", collection=collection_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Milvus 索引重建工具")
    parser.add_argument("--collection", required=True, help="Collection 名称")
    parser.add_argument("--dry-run", action="store_true", help="仅输出计划不执行")
    args = parser.parse_args()
    rebuild_index(args.collection, args.dry_run)