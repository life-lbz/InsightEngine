"""出题 Agent：按知识点/薄弱点从题库抽题或用 LLM 生成新题。"""
from __future__ import annotations

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from llm.rate_limiter import get_llm_semaphore
from llm.resilient_client import get_resilient_llm
from storage.async_db import run_sql

QUIZ_SYSTEM_PROMPT = """你是教育出题专家。根据学员的知识点或薄弱环节，提供练习题。

工作流程：
1. 若学员指定知识点，调用 fetch_questions 从题库抽题
2. 若题库不足或需要针对性出题，调用 generate_quiz 用 LLM 生成新题
3. 调用 save_practice 记录学员练习
4. 返回题目列表（含题型、难度、题干、选项、答案、解析）

约束：
- 优先从题库抽题（fetch_questions），不足时再生成
- 题目难度匹配学员水平
- 每次提供 3-5 道题，使用中文
"""

_FETCH_SQL = """
    SELECT question_id, question_type, difficulty, question_text,
           answer, explanation
    FROM questions
    WHERE course_id = :cid AND is_deleted = 0
      AND (:kp = '' OR point_id IN (
          SELECT point_id FROM knowledge_points
          WHERE name LIKE :kw AND is_deleted = 0
      ))
    ORDER BY RAND() LIMIT :n
"""

_SAVE_PRACTICE_SQL = """
    INSERT INTO practice_records
        (user_id, course_id, question_id, question_text, user_answer, is_correct, created_at)
    VALUES (:uid, :cid, :qid, :qt, :ua, :ic, NOW())
"""


@tool
async def fetch_questions(course_id: str, knowledge_point: str = "", limit: int = 5) -> list[dict]:
    """从题库按知识点/课程随机抽题。

    Args:
        course_id: 课程 ID
        knowledge_point: 知识点名称（空则不限）
        limit: 抽题数量
    """
    rows = await run_sql(
        _FETCH_SQL,
        {"cid": course_id, "kp": knowledge_point, "kw": f"%{knowledge_point}%", "n": limit},
    )
    return rows


@tool
async def generate_quiz(course_id: str, knowledge_point: str, question_type: str = "single_choice") -> dict:
    """用 LLM 按知识点生成新题目。

    Args:
        course_id: 课程 ID
        knowledge_point: 知识点名称
        question_type: 题型（single_choice/multiple_choice/short_answer）
    """
    llm = get_resilient_llm()
    prompt = (
        f"请围绕知识点「{knowledge_point}」出一道{question_type}题。"
        "要求：题干清晰、选项合理（选择题给4个选项）、附答案与解析。"
        "输出格式：题干\\n选项\\n答案\\n解析。"
    )
    async with get_llm_semaphore():
        resp = await llm.agenerate([{"role": "user", "content": prompt}])
    raw = getattr(resp, "content", str(resp))
    return {"raw": raw, "knowledge_point": knowledge_point, "question_type": question_type}


@tool
async def save_practice(
    user_id: str,
    course_id: str,
    question_id: str,
    question_text: str,
    user_answer: str,
    is_correct: bool,
) -> int:
    """记录学员的练习答题（写入 practice_records 表），供学情分析复用。"""
    try:
        return await run_sql(
            _SAVE_PRACTICE_SQL,
            {
                "uid": user_id, "cid": course_id, "qid": question_id,
                "qt": question_text, "ua": user_answer, "ic": 1 if is_correct else 0,
            },
            write=True,
        )
    except Exception:
        return 0


def build_quiz_agent():
    """构建出题 Agent。"""
    llm = get_resilient_llm().get_chat_model()
    return create_react_agent(
        model=llm,
        tools=[fetch_questions, generate_quiz, save_practice],
        prompt=QUIZ_SYSTEM_PROMPT,
        name="quiz_agent",
    )
