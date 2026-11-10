"""查询改写/扩展：Multi-Query + HyDE。"""
from __future__ import annotations

from typing import Any

from config.settings import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)


class QueryRewriter:
    """查询改写器。

    策略：
        1. Multi-Query：让 LLM 生成 3 个查询变体，合并检索结果
        2. HyDE：让 LLM 生成假设性答案，用答案向量检索
        3. 关键词扩展：基于同义词和上下文补充关键词
    """

    def __init__(self) -> None:
        """初始化查询改写器。"""
        self.settings = get_settings()
        self._llm = None

    def _get_llm(self) -> Any:
        """延迟获取 LLM 降级链。"""
        if self._llm is None:
            from llm.resilient_client import get_resilient_llm
            self._llm = get_resilient_llm()
        return self._llm

    def rewrite(self, query: str, intent: str = "") -> list[str]:
        """查询改写主入口。

        入参：
            query：原始查询
            intent：意图类型

        返回：
            改写后的查询列表（包含原始查询）
        """
        queries = [query]

        try:
            multi_queries = self._multi_query(query, intent)
            queries.extend(multi_queries)
        except Exception as exc:
            logger.warning("multi_query_failed", error=str(exc)[:100])

        return list(dict.fromkeys(queries))

    def generate_hyde_answer(self, query: str, intent: str = "") -> str | None:
        """HyDE：生成假设性答案用于向量检索。

        入参：
            query：原始查询
            intent：意图类型

        返回：
            假设性答案文本，失败时返回 None
        """
        try:
            llm = self._get_llm()
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是一个教育问答助手。请根据问题直接生成一个简短的假设性答案（100-200字），"
                        "不需要完全正确，只需要包含可能相关的关键词和概念，用于辅助检索。"
                        "直接输出答案内容，不要加任何前缀说明。"
                    ),
                },
                {"role": "user", "content": query},
            ]
            result = llm.generate(messages)
            content = getattr(result, "content", str(result))
            logger.info("hyde_generated", query_len=len(query), answer_len=len(content))
            return content
        except Exception as exc:
            logger.warning("hyde_failed", error=str(exc)[:100])
            return None

    def _multi_query(self, query: str, intent: str = "") -> list[str]:
        """Multi-Query：让 LLM 生成查询变体。"""
        llm = self._get_llm()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个查询改写助手。请将用户的查询改写为 3 个不同表述的变体，"
                    "保持语义不变但使用不同的词汇和句式，以提高检索召回率。"
                    "每行输出一个改写后的查询，不要编号，不要其他说明。"
                ),
            },
            {"role": "user", "content": query},
        ]
        result = llm.generate(messages)
        content = getattr(result, "content", str(result))
        queries = [
            line.strip()
            for line in content.strip().split("\n")
            if line.strip() and line.strip() != query
        ]
        logger.info("multi_query_generated", original=query[:50], variants=len(queries))
        return queries[:3]


_query_rewriter: QueryRewriter | None = None


def get_query_rewriter() -> QueryRewriter:
    """返回查询改写器单例。"""
    global _query_rewriter
    if _query_rewriter is None:
        _query_rewriter = QueryRewriter()
    return _query_rewriter
