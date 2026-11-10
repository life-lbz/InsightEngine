"""Agent 协作子包：六个专家 Agent 定义。

每个 Agent 用 langgraph.prebuilt.create_react_agent 构建，
绑定各自工具集与系统提示，由 core.agent_engine 的 Supervisor 编排。
"""
from core.agents.qa_agent import build_qa_agent
from core.agents.quiz_agent import build_quiz_agent
from core.agents.planner_agent import build_planner_agent
from core.agents.explain_agent import build_explain_agent
from core.agents.teacher_insight_agent import build_teacher_insight_agent
from core.agents.kb_ops_agent import build_kb_ops_agent

__all__ = [
    "build_qa_agent",
    "build_quiz_agent",
    "build_planner_agent",
    "build_explain_agent",
    "build_teacher_insight_agent",
    "build_kb_ops_agent",
]
