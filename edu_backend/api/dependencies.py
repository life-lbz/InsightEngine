"""API 依赖（生产级增强：Redis 分布式限流）。"""
from __future__ import annotations

import time
from typing import Any

import redis
from fastapi import HTTPException, status

from config.settings import get_settings

# 进程级 Redis 客户端单例
_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """返回 Redis 客户端单例。"""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(
            settings.redis_url,
            **settings.redis_pool_kwargs,
        )
    return _redis_client


def check_rate_limit(
    identifier: str,
    limit_per_minute: int | None = None,
) -> None:
    """Redis 滑动窗口限流（生产级增强版）。

    入参：
        identifier：限流标识（client_ip 或 user_id）
        limit_per_minute：每分钟允许的请求次数（默认使用配置）

    异常：
        HTTPException 429：超过限流阈值

    实现原理：
        使用 Redis Sorted Set：
        - score 为时间戳
        - member 为唯一请求 ID
        - 每次请求先清除窗口外的旧记录，再检查当前窗口内请求数
    """
    settings = get_settings()
    limit = limit_per_minute or settings.api_rate_limit_per_minute
    client = get_redis_client()

    key = f"ratelimit:{identifier}"
    now = time.time()
    window_start = now - 60  # 60 秒窗口

    pipe = client.pipeline()
    # 清除窗口外的旧记录
    pipe.zremrangebyscore(key, 0, window_start)
    # 添加当前请求
    pipe.zadd(key, {f"{now}:{id(identifier)}": now})
    # 统计窗口内请求数
    pipe.zcard(key)
    # 设置 Key 过期时间（防止无限增长）
    pipe.expire(key, 60)
    results = pipe.execute()

    current_count = results[2]
    if current_count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"请求过于频繁，请稍后重试（限制：{limit} 次/分钟）",
            headers={"Retry-After": "60"},
        )


def check_idempotency(
    idempotency_key: str,
    ttl: int = 300,
) -> str | None:
    """请求幂等检查。

    入参：
        idempotency_key：幂等键（从 Header 获取）
        ttl：幂等键过期时间（秒）

    返回：
        None 表示首次请求，非 None 表示已存在（返回缓存的响应）
    """
    if not idempotency_key:
        return None

    client = get_redis_client()
    key = f"idempotency:{idempotency_key}"

    # 尝试设置 Key（setnx 语义）
    if client.setnx(key, "processing"):
        client.expire(key, ttl)
        return None  # 首次请求
    else:
        # 已存在，返回缓存的响应
        cached = client.get(key)
        return cached if cached and cached != "processing" else None


def store_idempotent_response(
    idempotency_key: str,
    response: str,
    ttl: int = 300,
) -> None:
    """存储幂等响应。"""
    if not idempotency_key:
        return
    client = get_redis_client()
    client.setex(f"idempotency:{idempotency_key}", ttl, response)