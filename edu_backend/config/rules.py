"""规则配置：检索规则与阈值管理。"""
from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings


@dataclass
class RuleConfig:
    """检索规则配置。

    属性：
        min_score_threshold：最低检索分数阈值
        rerank_top_n：Rerank 返回 Top-N
        final_context_top_n：最终上下文文档数
        dedup_jaccard_threshold：去重 Jaccard 阈值
    """

    min_score_threshold: float = 0.2
    rerank_top_n: int = 5
    final_context_top_n: int = 4
    dedup_jaccard_threshold: float = 0.85


def get_rule_config() -> RuleConfig:
    """从 settings 构建规则配置单例。"""
    settings = get_settings()
    return RuleConfig(
        min_score_threshold=settings.rag_min_score_threshold,
        rerank_top_n=settings.rerank_top_n,
        final_context_top_n=settings.final_context_top_n,
        dedup_jaccard_threshold=settings.chunk_dedup_jaccard_threshold,
    )
