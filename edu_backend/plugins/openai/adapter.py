"""OpenAI 兼容 LLM 插件（生产级增强：健康检查 + Token 计数）。"""
from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from factory.registry import llm_registry
from interfaces.base_llm import BaseLLM
from observability.logger import get_logger

logger = get_logger(__name__)


class OpenAiCompatibleAdapter(BaseLLM):
    """ChatOpenAI 适配器。

    生产级增强：
        - health_check：发送 "ping" 请求验证 LLM 连通性
        - count_tokens：使用 tiktoken 精确计数
    """

    def __init__(self, config: dict) -> None:
        self.config = config
        self.model_name = config.get("model", "deepseek-chat")

    def _client(self, streaming: bool = False) -> ChatOpenAI:
        """根据插件配置创建客户端。"""
        return ChatOpenAI(
            model=self.model_name,
            api_key=self.config.get("api_key"),
            base_url=self.config.get("base_url"),
            streaming=streaming,
            temperature=self.config.get("temperature", 0.3),
            max_tokens=self.config.get("max_tokens", 2048),
            timeout=self.config.get("timeout", 30),
            max_retries=self.config.get("max_retries", 2),
        )

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        llm = self._client(streaming=False)
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        return str(response.content or "")

    def stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        llm = self._client(streaming=True)
        for chunk in llm.stream([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]):
            token = str(getattr(chunk, "content", "") or "")
            if token:
                yield token

    def health_check(self) -> dict[str, Any]:
        """发送最小请求验证 LLM 连通性。"""
        start = time.perf_counter()
        try:
            llm = self._client(streaming=False)
            response = llm.invoke([HumanMessage(content="ping")])
            latency = int((time.perf_counter() - start) * 1000)
            return {
                "healthy": True,
                "latency_ms": latency,
                "model": self.model_name,
            }
        except Exception as exc:
            latency = int((time.perf_counter() - start) * 1000)
            return {
                "healthy": False,
                "latency_ms": latency,
                "model": self.model_name,
                "error": str(exc),
            }

    def count_tokens(self, text: str) -> int:
        """使用 tiktoken 精确计数。"""
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model("gpt-4")
            return len(enc.encode(text))
        except Exception:
            return max(1, len(text) // 2)


llm_registry.register(
    "openai_compatible",
    OpenAiCompatibleAdapter,
    schema={
        "type": "object",
        "required": ["type", "model", "api_key", "base_url"],
        "properties": {
            "type": {"type": "string"},
            "model": {"type": "string"},
            "api_key": {"type": "string"},
            "base_url": {"type": "string"},
            "temperature": {"type": "number"},
            "max_tokens": {"type": "integer"},
            "timeout": {"type": "integer"},
            "max_retries": {"type": "integer"},
        },
    },
)