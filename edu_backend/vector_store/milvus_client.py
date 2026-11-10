"""Milvus 混合检索存储客户端：Dense + Sparse 双路检索（兼容 2.3.x 纯 Dense 降级）。"""
from __future__ import annotations

import hashlib
import time
from typing import Any

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from config.settings import get_settings
from observability.logger import get_logger
from vector_store.embeddings import embed
from vector_store.results import RetrievalResult

logger = get_logger(__name__)

DENSE_DIM = 1024

HAS_SPARSE = hasattr(DataType, "SPARSE_FLOAT_VECTOR")

_store: MilvusHybridStore | None = None


class MilvusHybridStore:
    """Milvus 混合检索存储。

    使用 BGE-M3 模型生成 Dense (1024d) + Sparse 向量，
    在 Milvus 中执行双路混合检索。
    当 pymilvus < 2.4 时自动降级为纯 Dense 检索。
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.alias = "default"
        self._connect()

    def _connect(self) -> None:
        settings = get_settings()
        if not connections.has_connection(self.alias):
            connections.connect(
                alias=self.alias,
                uri=settings.milvus_uri,
                db_name=settings.milvus_database,
            )
            logger.info(
                "milvus_connected",
                uri=settings.milvus_uri,
                db=settings.milvus_database,
                sparse=HAS_SPARSE,
            )

    def ensure_collection(self, collection_name: str) -> Collection:
        """确保 Collection 存在，不存在则创建。"""
        self._connect()
        if utility.has_collection(collection_name, using=self.alias):
            col = Collection(collection_name, using=self.alias)
            col.load()
            return col
        return self._create_collection(collection_name)

    def _create_collection(self, collection_name: str) -> Collection:
        """创建支持混合检索的 Collection（自动适配 Sparse 支持情况）。"""
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="course_id", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="kb_version", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="file_hash", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(
                name="dense_vector",
                dtype=DataType.FLOAT_VECTOR,
                dim=DENSE_DIM,
            ),
        ]
        if HAS_SPARSE:
            fields.append(
                FieldSchema(
                    name="sparse_vector",
                    dtype=DataType.SPARSE_FLOAT_VECTOR,
                )
            )
        schema = CollectionSchema(fields=fields, description="Edu RAG hybrid collection")
        col = Collection(collection_name, schema=schema, using=self.alias)

        col.create_index(
            field_name="dense_vector",
            index_params={
                "index_type": "HNSW",
                "metric_type": "COSINE",
                "params": {"M": 32, "efConstruction": 256},
            },
        )
        if HAS_SPARSE:
            col.create_index(
                field_name="sparse_vector",
                index_params={
                    "index_type": "SPARSE_INVERTED_INDEX",
                    "metric_type": "IP",
                },
            )
        col.load()
        logger.info("collection_created", name=collection_name, sparse=HAS_SPARSE)
        return col

    def add_documents(
        self,
        collection_name: str,
        chunks: list[dict[str, Any]],
        batch_size: int = 64,
    ) -> int:
        """批量写入文档到 Milvus。

        入参：
            collection_name：Collection 名称
            chunks：文档块列表，每项含 "content" 和 "kb_version"
            batch_size：Embedding 批大小

        返回：
            成功写入的条数
        """
        col = self.ensure_collection(collection_name)
        total = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c.get("text", c.get("content", "")) for c in batch]

            emb = embed(texts)
            dense_vecs = emb["dense_vecs"].tolist()

            ids = [
                hashlib.md5(f"{collection_name}_{i+j}".encode()).hexdigest()[:32]
                for j in range(len(batch))
            ]

            data = [
                ids,
                [t[:8190] for t in texts],
                [c.get("course_id", "") for c in batch],
                [c.get("kb_version", "") for c in batch],
                [c.get("file_hash", "") for c in batch],
                [c.get("source", str(c.get("file_path", ""))) for c in batch],
                dense_vecs,
            ]
            if HAS_SPARSE:
                sparse_vecs = [
                    {int(k): float(v) for k, v in sparse.items()}
                    for sparse in emb["lexical_weights"]
                ]
                data.append(sparse_vecs)
            col.insert(data)
            total += len(batch)

        col.flush()
        logger.info("documents_added", collection=collection_name, count=total)
        return total

    def search(
        self,
        query: str,
        collection_name: str,
        k: int = 10,
        expr: str | None = None,
        dense_weight: float = 0.55,
        sparse_weight: float = 0.45,
        **kwargs: Any,
    ) -> RetrievalResult:
        """混合检索：Dense + Sparse 双路加权（2.3.x 降级为纯 Dense）。

        入参：
            query：查询文本
            collection_name：Collection 名称
            k：返回 Top-K
            expr：过滤表达式
            dense_weight：Dense 权重
            sparse_weight：Sparse 权重

        返回：
            RetrievalResult
        """
        col = self.ensure_collection(collection_name)

        emb = embed(query)
        query_dense = emb["dense_vecs"][0].tolist()

        if HAS_SPARSE:
            return self._hybrid_search(
                col, query_dense, query, collection_name, k, expr,
                dense_weight, sparse_weight, emb,
            )
        return self._dense_search(
            col, query_dense, query, collection_name, k, expr,
        )

    def _dense_search(
        self,
        col: Collection,
        query_dense: list[float],
        query: str,
        collection_name: str,
        k: int,
        expr: str | None,
    ) -> RetrievalResult:
        """纯 Dense 向量检索（pymilvus 2.3.x 降级模式）。"""
        results = col.search(
            data=[query_dense],
            anns_field="dense_vector",
            param={"params": {"ef": 64}, "metric_type": "COSINE"},
            limit=k,
            expr=expr or "",
            output_fields=["content", "course_id", "kb_version", "file_hash", "source"],
        )

        hits: list[dict[str, Any]] = []
        if results:
            for hit in results[0]:
                raw = hit.entity.to_dict() if hasattr(hit, "entity") else {}
                entity = raw.get("entity", raw)
                hits.append({
                    "content": entity.get("content", ""),
                    "text": entity.get("content", ""),
                    "score": float(hit.score) if hasattr(hit, "score") else 0.0,
                    "metadata": {
                        "source": entity.get("source", ""),
                        "course_id": entity.get("course_id", ""),
                        "kb_version": entity.get("kb_version", ""),
                        "file_hash": entity.get("file_hash", ""),
                    },
                })

        return RetrievalResult(
            hits=hits,
            query=query,
            collection=collection_name,
            degraded=False,
        )

    def _hybrid_search(
        self,
        col: Collection,
        query_dense: list[float],
        query: str,
        collection_name: str,
        k: int,
        expr: str | None,
        dense_weight: float,
        sparse_weight: float,
        emb: Any,
    ) -> RetrievalResult:
        """Dense + Sparse 混合检索（pymilvus 2.4+）。"""
        from pymilvus import AnnSearchRequest, WeightedRanker

        query_sparse = {
            int(k): float(v) for k, v in emb["lexical_weights"][0].items()
        }

        dense_req = AnnSearchRequest(
            data=[query_dense],
            anns_field="dense_vector",
            param={"params": {"ef": 64}, "metric_type": "COSINE"},
            limit=k,
            expr=expr,
        )
        sparse_req = AnnSearchRequest(
            data=[query_sparse],
            anns_field="sparse_vector",
            param={"metric_type": "IP", "params": {"drop_ratio_search": 0.2}},
            limit=k,
            expr=expr,
        )

        ranker = WeightedRanker(dense_weight, sparse_weight)
        results = col.hybrid_search(
            [dense_req, sparse_req],
            ranker=ranker,
            limit=k,
            output_fields=["content", "course_id", "kb_version", "file_hash", "source"],
        )

        hits: list[dict[str, Any]] = []
        for hit in results[0] if results else []:
            raw = hit.entity.to_dict() if hasattr(hit, "entity") else {}
            entity = raw.get("entity", raw)
            hits.append({
                "content": entity.get("content", ""),
                "text": entity.get("content", ""),
                "score": float(hit.score) if hasattr(hit, "score") else 0.0,
                "metadata": {
                    "source": entity.get("source", ""),
                    "course_id": entity.get("course_id", ""),
                    "kb_version": entity.get("kb_version", ""),
                    "file_hash": entity.get("file_hash", ""),
                },
            })

        return RetrievalResult(
            hits=hits,
            query=query,
            collection=collection_name,
            degraded=False,
        )

    def delete_by_expr(self, collection_name: str, expr: str) -> bool:
        """按表达式删除文档。"""
        self._connect()
        if not utility.has_collection(collection_name, using=self.alias):
            return False
        col = Collection(collection_name, using=self.alias)
        col.delete(expr)
        col.flush()
        logger.info("documents_deleted", collection=collection_name, expr=expr)
        return True

    def get_collection_stats(self, collection_name: str) -> dict[str, Any]:
        """获取 Collection 统计信息。"""
        self._connect()
        if not utility.has_collection(collection_name, using=self.alias):
            return {"row_count": 0, "index_status": "not_found", "healthy": False}
        col = Collection(collection_name, using=self.alias)
        col.flush()
        row_count = col.num_entities
        indexes = col.indexes
        index_status = "built" if indexes else "none"
        return {
            "row_count": row_count,
            "index_status": index_status,
            "healthy": True,
        }

    def list_collections(self) -> list[str]:
        """列出所有 Collection。"""
        self._connect()
        return utility.list_collections(using=self.alias)

    def drop_collection(self, collection_name: str) -> bool:
        """删除 Collection。"""
        self._connect()
        if utility.has_collection(collection_name, using=self.alias):
            utility.drop_collection(collection_name, using=self.alias)
            logger.info("collection_dropped", name=collection_name)
            return True
        return False

    def health_check(self) -> dict[str, Any]:
        """健康检查。"""
        start = time.perf_counter()
        try:
            self._connect()
            utility.list_collections(using=self.alias)
            latency = int((time.perf_counter() - start) * 1000)
            return {"healthy": True, "latency_ms": latency}
        except Exception as exc:
            return {"healthy": False, "latency_ms": 0, "error": str(exc)}


def get_milvus_store() -> MilvusHybridStore:
    """返回 MilvusHybridStore 单例。"""
    global _store
    if _store is None:
        _store = MilvusHybridStore()
    return _store
