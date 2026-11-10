"""A2A 远端 Agent 客户端：与远端 Agent 通信。

A2A 协议（agent-to-agent）用于跨进程/跨部署 Agent 协作，
与 MCP 互补：MCP 是 agent-to-tool，A2A 是 agent-to-agent。
SDK 版本以官方为准，此处为骨架，落地前需按当时 a2a-sdk 联调。
"""
from __future__ import annotations

from observability.logger import get_logger

logger = get_logger(__name__)


async def call_remote_agent(
    agent_url: str, message: str, session_id: str = ""
) -> str:
    """调用远端 A2A Agent（骨架，待 SDK 联调）。"""
    try:
        from a2a.client import A2AClient
    except Exception as exc:
        logger.warning("a2a_sdk_unavailable", error=str(exc)[:100])
        return f"（A2A SDK 不可用：{exc}）"

    try:
        client = await A2AClient.connect(agent_url)
        response = await client.send_message(message)
        return response
    except Exception as exc:
        logger.error("a2a_call_failed", error=str(exc))
        return f"（A2A 调用失败：{exc}）"
