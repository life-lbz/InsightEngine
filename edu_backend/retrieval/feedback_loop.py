"""负反馈调优闭环：学员踩的反馈自动影响后续检索权重。"""
from __future__ import annotations

import time
from typing import Any

import redis
from sqlalchemy import create_engine, text

from config.settings import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)

# 惩罚分值：每次被踩扣 0.05 分
PENALTY_PER_DISLIKE = -0.05
# 触发惩罚的最小被踩次数
MIN_DISLIKES_FOR_PENALTY = 3
# 惩罚过期天数（连续 7 天无负反馈则衰减归零）
PENALTY_EXPIRE_DAYS = 7


class FeedbackLoop:
    """负反馈驱动的检索调优器。

    工作原理：
        1. 定时任务每小时从 qa_feedback 表读取 rating=not_useful 的记录
        2. 分析负反馈对应的检索结果 sources_json 中的 chunk_id
        3. 同一 chunk_id 被踩 >= 3 次时，在 Redis 中维护惩罚分值
        4. 检索时在 rerank 后对每个 hit 的 score 减去对应惩罚分值
        5. 连续 7 天无负反馈则惩罚分值衰减归零
    """

    def __init__(self) -> None:
        """初始化反馈闭环管理器。"""
        settings = get_settings()
        self.redis_client = redis.from_url(
            settings.redis_url,
            **settings.redis_pool_kwargs,
        )
        self.engine = create_engine(
            settings.mysql_sync_uri,
            **settings.mysql_engine_kwargs,
        )

    def _penalty_key(self, chunk_id: str) -> str:
        """构造惩罚分值的 Redis Key。"""
        return f"chunk_penalty:{chunk_id}"

    def collect_feedback(self, hours: int = 1) -> dict[str, int]:
        """从 MySQL 收集指定时间范围内的负反馈。

        入参：
            hours：收集最近多少小时的反馈

        返回：
            {chunk_id: dislike_count} 被踩次数统计
        """
        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT sources_json, rating FROM qa_feedback "
                    "WHERE rating = 'not_useful' "
                    "AND created_at >= DATE_SUB(NOW(), INTERVAL :hours HOUR)"
                ),
                {"hours": hours},
            )
            chunk_dislikes: dict[str, int] = {}
            for row in result.fetchall():
                import json
                try:
                    sources = json.loads(row[0]) if row[0] else []
                    for src in sources:
                        chunk_id = src.get("chunk_id", "")
                        if chunk_id:
                            chunk_dislikes[chunk_id] = chunk_dislikes.get(chunk_id, 0) + 1
                except (json.JSONDecodeError, TypeError):
                    continue

        logger.info(
            "feedback_collected",
            hours=hours,
            chunk_count=len(chunk_dislikes),
        )
        return chunk_dislikes

    def update_penalties(self, chunk_dislikes: dict[str, int]) -> int:
        """更新 Redis 中的惩罚分值。

        入参：
            chunk_dislikes：{chunk_id: dislike_count}

        返回：
            更新了惩罚分值的 chunk 数量
        """
        updated = 0
        expire_seconds = PENALTY_EXPIRE_DAYS * 86400

        for chunk_id, dislike_count in chunk_dislikes.items():
            if dislike_count < MIN_DISLIKES_FOR_PENALTY:
                continue

            key = self._penalty_key(chunk_id)
            penalty = dislike_count * PENALTY_PER_DISLIKE
            self.redis_client.setex(key, expire_seconds, str(penalty))
            updated += 1

        logger.info(
            "penalties_updated",
            total_chunks=len(chunk_dislikes),
            penalized=updated,
        )
        return updated

    def get_penalty(self, chunk_id: str) -> float:
        """获取指定 chunk 的惩罚分值。

        入参：
            chunk_id：chunk ID

        返回：
            惩罚分值（0.0 表示无惩罚，负数表示需要降低排名）
        """
        key = self._penalty_key(chunk_id)
        raw = self.redis_client.get(key)
        if raw is None:
            return 0.0
        try:
            return float(raw)
        except (ValueError, TypeError):
            return 0.0

    def apply_penalties(
        self,
        hits: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """对检索结果应用惩罚分值。

        入参：
            hits：Rerank 后的 hit 列表，每个 hit 含 score 和 chunk_id

        返回：
            应用惩罚后的 hit 列表（按新分数降序排列）
        """
        for hit in hits:
            chunk_id = hit.get("chunk_id", "")
            if chunk_id:
                penalty = self.get_penalty(chunk_id)
                if penalty != 0.0:
                    # 基于 rerank_score（CrossEncoder 精排分数）调整，保留 rerank 效果
                    original_score = hit.get("rerank_score", hit.get("score", 0.0))
                    hit["rerank_score"] = original_score + penalty
                    hit["penalty_applied"] = penalty
                    logger.debug(
                        "penalty_applied",
                        chunk_id=chunk_id,
                        original=original_score,
                        penalty=penalty,
                        adjusted=hit["rerank_score"],
                    )

        # 重新排序（基于 rerank_score，保留 CrossEncoder 精排效果）
        hits.sort(key=lambda h: h.get("rerank_score", h.get("score", 0.0)), reverse=True)
        return hits

    def run_feedback_cycle(self) -> dict[str, int]:
        """执行一次反馈收集与惩罚更新周期。

        返回：
            {"collected": int, "penalized": int}
        """
        chunk_dislikes = self.collect_feedback(hours=1)
        penalized = self.update_penalties(chunk_dislikes)
        return {"collected": len(chunk_dislikes), "penalized": penalized}