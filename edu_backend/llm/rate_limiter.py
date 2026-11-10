"""Agent LLM 并发限流：全局信号量防止突发调用拖垮上游限速。

Agent 编排中多个工具可能并发触发 LLM 调用，无上限会瞬间打满
DeepSeek 限速配额。本模块提供进程级 asyncio.Semaphore 单例，
所有 Agent 工具的 LLM 调用经 acquire 后执行。
"""
from __future__ import annotations

import asyncio

from config.settings import get_settings

_semaphore: asyncio.Semaphore | None = None


def get_llm_semaphore() -> asyncio.Semaphore:
    """返回全局 LLM 并发信号量单例。

    上限由 settings.agent_llm_concurrency 控制（默认 20）。
    在 Agent 工具中用法：
        async with get_llm_semaphore():
            return await llm.agenerate(messages)
    """
    global _semaphore
    if _semaphore is None:
        settings = get_settings()
        _semaphore = asyncio.Semaphore(settings.agent_llm_concurrency)
    return _semaphore
