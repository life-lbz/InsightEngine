"""检索结果缓存：基于 Redis 的二级缓存。"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import redis

from config.settings import get_settings
from observability.logger import get_logger
from observability.metrics import cache_hit_rate

logger = get_logger(__name__)


class SearchCache:
    """检索结果 Redis 缓存。

    缓存策略：
        - Key：search:{collection}:{course_id}:{md5(query)}:{k}
        - TTL：默认 300s（可通过 search_cache_ttl 配置）
        - 命中时直接反序列化返回，跳过 Embedding + Milvus 查询
        - 知识库版本更新时批量清除
    """

    def __init__(self) -> None:
        """初始化缓存客户端。"""
        settings = get_settings()
        self.client = redis.from_url(
            settings.redis_url,
            **settings.redis_pool_kwargs,
        )
        self.ttl = settings.search_cache_ttl

    def _make_key(
        self,
        collection: str,
        course_id: str,
        query: str,
        k: int,
    ) -> str:
        """构造缓存 Key。

        入参：
            collection：Milvus Collection 名称
            course_id：课程 ID
            query：查询文本
            k：Top-K 值

        返回：
            Redis Key 字符串
        """
        query_hash = hashlib.md5(query.encode("utf-8")).hexdigest()
        return f"search:{collection}:{course_id}:{query_hash}:{k}"

    def get(
        self,
        collection: str,
        query: str,
        k: int,
        course_id: str = "",
    ) -> Any:
        """查询缓存。

        入参：
            collection：Collection 名称
            query：查询文本
            k：Top-K 值
            course_id：课程 ID

        返回：
            缓存的 RetrievalResult 对象，或 None（未命中）
        """
        try:
            key = self._make_key(collection, course_id, query, k)
            raw = self.client.get(key)
            if raw is None:
                cache_hit_rate.labels(cache_type="search").set(0.0)
                return None

            cache_hit_rate.labels(cache_type="search").set(1.0)
            data = json.loads(raw)

            # 反序列化为 RetrievalResult
            from vector_store.results import RetrievalResult
            return RetrievalResult.from_dict(data)
        except Exception as exc:
            logger.warning("cache_get_error", error=str(exc))
            return None

    def set(
        self,
        collection: str,
        query: str,
        k: int,
        result: Any,
        course_id: str = "",
    ) -> None:
        """写入缓存。

        入参：
            collection：Collection 名称
            query：查询文本
            k：Top-K 值
            result：检索结果对象
            course_id：课程 ID
        """
        try:
            key = self._make_key(collection, course_id, query, k)
            data = result.to_dict() if hasattr(result, "to_dict") else str(result)
            self.client.setex(key, self.ttl, json.dumps(data, ensure_ascii=False))
        except Exception as exc:
            logger.warning("cache_set_error", error=str(exc))

    def invalidate(self, course_id: str) -> int:
        """清除指定课程的所有检索缓存。

        入参：
            course_id：课程 ID

        返回：
            清除的缓存条数
        """
        try:
            pattern = f"search:*:{course_id}:*"
            keys = list(self.client.scan_iter(match=pattern, count=100))
            if keys:
                self.client.delete(*keys)
            logger.info("cache_invalidated", course_id=course_id, cleared=len(keys))
            return len(keys)
        except Exception as exc:
            logger.warning("cache_invalidate_error", error=str(exc))
            return 0

    def invalidate_all(self) -> int:
        """清除所有检索缓存。"""
        try:
            keys = list(self.client.scan_iter(match="search:*", count=100))
            if keys:
                self.client.delete(*keys)
            logger.info("cache_all_invalidated", cleared=len(keys))
            return len(keys)
        except Exception as exc:
            logger.warning("cache_invalidate_all_error", error=str(exc))
            return 0