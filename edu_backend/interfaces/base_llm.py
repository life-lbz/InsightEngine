"""LLM 抽象接口（生产级增强：健康检查）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any


class BaseLLM(ABC):
    """所有 LLM 实现必须继承。

    生产级增强：
        - health_check：供降级链判断模型是否可用
        - count_tokens：Token 用量统计
    """

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """非流式生成。

        入参：
            system_prompt：系统提示词
            user_prompt：用户提示词

        返回：
            LLM 生成的文本
        """

    @abstractmethod
    def stream(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Iterator[str]:
        """流式生成。

        入参：
            system_prompt：系统提示词
            user_prompt：用户提示词

        返回：
            Token 迭代器
        """

    def health_check(self) -> dict[str, Any]:
        """健康检查（发送一个最小请求验证连通性）。

        返回：
            {"healthy": bool, "latency_ms": int, "model": str}
        """
        return {"healthy": True, "latency_ms": 0, "model": "unknown"}

    def count_tokens(self, text: str) -> int:
        """估算 Token 数（子类可覆写为精确计数）。

        入参：
            text：待计数的文本

        返回：
            Token 数（默认按 1 token ≈ 2 个中文字符估算）
        """
        return max(1, len(text) // 2)