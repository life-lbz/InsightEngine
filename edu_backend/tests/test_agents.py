"""Agent 协作单元测试：State 字段、role 白名单、PII 脱敏、工具可调用。"""
import pytest


def test_state_fields():
    from core.agents.state import CollabState

    keys = set(CollabState.__annotations__.keys())
    assert "messages" in keys
    assert "role" in keys
    assert "course_id" in keys
    assert "session_id" in keys


def test_filter_agents_by_role():
    from pipeline.agent_security import filter_agents_by_role

    student = set(filter_agents_by_role("student"))
    assert "qa_agent" in student
    assert "teacher_insight_agent" not in student

    teacher = set(filter_agents_by_role("teacher"))
    assert "teacher_insight_agent" in teacher

    admin = set(filter_agents_by_role("admin"))
    assert "kb_ops_agent" in admin


def test_mask_pii():
    from pipeline.agent_security import mask_pii

    out = mask_pii("联系 13800138000 或 a@b.com，身份证 110101199001011234")
    assert "13800138000" not in out
    assert "a@b.com" not in out
    assert "110101199001011234" not in out


def test_tool_callables():
    from core.agents.qa_agent import rag_answer
    from core.agents.quiz_agent import fetch_questions, generate_quiz
    from core.agents.planner_agent import get_student_progress
    from core.agents.explain_agent import get_question_detail
    from core.agents.teacher_insight_agent import get_class_insight
    from core.agents.kb_ops_agent import mine_unresolved_questions

    for t in (
        rag_answer, fetch_questions, generate_quiz, get_student_progress,
        get_question_detail, get_class_insight, mine_unresolved_questions,
    ):
        assert callable(t)
