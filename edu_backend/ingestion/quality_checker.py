"""数据质量评分器：入库前检测 chunk 质量，标记劣质数据。"""
from __future__ import annotations

from dataclasses import dataclass

from observability.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ChunkQualityResult:
    """chunk 质量评分结果。

    属性：
        quality_score：质量分（0.0~1.0，0 表示不合格不索引）
        reason：评分理由
    """

    quality_score: float
    reason: str


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """计算两段文本的 Jaccard 相似度（基于字符级 bigram）。

    入参：
        text_a：文本 A
        text_b：文本 B

    返回：
        Jaccard 相似度（0.0~1.0）
    """
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


class ChunkQualityChecker:
    """chunk 质量检查器。

    检查项：
        - 内容长度 >= min_chars
        - 非纯符号/空白
        - 与同文件其他 chunk 的重复度 < dedup_threshold
    """

    def __init__(
        self,
        min_chars: int = 20,
        dedup_jaccard_threshold: float = 0.85,
    ) -> None:
        """初始化质量检查器。

        入参：
            min_chars：最小字符数
            dedup_jaccard_threshold：重复度阈值（超过则标记为低质量）
        """
        self.min_chars = min_chars
        self.dedup_jaccard_threshold = dedup_jaccard_threshold

    def check_chunk(self, text: str) -> ChunkQualityResult:
        """检查单个 chunk 质量。

        入参：
            text：chunk 文本内容

        返回：
            ChunkQualityResult：质量评分结果
        """
        stripped = text.strip()

        # 空内容
        if len(stripped) == 0:
            return ChunkQualityResult(0.0, "内容为空")

        # 过短
        if len(stripped) < self.min_chars:
            return ChunkQualityResult(0.0, f"内容过短（{len(stripped)} < {self.min_chars}）")

        # 纯符号
        if not any(c.isalnum() for c in stripped):
            return ChunkQualityResult(0.0, "内容为纯符号/空白")

        # 基础分 1.0
        return ChunkQualityResult(1.0, "通过质量检查")

    def check_batch(
        self,
        chunks: list[dict[str, str]],
        content_key: str = "text",
    ) -> list[dict[str, Any]]:
        """批量检查 chunk 质量，标记重复 chunk。

        入参：
            chunks：chunk 字典列表
            content_key：内容字段名

        返回：
            添加了 quality_score 字段的 chunk 列表
        """
        from typing import Any

        results: list[dict[str, Any]] = []
        seen_texts: list[str] = []

        for chunk in chunks:
            text = chunk.get(content_key, "")
            qr = self.check_chunk(text)

            if qr.quality_score > 0:
                # 检查与已有 chunk 的重复度
                for seen in seen_texts:
                    sim = _jaccard_similarity(text, seen)
                    if sim >= self.dedup_jaccard_threshold:
                        qr = ChunkQualityResult(
                            0.0,
                            f"与已有 chunk 重复（Jaccard={sim:.2f} >= {self.dedup_jaccard_threshold}）",
                        )
                        break

            chunk_with_quality = dict(chunk)
            chunk_with_quality["quality_score"] = qr.quality_score
            chunk_with_quality["quality_reason"] = qr.reason

            if qr.quality_score > 0:
                seen_texts.append(text)

            results.append(chunk_with_quality)

        # 统计
        total = len(results)
        qualified = sum(1 for c in results if c["quality_score"] > 0)
        logger.info(
            "chunk_quality_check_complete",
            total=total,
            qualified=qualified,
            rejected=total - qualified,
        )

        return results