"""上下文构建器：将检索结果组装为 LLM 可用的上下文。"""
from __future__ import annotations

from typing import Any

from observability.logger import get_logger

logger = get_logger(__name__)


def build_final_context(
    merged_hits: list[dict[str, Any]],
    plan: Any,
    max_doc_chars: int = 1600,
    max_prompt_chars: int = 6000,
    top_n: int = 4,
) -> list[dict[str, Any]]:
    """将 Rerank + 去重后的 hits 构建为最终上下文文档列表。

    入参：
        merged_hits：Rerank + 去重后的 hit 列表
        plan：检索计划（RetrievalPlan）
        max_doc_chars：单个文档最大字符数
        max_prompt_chars：总上下文最大字符数
        top_n：最终返回的文档数

    返回：
        list[dict]：每个 dict 包含 text、source、score、chunk_id 等字段
    """
    if not merged_hits:
        return []

    context_docs: list[dict[str, Any]] = []
    total_chars = 0

    for hit in merged_hits[:top_n]:
        text = hit.get("text", "") or hit.get("content", "")

        if len(text) > max_doc_chars:
            text = text[:max_doc_chars] + "..."

        if total_chars + len(text) > max_prompt_chars:
            remaining = max_prompt_chars - total_chars
            if remaining > 100:
                text = text[:remaining] + "..."
            else:
                break

        doc = {
            "text": text,
            "source": hit.get("source", hit.get("metadata", {}).get("source", "unknown")),
            "score": hit.get("rerank_score", hit.get("score", 0.0)),
            "chunk_id": hit.get("chunk_id", ""),
            "channel": hit.get("channel", ""),
            "metadata": hit.get("metadata", {}),
        }
        context_docs.append(doc)
        total_chars += len(text)

    logger.info(
        "context_built",
        input_hits=len(merged_hits),
        output_docs=len(context_docs),
        total_chars=total_chars,
        intent=getattr(plan, "intent", "unknown"),
    )

    return context_docs
