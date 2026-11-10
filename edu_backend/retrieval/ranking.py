"""检索排序与去重（生产级增强：内容级去重 + 负反馈惩罚）。"""
from __future__ import annotations

from typing import Any

from observability.logger import get_logger

logger = get_logger(__name__)


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """计算两段文本的 Jaccard 相似度（字符级 bigram）。"""
    def bigrams(text: str) -> set[str]:
        chars = text.strip()
        if len(chars) < 2:
            return {chars}
        return {chars[i:i + 2] for i in range(len(chars) - 1)}

    set_a = bigrams(text_a)
    set_b = bigrams(text_b)
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def rerank_hits(
    query: str,
    hits: list[dict[str, Any]],
    top_n: int = 5,
    batch_size: int = 32,
) -> list[dict[str, Any]]:
    """CrossEncoder Rerank（增强：分批处理）。

    入参：
        query：查询文本
        hits：待 Rerank 的 hit 列表
        top_n：返回 Top-N
        batch_size：分批大小（减少峰值内存）

    返回：
        Rerank 后的 hit 列表（按分数降序）
    """
    if not hits:
        return []

    from vector_store.reranker import get_reranker

    # 截断到合理数量
    candidates = hits[:top_n * 4]

    # 分批预测（reranker 失败时降级为原始排序）
    try:
        reranker = get_reranker()
        all_scores: list[float] = []
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i + batch_size]
            pairs = [[query, hit.get("text", "")] for hit in batch]
            scores = reranker.compute_score(pairs)
            if isinstance(scores, (int, float)):
                scores = [scores]
            all_scores.extend(float(s) for s in scores)

        for hit, score in zip(candidates, all_scores):
            hit["rerank_score"] = float(score)

        candidates.sort(key=lambda h: h["rerank_score"], reverse=True)
    except Exception as exc:
        logger.warning("rerank_failed_fallback", error=str(exc)[:200])
        for hit in candidates:
            hit["rerank_score"] = hit.get("score", 0.0)

    # 应用负反馈惩罚
    try:
        from retrieval.feedback_loop import FeedbackLoop
        feedback = FeedbackLoop()
        candidates = feedback.apply_penalties(candidates)
    except Exception as exc:
        logger.warning("feedback_penalty_failed", error=str(exc))

    return candidates[:top_n]


def merge_hits_by_document(
    hits: list[dict[str, Any]],
    jaccard_threshold: float = 0.85,
) -> list[dict[str, Any]]:
    """去重合并（增强：ID 去重 + 内容相似度去重）。

    入参：
        hits：待去重的 hit 列表
        jaccard_threshold：内容相似度阈值（超过则判定为重复）

    返回：
        去重后的 hit 列表
    """
    if not hits:
        return []

    seen_ids: set[str] = set()
    seen_texts: list[str] = []
    merged: list[dict[str, Any]] = []

    for hit in hits:
        chunk_id = hit.get("chunk_id", "")
        text = hit.get("text", "")

        # ID 去重
        if chunk_id and chunk_id in seen_ids:
            continue

        # 内容相似度去重
        is_duplicate = False
        for seen_text in seen_texts:
            sim = _jaccard_similarity(text, seen_text)
            if sim >= jaccard_threshold:
                logger.debug(
                    "content_dedup",
                    jaccard=sim,
                    threshold=jaccard_threshold,
                )
                is_duplicate = True
                break

        if not is_duplicate:
            if chunk_id:
                seen_ids.add(chunk_id)
            seen_texts.append(text)
            merged.append(hit)

    logger.info(
        "merge_complete",
        input_count=len(hits),
        output_count=len(merged),
        deduped=len(hits) - len(merged),
    )
    return merged