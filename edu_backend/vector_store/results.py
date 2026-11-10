"""检索结果数据结构：统一封装向量检索返回。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievalResult:
    """混合检索结果。

    属性：
        hits：命中结果列表，每项 {"content", "score", "metadata"}
        query：原始查询文本
        collection：检索的 Collection 名称
        degraded：是否降级（超时/错误/BM25-only）
        degraded_reason：降级原因
    """

    hits: list[dict[str, Any]] = field(default_factory=list)
    query: str = ""
    collection: str = ""
    degraded: bool = False
    degraded_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "query": self.query,
            "collection": self.collection,
            "degraded": self.degraded,
            "degraded_reason": self.degraded_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetrievalResult:
        return cls(
            hits=data.get("hits", []),
            query=data.get("query", ""),
            collection=data.get("collection", ""),
            degraded=data.get("degraded", False),
            degraded_reason=data.get("degraded_reason"),
        )

    @property
    def top_score(self) -> float:
        if not self.hits:
            return 0.0
        return self.hits[0].get("score", 0.0)

    @property
    def hit_count(self) -> int:
        return len(self.hits)
