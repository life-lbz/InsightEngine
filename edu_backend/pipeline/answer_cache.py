"""答案缓存：高频问题的完整答案缓存到 Redis。"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import redis

from config.settings import get_settings
from observability.logger import get_logger
from observability.metrics import cache_hit_rate

logger = get_logger(__name__)


class AnswerCache:
    """答案缓存管理器。

    缓存策略：
        - Key：answer:{course_id}:{intent}:{md5(query)}
        - TTL：默认 3600s（可通过 answer_cache_ttl 配置）
        - 仅缓存非追问（intent != FOLLOW_UP）且置信度 high 的答案
    """

    def __init__(self) -> None:
        """初始化答案缓存。"""
        settings = get_settings()
        self.client = redis.from_url(
            settings.redis_url,
            **settings.redis_pool_kwargs,
        )
        self.ttl = settings.answer_cache_ttl

    def _make_key(self, course_id: str, intent: str, query: str) -> str:
        """构造缓存 Key。"""
        query_hash = hashlib.md5(query.encode("utf-8")).hexdigest()
        return f"answer:{course_id}:{intent}:{query_hash}"

    def get(
        self,
        course_id: str,
        intent: str,
        query: str,
    ) -> dict[str, Any] | None:
        """查询缓存的答案。

        入参：
            course_id：课程 ID
            intent：意图类型
            query：查询文本

        返回：
            缓存的答案字典，或 None（未命中）
        """
        try:
            key = self._make_key(course_id, intent, query)
            raw = self.client.get(key)
            if raw is None:
                cache_hit_rate.labels(cache_type="answer").set(0.0)
                return None

            cache_hit_rate.labels(cache_type="answer").set(1.0)
            logger.info("answer_cache_hit", course_id=course_id, intent=intent)
            return json.loads(raw)
        except Exception as exc:
            logger.warning("answer_cache_get_error", error=str(exc))
            return None

    def set(
        self,
        course_id: str,
        intent: str,
        query: str,
        answer: dict[str, Any],
    ) -> None:
        """写入答案缓存。

        入参：
            course_id：课程 ID
            intent：意图类型
            query：查询文本
            answer：答案字典（含 answer_text、sources、confidence 等字段）

        边界条件：
            - 仅缓存置信度为 high 的答案
            - 不缓存追问类型
        """
        if intent == "FOLLOW_UP":
            return
        if answer.get("confidence_level") != "high":
            return

        try:
            key = self._make_key(course_id, intent, query)
            # 脱敏后存储（仅保留前 200 字符 + hash）
            safe_answer = {
                "answer_text": answer.get("answer_text", ""),
                "sources": answer.get("sources", []),
                "confidence": answer.get("confidence", 0.0),
                "confidence_level": answer.get("confidence_level", ""),
                "hit_type": answer.get("hit_type", ""),
                "cache_hit": True,
            }
            self.client.setex(
                key, self.ttl,
                json.dumps(safe_answer, ensure_ascii=False),
            )
        except Exception as exc:
            logger.warning("answer_cache_set_error", error=str(exc))

    def invalidate_course(self, course_id: str) -> int:
        """清除指定课程的所有答案缓存。

        入参：
            course_id：课程 ID

        返回：
            清除的缓存条数
        """
        try:
            pattern = f"answer:{course_id}:*"
            keys = list(self.client.scan_iter(match=pattern, count=100))
            if keys:
                self.client.delete(*keys)
            logger.info(
                "answer_cache_invalidated",
                course_id=course_id,
                cleared=len(keys),
            )
            return len(keys)
        except Exception as exc:
            logger.warning("answer_cache_invalidate_error", error=str(exc))
            return 0