"""MCP Server：把 LMS 学员进度/题库能力标准化暴露给外部 Agent。

基于 mcp.server.fastmcp.FastMCP。供 A2A 远端 Agent 或外部工具调用，
实现 agent-to-tool 的标准化能力发现。
"""
from __future__ import annotations

from observability.logger import get_logger

logger = get_logger(__name__)


def build_lms_server():
    """构建 LMS MCP Server（延迟导入 mcp，避免版本冲突阻塞）。"""
    from mcp.server.fastmcp import FastMCP

    from storage.async_db import run_sql

    mcp = FastMCP("lms")

    @mcp.tool()
    async def get_student_progress(user_id: str, course_id: str) -> dict:
        """获取学员进度（MCP 暴露）。"""
        rows = await run_sql(
            "SELECT user_id, course_id, current_chapter_id, mastered_points "
            "FROM student_progress WHERE user_id=:u AND course_id=:c",
            {"u": user_id, "c": course_id},
        )
        return rows[0] if rows else {}

    @mcp.tool()
    async def list_questions(course_id: str, limit: int = 5) -> list[dict]:
        """列出题库题目（MCP 暴露）。"""
        return await run_sql(
            "SELECT question_id, question_type, difficulty, question_text "
            "FROM questions WHERE course_id=:c AND is_deleted=0 LIMIT :n",
            {"c": course_id, "n": limit},
        )

    return mcp
