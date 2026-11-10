"""核心 RAG 引擎（生产级增强：三通道检索 + 意图识别 + 查询改写 + Prompt 模板管理）。"""
from __future__ import annotations

import time
from typing import Any

from interfaces.base_llm import BaseLLM
from interfaces.base_vector_store import BaseVectorStore
from config.settings import get_settings
from observability.logger import get_logger
from observability.metrics import rag_request_duration

logger = get_logger(__name__)


class RagEngine:
    """组合 VectorStore 和 LLM 的核心引擎。

    生产级增强：
        - 检索失败时返回友好兜底，不抛异常给调用方
        - LLM 生成失败时返回标准降级提示
        - 全流程指标埋点（延迟、成功率）
    """

    def __init__(
        self,
        vector_store: BaseVectorStore,
        llm: BaseLLM,
    ) -> None:
        self.vector_store = vector_store
        self.llm = llm

    def answer(
        self,
        question: str,
        top_k: int = 5,
        filters: dict | None = None,
    ) -> dict[str, Any]:
        """检索并生成答案。

        入参：
            question：学员问题
            top_k：检索条数
            filters：过滤条件（course_id 等）

        返回：
            {
                "answer": str,
                "sources": list[dict],
                "confidence": float,
                "degraded": bool,
                "error": str | None,
            }
        """
        start = time.perf_counter()
        degraded = False
        error: str | None = None

        # 1. 检索
        try:
            hits = self.vector_store.search(question, top_k=top_k, filters=filters)
            if not hits:
                degraded = True
                error = "no_results"
        except Exception as exc:
            logger.error("rag_search_failed", error=str(exc))
            hits = []
            degraded = True
            error = f"search_error: {type(exc).__name__}"

        # 2. 构建上下文
        if hits:
            context = "\n\n".join(
                f"[{i + 1}] {hit.get('content', '')}"
                for i, hit in enumerate(hits)
            )
        else:
            context = "（未检索到相关内容）"

        # 3. 生成
        try:
            from pipeline.prompt_manager import get_prompt, get_fallback_message
            system_prompt, user_prompt = get_prompt(
                "rag_answer",
                context=context,
                question=question,
            )
            answer = self.llm.generate(system_prompt, user_prompt)
        except Exception as exc:
            logger.error("rag_generate_failed", error=str(exc))
            try:
                from pipeline.prompt_manager import get_fallback_message
                answer = get_fallback_message()
            except Exception:
                answer = (
                    "抱歉，回答生成服务暂时不可用，请稍后重试。"
                    "您也可以尝试换个方式提问或联系课程助教。"
                )
            degraded = True
            error = f"generate_error: {type(exc).__name__}"

        # 4. 指标埋点
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        rag_request_duration.labels(
            course_id="unknown",
            intent="unknown",
            hit_type="degraded" if degraded else "ok",
        ).observe(elapsed_ms / 1000)

        # 5. 置信度
        confidence = 0.9 if hits and not degraded else 0.3

        return {
            "answer": answer,
            "sources": hits,
            "confidence": confidence,
            "degraded": degraded,
            "error": error,
        }


def _resolve_course_kb_version(course_id: str) -> str:
    """按课程 ID 解析其绑定的知识库版本（active_kb_version）。

    课程不存在、未绑定或查询失败时，回落到默认版本，保证检索链路不中断。
    """
    settings = get_settings()
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(settings.mysql_sync_uri)
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT active_kb_version FROM courses "
                        "WHERE course_id = :ci AND is_deleted = 0"
                    ),
                    {"ci": course_id},
                ).fetchone()
            if row and row[0]:
                return str(row[0])
        finally:
            engine.dispose()
    except Exception as exc:
        logger.warning(
            "resolve_course_kb_version_failed",
            course_id=course_id,
            error=str(exc)[:100],
        )
    return settings.default_kb_version


