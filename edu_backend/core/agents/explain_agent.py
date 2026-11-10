"""错题讲解 Agent：针对学员做错的题目，检索相关知识给出个性化讲解。"""
from __future__ import annotations

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from llm.resilient_client import get_resilient_llm
from storage.async_db import run_sql_one

EXPLAIN_SYSTEM_PROMPT = """你是错题讲解专家。针对学员做错的题目，给出个性化讲解。

工作流程：
1. 调用 get_question_detail 获取题目详情（题干、答案、解析）
2. 调用 rag_answer 检索相关知识，补充讲解依据
3. 组织讲解：错因分析、正确思路、知识点延伸

约束：
- 讲解要针对错因，不是简单复述答案
- 使用中文，语气鼓励
"""

_DETAIL_SQL = """
    SELECT question_id, question_type, difficulty, question_text,
           answer, explanation, point_id
    FROM questions
    WHERE question_id = :qid AND is_deleted = 0
"""


@tool
async def get_question_detail(question_id: str) -> dict:
    """获取题目详情（题干、答案、解析、知识点）。"""
    return await run_sql_one(_DETAIL_SQL, {"qid": question_id}) or {}


@tool
async def rag_answer(question: str, course_id: str, session_id: str = "") -> dict:
    """检索知识库获取相关知识（复用 RagPipeline）。"""
    from core.rag_engine import get_rag_pipeline

    try:
        pipeline = get_rag_pipeline()
        result = await pipeline.answer(
            question=question, course_id=course_id, session_id=session_id
        )
        return {
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "ok": True,
        }
    except Exception as e:
        return {"answer": "", "ok": False, "error": f"rag_unavailable: {e}"}


def build_explain_agent():
    """构建错题讲解 Agent。"""
    llm = get_resilient_llm().get_chat_model()
    return create_react_agent(
        model=llm,
        tools=[get_question_detail, rag_answer],
        prompt=EXPLAIN_SYSTEM_PROMPT,
        name="explain_agent",
    )
