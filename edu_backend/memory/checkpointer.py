"""LangGraph Checkpointer：开发期用 MemorySaver，生产用 RedisSaver。

LangGraph 的 checkpointer 用于持久化 Agent 状态（消息历史、中间结果），
实现多轮对话记忆与中断恢复。开发期使用进程内存版 MemorySaver；
生产环境使用 RedisSaver（需安装 langgraph-checkpoint-redis），
支持多进程共享状态与重启恢复，对外接口保持不变。
"""
from __future__ import annotations

from config.settings import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)

_checkpointer = None


def get_checkpointer():
    """返回 checkpointer 单例，根据环境自动选择后端。

    生产环境（APP_ENV=prod/staging）使用 RedisSaver，需设置 REDIS_URL
    并安装 langgraph-checkpoint-redis。开发/测试环境使用 MemorySaver。

    与 memory/history.py 职责分离：
    history.py 负责业务侧聊天记录落库（chat_history 表），
    checkpointer 负责 LangGraph 运行时状态快照（用于中断恢复）。
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    settings = get_settings()
    use_redis = settings.app_env in ("prod", "staging")

    if use_redis:
        try:
            from langgraph.checkpoint.redis import RedisSaver

            _checkpointer = RedisSaver.from_conn_string(settings.redis_url)
            logger.info("agent_checkpointer_initialized", backend="redis")
        except ImportError:
            logger.warning(
                "agent_checkpointer_redis_unavailable",
                reason="langgraph-checkpoint-redis not installed, falling back to memory",
            )
            from langgraph.checkpoint.memory import MemorySaver

            _checkpointer = MemorySaver()
            logger.info("agent_checkpointer_initialized", backend="memory")
    else:
        from langgraph.checkpoint.memory import MemorySaver

        _checkpointer = MemorySaver()
        logger.info("agent_checkpointer_initialized", backend="memory")

    return _checkpointer
