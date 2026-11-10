"""Agent 安全加固：角色路由白名单 + 输入注入防护 + PII 脱敏。"""
from __future__ import annotations

import re

from anyio import to_thread

from config.settings import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)


def filter_agents_by_role(role: str) -> list[str]:
    """按 role 返回允许调用的 Agent 名列表（硬约束）。

    越权请求一律降级为答疑，由 agent_engine 在构建 Supervisor 时收窄可用 Agent。
    """
    settings = get_settings()
    return list(
        settings.agent_role_whitelist.get(
            role, settings.agent_role_whitelist["student"]
        )
    )


async def input_guard(text: str) -> str:
    """输入注入防护：检测 prompt injection 并返回清洗后输入。

    复用 pipeline.input_guard.PromptInjectionGuard。
    """
    from pipeline.input_guard import PromptInjectionGuard

    guard = PromptInjectionGuard()
    result = await to_thread.run_sync(lambda: guard.check(text))
    if not result.safe:
        logger.warning(
            "input_guard_detected",
            patterns=result.detected_patterns,
        )
    return result.sanitized_input


_PII_PATTERNS = [
    re.compile(r"\b1[3-9]\d{9}\b"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    re.compile(r"\b\d{15,18}\b"),
]


def mask_pii(text: str) -> str:
    """脱敏手机号/邮箱/身份证等 PII，供学情报告输出前调用。"""
    for p in _PII_PATTERNS:
        text = p.sub("***", text)
    return text
