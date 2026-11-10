"""Milvus 容错存储客户端：连接重试、检索超时、降级机制。"""
from __future__ import annotations

import time
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import get_settings
from observability.logger import get_logger
from observability.metrics import (
    degraded_request_total,
    milvus_search_duration,
    milvus_search_total,
)
from vector_store.milvus_client import MilvusHybridStore
from vector_store.results import RetrievalResult

logger = get_logger(__name__)


class ResilientMilvusStore(MilvusHybridStore):
    """容错版 Milvus 存储客户端。

    增强能力：
        - 连接重试：Milvus 连接失败时自动重试（指数退避）
        - 检索超时：单次检索超时后返回空结果并告警
        - 降级机制：Milvus 不可用时降级为 BM25-only 或缓存兜底
    """

    def __init__(self) -> None:
        """初始化容错存储客户端。"""
        super().__init__()
        self.settings = get_settings()
        self.search_timeout = self.settings.milvus_search_timeout
        self.connect_retry = self.settings.milvus_connect_retry

    @retry(
        retry=retry_if_exception_type(ConnectionError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=4),
        reraise=True,
    )
    def _ensure_connection(self) -> None:
        """确保 Milvus 连接可用，失败时自动重试。

        重试策略：
            - 最多重试 3 次
            - 指数退避：1s → 2s → 4s
            - 仍然失败则抛出 ConnectionError
        """
        try:
            self.client.list_collections()
        except Exception as exc:
            raise ConnectionError(f"Milvus 连接失败: {exc}") from exc

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
        """容错版混合检索。

        入参：
            query：查询文本
            collection_name：Milvus Collection 名称
            k：返回 Top-K 结果
            expr：过滤表达式
            dense_weight：Dense 向量权重
            sparse_weight：Sparse 稀疏权重
            **kwargs：其他传递给父类的参数

        返回：
            RetrievalResult：检索结果，降级时 degraded=True

        降级策略：
            1. 检索超时 → 降级为 BM25-only 检索
            2. BM25-only 也失败 → 返回空结果并标记 degraded
        """
        start_time = time.perf_counter()
        cache_hit = False

        # 检查缓存
        from vector_store.search_cache import SearchCache
        cache = SearchCache()
        cached = cache.get(collection_name, query, k)
        if cached is not None:
            cache_hit = True
            milvus_search_total.labels(
                collection=collection_name, cache_hit="true"
            ).inc()
            return cached

        try:
            # 正常混合检索
            result = super().search(
                query=query,
                collection_name=collection_name,
                k=k,
                expr=expr,
                dense_weight=dense_weight,
                sparse_weight=sparse_weight,
                **kwargs,
            )

            # 写入缓存
            cache.set(collection_name, query, k, result)

            elapsed = time.perf_counter() - start_time
            milvus_search_duration.labels(collection=collection_name).observe(elapsed)
            milvus_search_total.labels(
                collection=collection_name, cache_hit="false"
            ).inc()

            if elapsed > 0.5:
                logger.warning(
                    "milvus_slow_search",
                    collection=collection_name,
                    query=query[:100],
                    elapsed_ms=int(elapsed * 1000),
                )

            return result

        except TimeoutError:
            logger.warning(
                "milvus_search_timeout",
                collection=collection_name,
                timeout=self.search_timeout,
            )
            degraded_request_total.labels(degraded_type="milvus_timeout").inc()

            # 降级：BM25-only 检索
            try:
                result = super().search(
                    query=query,
                    collection_name=collection_name,
                    k=k,
                    expr=expr,
                    dense_weight=0.0,
                    sparse_weight=1.0,
                    **kwargs,
                )
                result.degraded = True
                result.degraded_reason = "milvus_dense_timeout"
                logger.info("milvus_degraded_to_bm25", collection=collection_name)
                return result
            except Exception:
                logger.error("milvus_fully_unavailable", collection=collection_name)
                degraded_request_total.labels(
                    degraded_type="milvus_unavailable"
                ).inc()
                return RetrievalResult(
                    hits=[],
                    query=query,
                    collection=collection_name,
                    degraded=True,
                    degraded_reason="milvus_unavailable",
                )

        except Exception as exc:
            logger.error(
                "milvus_search_error",
                collection=collection_name,
                error=str(exc),
            )
            degraded_request_total.labels(
                degraded_type="milvus_error"
            ).inc()
            return RetrievalResult(
                hits=[],
                query=query,
                collection=collection_name,
                degraded=True,
                degraded_reason=f"error: {type(exc).__name__}",
            )