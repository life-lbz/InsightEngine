"""置信度校准器：基于实际反馈数据动态调整置信度参数。"""
from __future__ import annotations

import json
from typing import Any

import redis
from sqlalchemy import create_engine, text

from config.settings import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)

# 校准 Redis Key
CALIBRATION_KEY = "confidence:calibration"

# 默认权重系数（初始值，会被校准结果覆盖）
DEFAULT_WEIGHTS: dict[str, float] = {
    "faq_exact_match": 0.95,
    "faq_high_score": 0.85,
    "rag_high_score": 0.82,
    "rag_medium_score": 0.65,
    "question_exact_match": 0.90,
    "low_score": 0.40,
    "no_hits": 0.20,
}


class ConfidenceCalibrator:
    """置信度校准器。

    工作原理：
        1. 每日定时任务从 qa_feedback 表统计各 hit_type 的实际采纳率
        2. 与当前权重系数的预测值比对
        3. 偏差 > 0.1 时自动调整权重系数
        4. 调整后的参数写入 Redis 供运行时读取
    """

    def __init__(self) -> None:
        """初始化校准器。"""
        settings = get_settings()
        self.redis_client = redis.from_url(
            settings.redis_url,
            **settings.redis_pool_kwargs,
        )
        self.engine = create_engine(
            settings.mysql_sync_uri,
            **settings.mysql_engine_kwargs,
        )

    def get_current_weights(self) -> dict[str, float]:
        """获取当前权重系数（优先从 Redis 读取）。

        返回：
            各 hit_type 的权重系数字典
        """
        raw = self.redis_client.get(CALIBRATION_KEY)
        if raw:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        return DEFAULT_WEIGHTS.copy()

    def calculate_adoption_rates(self, days: int = 7) -> dict[str, float]:
        """统计各 hit_type 的实际采纳率。

        入参：
            days：统计最近多少天的数据

        返回：
            {hit_type: adoption_rate} 采纳率（0.0~1.0）
        """
        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT
                        sources_json,
                        rating
                    FROM qa_feedback
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
                        AND sources_json IS NOT NULL
                    """
                ),
                {"days": days},
            )

            # sources_json 是 JSON 数组，形如 [{"chunk_id": "...", "hit_type": "faq_exact_match", ...}]
            # 在 Python 层解析以兼容 MySQL 5.7（不支持 JSON_TABLE）
            stats: dict[str, dict[str, int]] = {}
            for row in result.fetchall():
                sources_json = row[0]
                rating = row[1]
                try:
                    sources = json.loads(sources_json) if isinstance(sources_json, str) else sources_json
                    if not isinstance(sources, list):
                        sources = [sources] if sources else []
                except (json.JSONDecodeError, TypeError):
                    continue
                for src in sources:
                    hit_type = src.get("hit_type", "unknown") if isinstance(src, dict) else "unknown"
                    if hit_type not in stats:
                        stats[hit_type] = {"useful": 0, "total": 0}
                    stats[hit_type]["total"] += 1
                    if rating == "useful":
                        stats[hit_type]["useful"] += 1

            rates: dict[str, float] = {}
            for hit_type, counts in stats.items():
                total = counts["total"] or 1
                rates[hit_type] = counts["useful"] / total if total > 0 else 0.0

        return rates

    def calibrate(self) -> dict[str, Any]:
        """执行一次校准周期。

        返回：
            {
                "previous_weights": dict,
                "adoption_rates": dict,
                "adjusted": dict,
                "changes": list[str],
            }
        """
        current_weights = self.get_current_weights()
        adoption_rates = self.calculate_adoption_rates(days=7)

        adjusted = current_weights.copy()
        changes: list[str] = []

        for hit_type, actual_rate in adoption_rates.items():
            if hit_type not in current_weights:
                continue

            predicted = current_weights[hit_type]
            diff = abs(predicted - actual_rate)

            if diff > 0.1:
                # 向实际采纳率方向调整（取加权平均，避免剧烈变动）
                new_weight = predicted * 0.7 + actual_rate * 0.3
                adjusted[hit_type] = round(new_weight, 4)
                changes.append(
                    f"{hit_type}: {predicted:.4f} -> {adjusted[hit_type]:.4f} "
                    f"(actual: {actual_rate:.4f}, diff: {diff:.4f})"
                )

        if changes:
            self.redis_client.set(
                CALIBRATION_KEY,
                json.dumps(adjusted, ensure_ascii=False),
            )
            logger.info(
                "confidence_calibrated",
                changes_count=len(changes),
                changes=changes,
            )
        else:
            logger.info("confidence_calibration_no_change")

        return {
            "previous_weights": current_weights,
            "adoption_rates": adoption_rates,
            "adjusted": adjusted,
            "changes": changes,
        }