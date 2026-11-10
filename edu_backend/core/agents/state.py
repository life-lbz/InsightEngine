"""Agent 协作状态：LangGraph State 定义。"""
from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class CollabState(TypedDict, total=False):
    """多 Agent 协作共享状态。

    messages 由 add_messages reducer 自动累加（LangGraph 消息协议），
    其余字段为业务侧传递的上下文，供各专家 Agent 读写协作。
    """

    messages: Annotated[list, add_messages]
    role: str
    course_id: str
    session_id: str
    user_id: str
    intent: str
    sources: list[dict[str, Any]]
    practice_records: list[dict[str, Any]]
    insight_report: str
    faq_candidates: list[dict[str, Any]]
    final_answer: str
