"""学情分析 Agent（教师端）：聚合答题/答疑数据生成学情报告。"""
from __future__ import annotations

import json

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from llm.rate_limiter import get_llm_semaphore
from llm.resilient_client import get_resilient_llm
from pipeline.agent_security import mask_pii
from storage.async_db import run_sql

INSIGHT_SYSTEM_PROMPT = """你是学情分析专家，面向教师端。基于班级答题与答疑数据生成学情报告。

工作流程：
1. 调用 get_class_insight 获取班级整体答题正确率与答疑高频问题
2. 调用 find_high_freq_questions 定位高频错题
3. 调用 generate_insight_report 用 LLM 汇总成结构化报告

约束：
- 报告面向教师，聚焦教学改进建议
- 学员姓名等 PII 必须脱敏
- 使用中文，结论要有数据支撑
"""

_CLASS_INSIGHT_SQL = """
    SELECT course_id,
           COUNT(*) AS total_answers,
           SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct_count
    FROM practice_records
    WHERE course_id = :cid
    GROUP BY course_id
"""

_HIGH_FREQ_Q_SQL = """
    SELECT question, COUNT(*) AS cnt
    FROM qa_feedback
    WHERE course_id = :cid
    GROUP BY question
    ORDER BY cnt DESC
    LIMIT :n
"""

_RETRIEVAL_HOT_SQL = """
    SELECT query, intent, COUNT(*) AS cnt
    FROM retrieval_logs
    WHERE session_id IN (
        SELECT session_id FROM qa_feedback WHERE course_id = :cid
    )
    GROUP BY query, intent
    ORDER BY cnt DESC
    LIMIT :n
"""


@tool
async def get_class_insight(course_id: str) -> dict:
    """获取班级整体学情：答题正确率 + 答疑高频问题。"""
    try:
        practice = await run_sql(_CLASS_INSIGHT_SQL, {"cid": course_id})
    except Exception:
        practice = []
    try:
        hot = await run_sql(_RETRIEVAL_HOT_SQL, {"cid": course_id, "n": 10})
    except Exception:
        hot = []
    return {
        "course_id": course_id,
        "practice_summary": practice,
        "hot_questions": hot,
    }


@tool
async def find_high_freq_questions(course_id: str, limit: int = 5) -> list[dict]:
    """定位高频错题/差评问题。"""
    try:
        return await run_sql(_HIGH_FREQ_Q_SQL, {"cid": course_id, "n": limit})
    except Exception:
        return []


@tool
async def generate_insight_report(course_id: str, insight: dict, high_freq: list[dict]) -> str:
    """用 LLM 汇总生成结构化学情报告（自动脱敏 PII）。"""
    llm = get_resilient_llm()
    prompt = (
        f"课程 {course_id} 的学情数据：{json.dumps(insight, ensure_ascii=False)}。"
        f"高频错题：{json.dumps(high_freq, ensure_ascii=False)}。"
        "请生成教师端学情报告：包含整体正确率、薄弱知识点、"
        "高频问题、教学改进建议。中文输出。"
    )
    async with get_llm_semaphore():
        resp = await llm.agenerate([{"role": "user", "content": prompt}])
    report = getattr(resp, "content", str(resp))
    return mask_pii(report)


def build_teacher_insight_agent():
    """构建学情分析 Agent。"""
    llm = get_resilient_llm().get_chat_model()
    return create_react_agent(
        model=llm,
        tools=[get_class_insight, find_high_freq_questions, generate_insight_report],
        prompt=INSIGHT_SYSTEM_PROMPT,
        name="teacher_insight_agent",
    )
