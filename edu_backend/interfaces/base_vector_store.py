"""向量存储抽象接口（生产级增强：健康检查与统计）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.documents import Document


class BaseVectorStore(ABC):
    """所有向量存储实现必须继承。

    生产级增强：
        - health_check：供插件监护器定期探测存活
        - get_stats：返回行数/索引状态等运维指标
    """

    @abstractmethod
    def insert(self, documents: list[Document], ids: list[str]) -> list[str]:
        """插入文档。

        入参：
            documents：文档列表
            ids：文档 ID 列表

        返回：
            成功插入的 ID 列表
        """

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int,
        filters: dict | None = None,
    ) -> list[dict[str, Any]]:
        """检索 Top-K。

        入参：
            query：查询文本
            top_k：返回条数
            filters：过滤条件（course_id、doc_type 等）

        返回：
            [{"content": str, "score": float, "metadata": dict}, ...]
        """

    @abstractmethod
    def delete(self, ids: list[str]) -> bool:
        """删除文档。

        入参：
            ids：待删除文档 ID 列表

        返回：
            是否删除成功
        """

    def health_check(self) -> dict[str, Any]:
        """健康检查（子类可覆写）。

        返回：
            {"healthy": bool, "latency_ms": int, "details": str}
        """
        return {"healthy": True, "latency_ms": 0, "details": "not implemented"}

    def get_stats(self) -> dict[str, Any]:
        """获取存储统计信息（子类可覆写）。

        返回：
            {"row_count": int, "index_status": str, "collection_name": str}
        """
        return {"row_count": 0, "index_status": "unknown", "collection_name": ""}