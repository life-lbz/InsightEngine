"""Qdrant 模拟插件（生产级增强）。"""
from __future__ import annotations

from typing import Any

from factory.registry import vector_store_registry
from interfaces.base_vector_store import BaseVectorStore


class QdrantAdapter(BaseVectorStore):
    """教学用 Qdrant 模拟实现。

    生产环境应替换为真实的 qdrant-client 调用。
    """

    def __init__(self, config: dict) -> None:
        self.config = config
        self.collection_name = config.get("collection_name", "edu_qdrant")
        self.items: list[dict[str, Any]] = []

    def insert(self, documents, ids):
        self.items.extend(
            {
                "id": doc_id,
                "content": doc.page_content,
                "metadata": doc.metadata,
            }
            for doc_id, doc in zip(ids, documents)
        )
        return list(ids)

    def search(self, query, top_k, filters=None):
        results = self.items
        if filters:
            course_id = filters.get("course_id")
            if course_id:
                results = [
                    item for item in results
                    if item["metadata"].get("course_id") == course_id
                ]
        return [
            {
                "content": item["content"],
                "score": 0.5,
                "metadata": item["metadata"],
            }
            for item in results[:top_k]
        ]

    def delete(self, ids):
        id_set = set(ids)
        self.items = [item for item in self.items if item["id"] not in id_set]
        return True

    def health_check(self) -> dict[str, Any]:
        return {
            "healthy": True,
            "latency_ms": 0,
            "details": f"in-memory items: {len(self.items)}",
        }

    def get_stats(self) -> dict[str, Any]:
        return {
            "row_count": len(self.items),
            "index_status": "in-memory",
            "collection_name": self.collection_name,
        }


vector_store_registry.register(
    "qdrant",
    QdrantAdapter,
    schema={
        "type": "object",
        "required": ["type", "collection_name"],
        "properties": {
            "type": {"type": "string"},
            "uri": {"type": "string"},
            "collection_name": {"type": "string"},
        },
    },
)