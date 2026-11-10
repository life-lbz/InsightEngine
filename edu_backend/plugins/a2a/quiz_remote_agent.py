"""A2A 远端出题 Agent：可独立部署的出题服务。

作为 A2A 远端 Agent 示范，供其他系统通过 A2A 协议调用出题能力。
落地前需按当时 a2a-sdk 校准 AgentCard 与 task 状态机字段。
"""
from __future__ import annotations

from observability.logger import get_logger

logger = get_logger(__name__)


async def build_quiz_remote_agent():
    """构建可独立部署的出题 A2A Agent（骨架）。"""
    try:
        from a2a.server import AgentCard, AgentSkill
    except Exception as exc:
        logger.warning("a2a_sdk_unavailable", error=str(exc)[:100])
        return None

    skill = AgentSkill(
        id="generate_quiz",
        name="出题",
        description="按知识点生成练习题",
        tags=["education", "quiz"],
    )
    card = AgentCard(
        name="Quiz Remote Agent",
        description="远端出题 Agent",
        url="http://127.0.0.1:8090",
        version="0.1.0",
        skills=[skill],
    )
    return card
