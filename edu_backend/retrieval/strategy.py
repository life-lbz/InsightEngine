"""检索策略编排：根据意图生成检索计划。"""
from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings


@dataclass
class RetrievalPlan:
    """检索计划：按意图分配各通道 Top-K 与策略。

    属性：
        intent：意图类型（FAQ_QUERY/KNOWLEDGE_QUERY/QUESTION_PRACTICE/FOLLOW_UP）
        faq_k：FAQ 通道 Top-K
        doc_k：讲义通道 Top-K
        question_k：题库通道 Top-K
        use_rerank：是否启用 Rerank
        use_cache：是否启用检索缓存
    """

    intent: str
    faq_k: int = 20
    doc_k: int = 20
    question_k: int = 20
    use_rerank: bool = True
    use_cache: bool = True


# 意图 → 各通道 Top-K 分配
INTENT_K_MAP: dict[str, dict[str, int]] = {
    "FAQ_QUERY": {"faq_k": 30, "doc_k": 5, "question_k": 5},
    "KNOWLEDGE_QUERY": {"faq_k": 10, "doc_k": 30, "question_k": 10},
    "QUESTION_PRACTICE": {"faq_k": 5, "doc_k": 10, "question_k": 30},
    "FOLLOW_UP": {"faq_k": 15, "doc_k": 15, "question_k": 10},
}


def build_retrieval_plan(intent: str) -> RetrievalPlan:
    """根据意图类型构建检索计划。

    入参：
        intent：意图类型

    返回：
        RetrievalPlan：包含各通道 Top-K 和策略开关
    """
    settings = get_settings()
    k_config = INTENT_K_MAP.get(intent, INTENT_K_MAP["KNOWLEDGE_QUERY"])

    return RetrievalPlan(
        intent=intent,
        faq_k=k_config.get("faq_k", settings.faq_top_k),
        doc_k=k_config.get("doc_k", settings.doc_top_k),
        question_k=k_config.get("question_k", settings.question_top_k),
        use_rerank=True,
        use_cache=True,
    )
