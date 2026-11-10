"""BGE-Reranker 模型加载与缓存。"""
from __future__ import annotations

from typing import Any

from config.settings import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)

_reranker: Any = None


def _detect_device() -> tuple[str, bool]:
    """检测可用设备，cuDNN 不可用时降级到 CPU。"""
    try:
        import torch

        if not torch.cuda.is_available():
            return "cpu", False
        _ = torch.cuda.cudnn_version()
        return "cuda", True
    except Exception:
        return "cpu", False


def get_reranker() -> Any:
    """返回 BGE-Reranker 模型单例。"""
    global _reranker
    if _reranker is None:
        settings = get_settings()
        from FlagEmbedding import FlagReranker

        device, use_fp16 = _detect_device()
        model_path = settings.reranker_model_path.replace("\\", "/")
        logger.info("loading_reranker_model", path=model_path, device=device, fp16=use_fp16)
        _reranker = FlagReranker(
            model_path,
            use_fp16=use_fp16,
            devices=device,
        )
        logger.info("reranker_model_loaded", device=device)
    return _reranker


def rerank(
    query: str,
    documents: list[str],
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """对文档列表进行重排序。"""
    model = get_reranker()
    pairs = [[query, doc] for doc in documents]
    scores = model.compute_score(pairs)
    if isinstance(scores, float):
        scores = [scores]
    ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
    if top_n:
        ranked = ranked[:top_n]
    return [{"content": doc, "score": float(score)} for doc, score in ranked]