class RagPipeline:
    """完整 RAG 管道：意图识别 → 查询改写 → 三通道检索 → Prompt 模板生成。

    生产级增强：
        - 意图识别（关键词 + 可选 BERT）
        - Multi-Query + HyDE 查询扩展
        - 三通道并行检索（FAQ/讲义/题库）
        - Prompt 模板外部化管理
        - 全链路降级容错
    """

    def __init__(self) -> None:
        """初始化 RAG 管道。"""
        self._retriever = None
        self._intent_classifier = None
        self._query_rewriter = None
        self._llm = None

    @property
    def retriever(self) -> Any:
        """延迟初始化 Retriever。"""
        if self._retriever is None:
            from retrieval.retriever import Retriever
            self._retriever = Retriever()
        return self._retriever

    @property
    def intent_classifier(self) -> Any:
        """延迟初始化意图分类器。"""
        if self._intent_classifier is None:
            from retrieval.intent_classifier import get_intent_classifier
            self._intent_classifier = get_intent_classifier()
        return self._intent_classifier

    @property
    def query_rewriter(self) -> Any:
        """延迟初始化查询改写器。"""
        if self._query_rewriter is None:
            from retrieval.query_rewriter import get_query_rewriter
            self._query_rewriter = get_query_rewriter()
        return self._query_rewriter

    @property
    def llm(self) -> Any:
        """延迟初始化 LLM 降级链。"""
        if self._llm is None:
            from llm.resilient_client import get_resilient_llm
            self._llm = get_resilient_llm()
        return self._llm

    async def answer(
        self,
        question: str,
        course_id: str = "",
        session_id: str = "",
        history: list[dict] | None = None,
    ) -> dict[str, Any]:
        """完整 RAG 管道：意图识别 → 查询改写 → 三通道检索 → 生成。

        入参：
            question：学员问题
            course_id：课程 ID
            session_id：会话 ID
            history：对话历史

        返回：
            {
                "answer": str,
                "sources": list[dict],
                "confidence": float,
                "confidence_level": str,
                "degraded": bool,
                "intent": str,
                "error": str | None,
            }
        """
        start = time.perf_counter()
        degraded = False
        error: str | None = None

        # 1. 意图识别
        try:
            intent = self.intent_classifier.classify(question, history)
            logger.info("intent_classified", intent=intent, query=question[:100])
        except Exception as exc:
            logger.warning("intent_classify_failed", error=str(exc)[:100])
            intent = "KNOWLEDGE_QUERY"

        # 2. 查询改写
        try:
            queries = self.query_rewriter.rewrite(question, intent)
            hyde_answer = self.query_rewriter.generate_hyde_answer(question, intent)
        except Exception as exc:
            logger.warning("query_rewrite_failed", error=str(exc)[:100])
            queries = [question]
            hyde_answer = None

        # 3. 三通道检索
        context_docs: list[dict[str, Any]] = []
        all_sources: list[dict[str, Any]] = []
        try:
            from retrieval.course_scope import CourseScope
            from retrieval.strategy import build_retrieval_plan

            resolved_course_id = course_id or get_settings().default_course_id
            kb_version = _resolve_course_kb_version(resolved_course_id)
            scope = CourseScope(course_id=resolved_course_id, kb_version=kb_version)
            plan = build_retrieval_plan(intent)

            retrieval_query = hyde_answer or queries[0]
            result = self.retriever.search_all(
                query=retrieval_query,
                scope=scope,
                plan=plan,
                session_id=session_id,
                trace_id=session_id,
            )
            context_docs = result.get("context_docs", [])
            all_sources = (
                result.get("faq_hits", [])[:3]
                + result.get("doc_hits", [])[:3]
                + result.get("question_hits", [])[:3]
            )
            if result.get("degraded"):
                degraded = True

            if not context_docs and queries[0] != retrieval_query:
                result = self.retriever.search_all(
                    query=queries[0],
                    scope=scope,
                    plan=plan,
                    session_id=session_id,
                    trace_id=session_id,
                )
                context_docs = result.get("context_docs", [])
                all_sources = (
                    result.get("faq_hits", [])[:3]
                    + result.get("doc_hits", [])[:3]
                    + result.get("question_hits", [])[:3]
                )

            if not context_docs:
                degraded = True
                error = "no_results"

        except Exception as exc:
            logger.error("retrieval_failed", error=str(exc))
            degraded = True
            error = f"retrieval_error: {type(exc).__name__}"

        # 4. 构建上下文文本
        if context_docs:
            context = "\n\n".join(
                f"[{i + 1}] {doc.get('text', '')}"
                for i, doc in enumerate(context_docs)
            )
        else:
            context = "（未检索到相关内容）"

        # 5. LLM 生成（使用外部化 Prompt 模板）
        try:
            from pipeline.prompt_manager import get_prompt, get_fallback_message
            system_prompt, user_prompt = get_prompt(
                "rag_answer",
                context=context,
                question=question,
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            llm_result = self.llm.generate(messages)
            answer = getattr(llm_result, "content", str(llm_result))
        except Exception as exc:
            logger.error("llm_generate_failed", error=str(exc))
            try:
                from pipeline.prompt_manager import get_fallback_message
                answer = get_fallback_message()
            except Exception:
                answer = "抱歉，回答生成服务暂时不可用，请稍后重试。"
            degraded = True
            error = f"generate_error: {type(exc).__name__}"

        # 6. 置信度评估
        if context_docs and not degraded:
            top_score = context_docs[0].get("score", 0.0) if context_docs else 0.0
            if top_score >= 0.8:
                confidence = 0.9
                confidence_level = "high"
            elif top_score >= 0.5:
                confidence = 0.7
                confidence_level = "medium"
            else:
                confidence = 0.5
                confidence_level = "low"
        else:
            confidence = 0.3
            confidence_level = "low"

        # 7. 指标埋点
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        rag_request_duration.labels(
            course_id=course_id or "unknown",
            intent=intent,
            hit_type="degraded" if degraded else "ok",
        ).observe(elapsed_ms / 1000)

        logger.info(
            "rag_pipeline_complete",
            intent=intent,
            query_count=len(queries),
            context_docs=len(context_docs),
            confidence=confidence,
            elapsed_ms=elapsed_ms,
            degraded=degraded,
        )

        return {
            "answer": answer,
            "sources": all_sources,
            "confidence": confidence,
            "confidence_level": confidence_level,
            "degraded": degraded,
            "intent": intent,
            "error": error,
        }


_pipeline: RagPipeline | None = None


def get_rag_pipeline() -> RagPipeline:
    """返回 RAG 管道单例。"""
    global _pipeline
    if _pipeline is None:
        _pipeline = RagPipeline()
    return _pipeline
