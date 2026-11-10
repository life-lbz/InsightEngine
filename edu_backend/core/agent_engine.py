"""LangGraph Agent 协作引擎：Supervisor + 专家 Agent 编排。

保留 RagPipeline 线性管道不动，在其之上叠加多 Agent 协作层。
Supervisor 按 role 路由到对应专家 Agent（role 受限由图结构保证），
Agent 间可协作。失败由 agent_router 层回退 RagPipeline 兜底。
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph_supervisor import create_supervisor

from config.settings import get_settings
from core.agents import (
    build_explain_agent,
    build_kb_ops_agent,
    build_planner_agent,
    build_qa_agent,
    build_quiz_agent,
    build_teacher_insight_agent,
)
from llm.resilient_client import get_resilient_llm
from memory.checkpointer import get_checkpointer
from observability.logger import get_logger
from pipeline.agent_security import filter_agents_by_role

logger = get_logger(__name__)

SUPERVISOR_PROMPT = """你是在线教育多 Agent 协作系统的调度主管（Supervisor）。

你管理若干专家 Agent，根据用户请求意图分派：
- qa_agent：智能答疑
- quiz_agent：出题练习
- planner_agent：学习路径规划
- explain_agent：错题讲解
- teacher_insight_agent：学情分析（教师端）
- kb_ops_agent：知识库运维（管理端）

原则：
1. 根据意图选最合适的 Agent 处理
2. 不确定时默认分派给 qa_agent
3. 用中文，专业友好
"""

AGENT_BUILDERS: dict[str, Any] = {
    "qa_agent": build_qa_agent,
    "quiz_agent": build_quiz_agent,
    "planner_agent": build_planner_agent,
    "explain_agent": build_explain_agent,
    "teacher_insight_agent": build_teacher_insight_agent,
    "kb_ops_agent": build_kb_ops_agent,
}

_graph_cache: dict[str, Any] = {}


def build_agent_graph(role: str = "student") -> Any:
    """按 role 构建受限的 Supervisor 编排图。

    用 filter_agents_by_role 收窄该 role 可用的 Agent 子集，
    越权请求无法触达受限 Agent（硬约束，不依赖 Supervisor 自觉）。
    """
    allowed = filter_agents_by_role(role)
    agents = [AGENT_BUILDERS[name]() for name in allowed if name in AGENT_BUILDERS]
    if not agents:
        agents = [build_qa_agent()]

    llm = get_resilient_llm().get_chat_model()
    supervisor = create_supervisor(
        agents=agents,
        model=llm,
        prompt=SUPERVISOR_PROMPT,
        output_mode="last_message",
        supervisor_name="supervisor",
    )
    return supervisor.compile(
        checkpointer=get_checkpointer(),
    )


def get_agent_graph(role: str = "student") -> Any:
    """获取按 role 缓存的 Supervisor 图（进程级单例）。"""
    if role not in _graph_cache:
        _graph_cache[role] = build_agent_graph(role)
    return _graph_cache[role]


async def agent_answer(
    question: str,
    role: str = "student",
    course_id: str = "",
    session_id: str = "",
    user_id: str = "",
) -> dict[str, Any]:
    """供路由层调用：执行 Agent 协作并返回最终答案。

    失败时由调用方（agent_router）捕获并回退 RagPipeline。
    """
    graph = get_agent_graph(role)
    context = (
        f"[上下文 course_id={course_id} session_id={session_id} "
        f"user_id={user_id} role={role}]"
    )
    inputs = {
        "messages": [
            SystemMessage(content=context),
            HumanMessage(content=question),
        ],
    }
    config = {
        "configurable": {"thread_id": session_id or "default"},
        "recursion_limit": get_settings().agent_recursion_limit,
    }
    result = await graph.ainvoke(inputs, config=config)
    messages = result.get("messages", [])
    answer = ""
    if messages:
        last = messages[-1]
        answer = getattr(last, "content", str(last))
    return {
        "answer": answer,
        "sources": result.get("sources", []),
        "intent": result.get("intent", ""),
    }
