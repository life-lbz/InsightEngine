"""MCP 工具加载：从 MCP Server 发现工具并入 Agent。

延迟导入 langchain_mcp_adapters，版本不兼容时返回空列表，
不阻塞主流程（MCP 为 P3 增强能力）。
"""
from __future__ import annotations

from config.settings import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)


async def load_mcp_tools() -> list:
    """加载 MCP 工具。失败时返回空列表，不影响 Agent 编排。"""
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except Exception as exc:
        logger.warning("mcp_adapters_unavailable", error=str(exc)[:100])
        return []

    settings = get_settings()
    try:
        client = MultiServerMCPClient(
            {
                "lms": {
                    "url": f"http://127.0.0.1:{settings.api_port}/mcp",
                    "transport": "streamable_http",
                }
            }
        )
        tools = await client.get_tools()
        logger.info("mcp_tools_loaded", count=len(tools))
        return tools
    except Exception as exc:
        logger.warning("mcp_tools_load_failed", error=str(exc)[:100])
        return []
