"""Agent 行为护栏：成本预算 + 输出内容安全/幻觉检测。

复用现有 pipeline.output_filter.OutputFilter 与
pipeline.hallucination_guard.HallucinationChecker，避免重造轮子。
"""
from __future__ import annotations

from typing import Any

from anyio import to_thread
from langchain_core.callbacks import BaseCallbackHandler

from observability.logger import get_logger

logger = get_logger(__name__)


class CostBudgetGuard(BaseCallbackHandler):
    """累计 token 超预算即抛 RuntimeError，由路由层捕获降级。"""

    def __init__(self, max_tokens: int = 8000) -> None:
        self.total = 0
        self.max_tokens = max_tokens

    def on_llm_end(self, response, **kwargs) -> None:
        usage = (response.llm_output or {}).get("token_usage", {})
        self.total += usage.get("total_tokens", 0)
        if self.total > self.max_tokens:
            raise RuntimeError(
                f"agent cost budget exceeded: {self.total}>{self.max_tokens}"
            )


async def output_guard(
    text: str,
    sources: list[dict] | None = None,
    course_id: str = "",
) -> str:
    """过滤输出内容：内容安全 + 幻觉检测。

    供路由层在 Agent 产出最终回复后调用，确保回传前端的内容安全可靠。
    """
    from pipeline.output_filter import OutputFilter
    from pipeline.hallucination_guard import HallucinationChecker

    filt = OutputFilter()
    filtered, _hit = await to_thread.run_sync(lambda: filt.filter_output(text))

    checker = HallucinationChecker()
    try:
        result = await to_thread.run_sync(
            lambda: checker.check(filtered, sources or [], course_id)
        )
        if checker.should_degrade(result):
            filtered = "（检测到可能未充分支撑的内容，已降级处理）" + filtered
    except Exception as exc:
        logger.warning("hallucination_check_failed", error=str(exc)[:100])

    return filtered
