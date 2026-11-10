"""统一检索器（生产级增强版）：并行三通道检索 + 通道级容错。"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from config.settings import get_settings
from config.rules import get_rule_config
from observability.logger import get_logger
from observability.metrics import retrieval_hit_count
from retrieval.course_scope import CourseScope
from retrieval.filters import build_course_expr, escape_expr_value
from retrieval.ranking import rerank_hits, merge_hits_by_document
from retrieval.strategy import build_retrieval_plan, RetrievalPlan
from retrieval.context_builder import build_final_context
from vector_store.results import RetrievalResult
from vector_store.milvus_resilient import ResilientMilvusStore

logger = get_logger(__name__)


class Retriever:
    """统一检索器：FAQ + 讲义 + 题库三通道并行检索。

    生产级增强：
        - 三通道并行执行（ThreadPoolExecutor）
        - 单通道异常隔离，不影响其他通道
        - Dense-Sparse 权重按意图动态调整
        - 检索日志写入 retrieval_logs 表
    """

    def __init__(self) -> None:
        """初始化检索器。"""
        self.settings = get_settings()
        self.store = ResilientMilvusStore()
        self.rules = get_rule_config()
        self.max_workers = 3

    def _get_dense_sparse_weights(self, intent: str) -> tuple[float, float]:
        """根据意图类型获取 Dense-Sparse 权重。

        入参：
            intent：意图类型（FAQ_QUERY/KNOWLEDGE_QUERY/QUESTION_PRACTICE）

        返回：
            (dense_weight, sparse_weight)
        """
        weight_map = {
            "FAQ_QUERY": (0.35, 0.65),          # FAQ：关键词强匹配，调高 Sparse
            "KNOWLEDGE_QUERY": (0.70, 0.30),     # 知识点：语义理解为主，调高 Dense
            "QUESTION_PRACTICE": (0.45, 0.55),   # 题库：精确术语匹配
            "FOLLOW_UP": (0.55, 0.45),           # 追问：均衡
        }
        return weight_map.get(intent, (0.55, 0.45))

    def _search_channel(
        self,
        query: str,
        collection_name: str,
        k: int,
        expr: str,
        dense_weight: float,
        sparse_weight: float,
        channel_name: str,
    ) -> RetrievalResult:
        """单通道检索（带异常隔离）。

        入参：
            query：查询文本
            collection_name：Collection 名称
            k：Top-K
            expr：过滤表达式
            dense_weight：Dense 权重
            sparse_weight：Sparse 权重
            channel_name：通道名称（用于日志）

        返回：
            RetrievalResult：检索结果，异常时返回空结果
        """
        try:
            result = self.store.search(
                query=query,
                collection_name=collection_name,
                k=k,
                expr=expr,
                dense_weight=dense_weight,
                sparse_weight=sparse_weight,
            )
            retrieval_hit_count.labels(channel=channel_name).observe(len(result.hits))
            return result
        except Exception as exc:
            logger.warning(
                "channel_search_failed",
                channel=channel_name,
                error=str(exc),
            )
            return RetrievalResult(
                hits=[],
                query=query,
                collection=collection_name,
                degraded=True,
                degraded_reason=f"channel_error: {channel_name}",
            )

    def search_all(
        self,
        query: str,
        scope: CourseScope,
        plan: RetrievalPlan,
        session_id: str = "",
        trace_id: str = "",
    ) -> dict[str, Any]:
        """并行三通道检索 + Rerank + 去重 + 上下文构建。

        入参：
            query：学员查询
            scope：课程范围
            plan：检索计划
            session_id：会话 ID
            trace_id：链路追踪 ID

        返回：
            {
                "context_docs": list[dict],      # 最终上下文文档
                "faq_hits": list,                 # FAQ 命中
                "doc_hits": list,                 # 讲义命中
                "question_hits": list,            # 题库命中
                "degraded": bool,                 # 是否降级
                "elapsed_ms": int,                # 总耗时
            }
        """
        start_time = time.perf_counter()

        # 构建过滤表达式
        expr = build_course_expr(scope)

        # 获取意图对应的权重
        dense_w, sparse_w = self._get_dense_sparse_weights(plan.intent)

        kb_version = scope.kb_version or self.settings.default_kb_version

        # 三通道并行检索
        tasks = {
            "faq": {
                "collection": f"edu_faq_hybrid_{kb_version}",
                "k": plan.faq_k,
            },
            "doc": {
                "collection": f"edu_doc_hybrid_{kb_version}",
                "k": plan.doc_k,
            },
            "question": {
                "collection": f"edu_question_hybrid_{kb_version}",
                "k": plan.question_k,
            },
        }

        results: dict[str, RetrievalResult] = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._search_channel,
                    query,
                    task["collection"],
                    task["k"],
                    expr,
                    dense_w,
                    sparse_w,
                    channel,
                ): channel
                for channel, task in tasks.items()
            }

            for future in as_completed(futures):
                channel = futures[future]
                try:
                    results[channel] = future.result()
                except Exception as exc:
                    logger.error(
                        "parallel_channel_error",
                        channel=channel,
                        error=str(exc),
                    )
                    results[channel] = RetrievalResult(
                        hits=[],
                        query=query,
                        collection=tasks[channel]["collection"],
                        degraded=True,
                        degraded_reason=f"parallel_error: {channel}",
                    )

        faq_result = results.get("faq", RetrievalResult(query=query, collection="", hits=[]))
        doc_result = results.get("doc", RetrievalResult(query=query, collection="", hits=[]))
        question_result = results.get("question", RetrievalResult(query=query, collection="", hits=[]))

        # 记录检索日志
        self._log_retrieval(query, plan.intent, results, session_id, trace_id)

        # 合并 + Rerank + 去重
        all_hits = list(faq_result.hits) + list(doc_result.hits) + list(question_result.hits)
        reranked = rerank_hits(query, all_hits, self.settings.rerank_top_n)
        merged = merge_hits_by_document(
            reranked,
            jaccard_threshold=self.settings.chunk_dedup_jaccard_threshold,
        )

        # 构建上下文
        context_docs = build_final_context(
            merged,
            plan,
            self.settings.max_context_doc_chars,
            self.settings.max_prompt_context_chars,
            self.settings.final_context_top_n,
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        any_degraded = any(r.degraded for r in results.values())

        logger.info(
            "retrieval_complete",
            intent=plan.intent,
            faq_hits=len(faq_result.hits),
            doc_hits=len(doc_result.hits),
            question_hits=len(question_result.hits),
            reranked=len(reranked),
            context_docs=len(context_docs),
            elapsed_ms=elapsed_ms,
            degraded=any_degraded,
        )

        return {
            "context_docs": context_docs,
            "faq_hits": faq_result.hits,
            "doc_hits": doc_result.hits,
            "question_hits": question_result.hits,
            "degraded": any_degraded,
            "elapsed_ms": elapsed_ms,
        }

    def _log_retrieval(
        self,
        query: str,
        intent: str,
        results: dict[str, RetrievalResult],
        session_id: str,
        trace_id: str,
    ) -> None:
        """写入检索日志到 MySQL（使用引擎单例）。"""
        try:
            from storage.db_engine import get_engine
            from sqlalchemy import text
            engine = get_engine()
            with engine.begin() as conn:
                for channel, result in results.items():
                    top_score = result.hits[0].get("score") if result.hits else None
                    conn.execute(
                        text(
                            "INSERT INTO retrieval_logs "
                            "(session_id, query, intent, channel, hit_count, top_score, elapsed_ms, trace_id) "
                            "VALUES (:sid, :q, :intent, :ch, :hc, :ts, :em, :tid)"
                        ),
                        {
                            "sid": session_id,
                            "q": query[:500],
                            "intent": intent,
                            "ch": channel,
                            "hc": len(result.hits),
                            "ts": top_score,
                            "em": None,
                            "tid": trace_id,
                        },
                    )
        except Exception as exc:
            logger.warning("retrieval_log_write_failed", error=str(exc))