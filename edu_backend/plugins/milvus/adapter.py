"""Milvus 插件（生产级增强：健康检查 + 统计）。"""
from __future__ import annotations

import time
from typing import Any

from factory.registry import vector_store_registry
from interfaces.base_vector_store import BaseVectorStore
from observability.logger import get_logger
from vector_store.embeddings import get_embedder
from vector_store.milvus_client import MilvusHybridStore

logger = get_logger(__name__)


class MilvusAdapter(BaseVectorStore):
    """Milvus 适配器。

    生产级增强：
        - health_check：发送轻量级查询探测 Milvus 存活
        - get_stats：返回 Collection 行数和索引状态
    """

    def __init__(self, config: dict) -> None:
        self.config = config
        self.store = MilvusHybridStore(
            collection_name=config.get("collection_name", "edu_doc_hybrid_v1"),
            embedder=get_embedder(),
            uri=config.get("uri", "http://127.0.0.1:19530"),
            username=config.get("username"),
            password=config.get("password"),
        )

    def insert(self, documents, ids):
        return self.store.add_documents(documents, ids)

    def search(self, query, top_k, filters=None):
        result = self.store.search(query, k=top_k, filters=filters)
        return [
            {
                "content": hit.document.page_content,
                "score": hit.score,
                "metadata": hit.document.metadata,
            }
            for hit in result.hits
        ]

    def delete(self, ids):
        return self.store.delete_ids(ids)

    def health_check(self) -> dict[str, Any]:
        """探测 Milvus 连通性。"""
        start = time.perf_counter()
        try:
            from pymilvus import connections, utility

            conn = connections.get_connection_addr("default")
            if conn is None:
                connections.connect(
                    alias="default",
                    uri=self.config.get("uri", "http://127.0.0.1:19530"),
                )

            collections = utility.list_collections()
            latency = int((time.perf_counter() - start) * 1000)
            return {
                "healthy": True,
                "latency_ms": latency,
                "details": f"collections: {len(collections)}",
            }
        except Exception as exc:
            latency = int((time.perf_counter() - start) * 1000)
            return {
                "healthy": False,
                "latency_ms": latency,
                "details": str(exc),
            }

    def get_stats(self) -> dict[str, Any]:
        """获取 Collection 统计信息。"""
        try:
            from pymilvus import Collection, connections

            conn = connections.get_connection_addr("default")
            if conn is None:
                connections.connect(
                    alias="default",
                    uri=self.config.get("uri", "http://127.0.0.1:19530"),
                )

            coll = Collection(
                self.config.get("collection_name", "edu_doc_hybrid_v1")
            )
            coll.load()
            row_count = coll.num_entities

            return {
                "row_count": row_count,
                "index_status": "loaded",
                "collection_name": coll.name,
            }
        except Exception as exc:
            return {
                "row_count": 0,
                "index_status": f"error: {type(exc).__name__}",
                "collection_name": self.config.get("collection_name", ""),
            }


vector_store_registry.register(
    "milvus",
    MilvusAdapter,
    schema={
        "type": "object",
        "required": ["type", "uri", "collection_name"],
        "properties": {
            "type": {"type": "string"},
            "uri": {"type": "string"},
            "collection_name": {"type": "string"},
            "username": {"type": "string"},
            "password": {"type": "string"},
        },
    },
)