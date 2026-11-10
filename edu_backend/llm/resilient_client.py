"""LLM 容错客户端：主备模型降级链 + 流式断连恢复。"""
from __future__ import annotations

import time
from typing import Any, Generator

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import get_settings
from observability.logger import get_logger
from observability.metrics import llm_request_duration, llm_request_total

logger = get_logger(__name__)


class LLMFailoverChain:
    """LLM 降级链：主模型失败时自动切换备用模型。

    降级策略：
        1. 主模型（deepseek-v4-flash）超时或报错
        2. 自动切换到备用模型（deepseek-v4-lite）重试
        3. 备用模型也失败时返回模板兜底回复
    """

    def __init__(self) -> None:
        """初始化降级链。"""
        self.settings = get_settings()
        self.primary_model = self.settings.llm_model
        self.fallback_model = self.settings.llm_fallback_model
        self.retry_count = self.settings.llm_retry_count
        self.timeout = self.settings.llm_timeout

    @retry(
        retry=retry_if_exception_type(TimeoutError),
        stop=stop_after_attempt(2),
        wait=wait_exponential(min=1, max=4),
        reraise=True,
    )
    def _call_model(
        self,
        model: str,
        messages: list[dict[str, str]],
        stream: bool = False,
    ) -> Any:
        """调用单个 LLM 模型。

        入参：
            model：模型名称
            messages：消息列表
            stream：是否流式输出

        返回：
            LLM 响应或流式生成器

        异常：
            TimeoutError：请求超时
        """
        from langchain_deepseek import ChatDeepSeek
        llm = ChatDeepSeek(
            model=model,
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
            temperature=self.settings.llm_temperature,
            timeout=self.timeout,
            streaming=stream,
        )
        return llm.invoke(messages) if not stream else llm.stream(messages)

    def generate(
        self,
        messages: list[dict[str, str]],
        stream: bool = False,
    ) -> Any:
        """生成回复（带降级链）。

        入参：
            messages：消息列表
            stream：是否流式输出

        返回：
            LLM 响应或流式生成器

        降级流程：
            主模型 → 重试 → 备用模型 → 重试 → 模板兜底
        """
        start_time = time.perf_counter()

        # 尝试主模型
        for attempt in range(self.retry_count):
            try:
                result = self._call_model(self.primary_model, messages, stream)
                elapsed = time.perf_counter() - start_time
                llm_request_duration.labels(model=self.primary_model).observe(elapsed)
                llm_request_total.labels(
                    model=self.primary_model, status="success"
                ).inc()
                return result
            except TimeoutError:
                logger.warning(
                    "llm_primary_timeout",
                    model=self.primary_model,
                    attempt=attempt + 1,
                )
                llm_request_total.labels(
                    model=self.primary_model, status="timeout"
                ).inc()
            except Exception as exc:
                logger.warning(
                    "llm_primary_error",
                    model=self.primary_model,
                    error=str(exc),
                    attempt=attempt + 1,
                )
                llm_request_total.labels(
                    model=self.primary_model, status="failed"
                ).inc()

        # 尝试备用模型
        logger.warning("llm_failover_to_fallback", fallback_model=self.fallback_model)
        llm_request_total.labels(
            model=self.fallback_model, status="failover"
        ).inc()

        for attempt in range(self.retry_count):
            try:
                result = self._call_model(self.fallback_model, messages, stream)
                elapsed = time.perf_counter() - start_time
                llm_request_duration.labels(model=self.fallback_model).observe(elapsed)
                llm_request_total.labels(
                    model=self.fallback_model, status="success"
                ).inc()
                return result
            except Exception as exc:
                logger.warning(
                    "llm_fallback_error",
                    model=self.fallback_model,
                    error=str(exc),
                    attempt=attempt + 1,
                )
                llm_request_total.labels(
                    model=self.fallback_model, status="failed"
                ).inc()

        # 全部失败，返回兜底
        logger.error("llm_all_models_failed")
        llm_request_total.labels(model="fallback", status="template").inc()
        return self._template_fallback(messages)

    def get_chat_model(self) -> Any:
        """返回 langchain ChatDeepSeek 主模型实例（供 LangGraph Agent 编排使用）。

        Agent 编排需要 langchain Runnable 接口（ainvoke/astream），此方法
        返回主模型的 ChatDeepSeek 实例（官方集成，正确透传 reasoning_content，
        避免 thinking 模式多轮对话报 400）；主备降级由 agent_engine 层的
        try/except + RagPipeline 回退兜底。
        """
        from langchain_deepseek import ChatDeepSeek
        return ChatDeepSeek(
            model=self.primary_model,
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
            temperature=self.settings.llm_temperature,
            timeout=self.timeout,
        )

    async def agenerate(self, messages: list[dict[str, str]]) -> Any:
        """异步生成：在线程池执行同步 generate，避免阻塞事件循环。

        供 Agent 工具内部需要 LLM 的场景（如生成题目）调用。
        """
        from anyio import to_thread
        return await to_thread.run_sync(
            lambda: self.generate(messages, stream=False)
        )

    def _template_fallback(self, messages: list[dict[str, str]]) -> Any:
        """模板兜底回复：所有 LLM 模型不可用时返回。

        入参：
            messages：原始消息列表

        返回：
            模拟的 LLM 响应对象
        """
        class TemplateResponse:
            """模板兜底响应对象。"""
            content = (
                "抱歉，答疑服务暂时不可用。"
                "请稍后重试，或联系课程助教获取帮助。"
            )

        return TemplateResponse()

    def stream_resume(
        self,
        messages: list[dict[str, str]],
        last_token: str,
        session_id: str,
    ) -> Generator[str, None, None]:
        """流式断连恢复：从上次中断位置继续生成。

        入参：
            messages：原始消息列表
            last_token：中断前最后生成的 token
            session_id：会话 ID

        生成：
            续传的 token 流
        """
        resume_messages = list(messages)
        resume_messages.append({
            "role": "user",
            "content": f"请从以下内容继续：{last_token}",
        })

        logger.info(
            "stream_resume",
            session_id=session_id,
            last_token=last_token[:50],
        )

        try:
            result = self.generate(resume_messages, stream=True)
            if hasattr(result, "__iter__"):
                for chunk in result:
                    yield chunk
            else:
                yield getattr(result, "content", "（生成中断，请重新提问）")
        except Exception as exc:
            logger.error(
                "stream_resume_failed",
                session_id=session_id,
                error=str(exc),
            )
            yield "（生成中断，请重新提问）"


_resilient_chain: LLMFailoverChain | None = None


def get_resilient_llm() -> LLMFailoverChain:
    """返回 LLM 降级链单例。"""
    global _resilient_chain
    if _resilient_chain is None:
        _resilient_chain = LLMFailoverChain()
    return _resilient_chain