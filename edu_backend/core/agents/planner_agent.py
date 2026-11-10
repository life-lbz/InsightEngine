"""学习路径规划 Agent：分析学员掌握度并规划下一步学习。"""
from __future__ import annotations

import json

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from llm.rate_limiter import get_llm_semaphore
from llm.resilient_client import get_resilient_llm
from storage.async_db import run_sql, run_sql_one

PLANNER_SYSTEM_PROMPT = """你是学习路径规划专家。根据学员的进度与掌握情况，规划下一步学习。

工作流程：
1. 调用 get_student_progress 获取学员当前章节与已掌握知识点
2. 调用 get_chapters 与 get_knowledge_points 了解课程结构
3. 调用 recommend_path 让 LLM 基于上述信息生成个性化学习路径
4. 返回推荐章节、知识点与学习建议

约束：
- 路径要循序渐进，先补薄弱点再推进新内容
- 使用中文，建议具体可执行
"""

_PROGRESS_SQL = """
    SELECT user_id, course_id, current_chapter_id, mastered_points, updated_at
    FROM student_progress
    WHERE user_id = :uid AND course_id = :cid
"""

_CHAPTERS_SQL = """
    SELECT chapter_id, chapter_no, title, summary
    FROM chapters
    WHERE course_id = :cid AND is_deleted = 0
    ORDER BY chapter_no
"""

_POINTS_SQL = """
    SELECT point_id, chapter_id, name, summary
    FROM knowledge_points
    WHERE course_id = :cid AND is_deleted = 0
    ORDER BY chapter_id
"""


@tool
async def get_student_progress(user_id: str, course_id: str) -> dict:
    """获取学员学习进度（当前章节 + 已掌握知识点）。"""
    row = await run_sql_one(_PROGRESS_SQL, {"uid": user_id, "cid": course_id})
    if not row:
        return {
            "user_id": user_id, "course_id": course_id,
            "current_chapter_id": None, "mastered_points": [],
        }
    mastered = row.get("mastered_points") or "[]"
    if isinstance(mastered, str):
        try:
            mastered = json.loads(mastered)
        except Exception:
            mastered = []
    return {**row, "mastered_points": mastered}


@tool
async def get_chapters(course_id: str) -> list[dict]:
    """获取课程的章节列表（按顺序）。"""
    return await run_sql(_CHAPTERS_SQL, {"cid": course_id})


@tool
async def get_knowledge_points(course_id: str) -> list[dict]:
    """获取课程的知识点列表。"""
    return await run_sql(_POINTS_SQL, {"cid": course_id})


@tool
async def recommend_path(
    user_id: str,
    course_id: str,
    progress: dict,
    chapters: list[dict],
    knowledge_points: list[dict],
) -> str:
    """基于学员进度与课程结构，用 LLM 生成个性化学习路径建议。"""
    llm = get_resilient_llm()
    prompt = (
        f"学员 {user_id} 在课程 {course_id} 的进度："
        f"{json.dumps(progress, ensure_ascii=False)}。"
        f"课程章节：{json.dumps(chapters, ensure_ascii=False)}。"
        f"知识点：{json.dumps(knowledge_points, ensure_ascii=False)}。"
        "请生成下一步学习路径：推荐章节、要掌握的知识点、学习建议。中文输出。"
    )
    async with get_llm_semaphore():
        resp = await llm.agenerate([{"role": "user", "content": prompt}])
    return getattr(resp, "content", str(resp))


def build_planner_agent():
    """构建学习路径规划 Agent。"""
    llm = get_resilient_llm().get_chat_model()
    return create_react_agent(
        model=llm,
        tools=[get_student_progress, get_chapters, get_knowledge_points, recommend_path],
        prompt=PLANNER_SYSTEM_PROMPT,
        name="planner_agent",
    )
