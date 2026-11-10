"""BGE-M3 Embedding 模型加载与缓存。"""
from __future__ import annotations

from typing import Any

from config.settings import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)

_embedder: Any = None


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


def get_embedder() -> Any:
    """返回 BGE-M3 Embedding 模型单例。"""
    global _embedder
    if _embedder is None:
        settings = get_settings()
        from FlagEmbedding import BGEM3FlagModel

        device, use_fp16 = _detect_device()
        model_path = settings.embedding_model_path.replace("\\", "/")
        logger.info("loading_embedding_model", path=model_path, device=device, fp16=use_fp16)
        _embedder = BGEM3FlagModel(
            model_path,
            use_fp16=use_fp16,
            devices=device,
        )
        logger.info("embedding_model_loaded", device=device)
    return _embedder


def embed(texts: str | list[str]) -> dict[str, Any]:
    """生成文本的稠密 + 稀疏向量。"""
    model = get_embedder()
    if isinstance(texts, str):
        texts = [texts]
    return model.encode(
        texts,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )
