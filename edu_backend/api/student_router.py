"""学员路由：个人进度查询、课程资料浏览。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from api.auth import require_student_auth
from config.settings import get_settings
from observability.logger import get_logger
from storage.db_engine import get_engine

router = APIRouter()
logger = get_logger(__name__)


def _load_user_course_ids(user_id: str) -> list[str]:
    """实时读取用户可访问课程列表（管理端分配后即时生效，不依赖 JWT 快照）。"""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT course_ids FROM users "
                    "WHERE user_id = :uid AND is_active = 1"
                ),
                {"uid": user_id},
            ).fetchone()
        if row and row[0]:
            return [c for c in str(row[0]).split(",") if c]
    except Exception as exc:
        logger.warning("load_user_course_ids_failed", user_id=user_id, error=str(exc))
    return []


def _resolve_course_scope(course_id: str | None, user_course_ids: list[str]) -> tuple[str, bool]:
    """解析课程范围：未传时取首个分配课程；校验越权。

    返回：
        (有效 course_id 或 "", 是否有已分配课程)
    """
    if course_id:
        if not user_course_ids or course_id not in user_course_ids:
            raise HTTPException(status_code=403, detail="无权访问该课程")
        return course_id, True
    if user_course_ids:
        return user_course_ids[0], True
    return "", False


@router.get("/student/progress")
async def student_progress(
    course_id: str | None = Query(default=None),
    user=Depends(require_student_auth),
):
    """查询当前学员的个人学习进度（仅限已分配课程）。"""
    settings = get_settings()
    engine = get_engine()
    user_id = user["user_id"]
    try:
        user_course_ids = _load_user_course_ids(user_id)
        resolved_course_id, _ = _resolve_course_scope(course_id, user_course_ids)

        with engine.connect() as conn:
            where = "WHERE user_id = :uid"
            params: dict[str, Any] = {"uid": user_id}
            if resolved_course_id:
                where += " AND course_id = :ci"
                params["ci"] = resolved_course_id
            result = conn.execute(
                text(
                    f"SELECT user_id, course_id, current_chapter_id, "
                    f"mastered_points, updated_at "
                    f"FROM student_progress {where}"
                ),
                params,
            )
            rows = result.fetchall()
            progress = [
                {
                    "user_id": r[0],
                    "course_id": r[1],
                    "current_chapter_id": r[2],
                    "mastered_points": r[3].split(",") if r[3] else [],
                    "updated_at": str(r[4]) if r[4] else "",
                }
                for r in rows
            ]

            chat_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM chat_messages WHERE user_id = :uid"
                ),
                {"uid": user_id},
            ).scalar() or 0

            feedback_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM qa_feedback WHERE session_id IN "
                    "(SELECT DISTINCT session_id FROM chat_messages WHERE user_id = :uid)"
                ),
                {"uid": user_id},
            ).scalar() or 0

        return {
            "progress": progress,
            "chat_count": chat_count,
            "feedback_count": feedback_count,
            "course_ids": user_course_ids,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("student_progress_error", error=str(exc))
        return {"progress": [], "chat_count": 0, "feedback_count": 0, "course_ids": []}


@router.get("/student/sessions")
async def student_sessions(
    user=Depends(require_student_auth),
):
    """当前学员的会话列表（聊天历史入口，按最近活跃排序）。"""
    engine = get_engine()
    user_id = user["user_id"]
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT session_id, COUNT(*) as msg_count, MAX(id) as last_id "
                    "FROM chat_messages "
                    "WHERE user_id = :uid AND session_id IS NOT NULL AND session_id != '' "
                    "GROUP BY session_id ORDER BY last_id DESC LIMIT 50"
                ),
                {"uid": user_id},
            ).fetchall()

            sessions = []
            for r in rows:
                sid, msg_count, _ = r
                last = conn.execute(
                    text(
                        "SELECT message FROM chat_messages "
                        "WHERE session_id = :sid ORDER BY id DESC LIMIT 1"
                    ),
                    {"sid": sid},
                ).fetchone()
                preview, role = "", "assistant"
                if last and last[0]:
                    try:
                        import json as _json
                        data = _json.loads(last[0])
                        preview = str(data.get("content", ""))[:80]
                        role = data.get("role", "assistant")
                    except Exception:
                        preview = str(last[0])[:80]
                sessions.append({
                    "session_id": sid,
                    "message_count": msg_count,
                    "preview": preview,
                    "role": role,
                })

        return {"sessions": sessions, "total": len(sessions)}
    except Exception as exc:
        logger.error("student_sessions_error", error=str(exc))
        return {"sessions": [], "total": 0}


@router.get("/student/materials")
async def student_materials(
    course_id: str | None = Query(default=None),
    user=Depends(require_student_auth),
):
    """查询课程资料：按章节列出知识点和题目数量（仅限已分配课程）。"""
    settings = get_settings()
    engine = get_engine()
    user_id = user["user_id"]
    try:
        user_course_ids = _load_user_course_ids(user_id)
        resolved_course_id, assigned = _resolve_course_scope(course_id, user_course_ids)
        if not assigned or not resolved_course_id:
            return {"chapters": [], "total": 0, "assigned": False, "course_ids": []}

        with engine.connect() as conn:
            chapters = conn.execute(
                text(
                    "SELECT chapter_id, course_id, chapter_no, title, summary "
                    "FROM chapters WHERE course_id = :ci AND is_deleted = 0 "
                    "ORDER BY chapter_no"
                ),
                {"ci": resolved_course_id},
            ).fetchall()

            materials = []
            for ch in chapters:
                chapter_id = ch[0]
                point_count = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM knowledge_points "
                        "WHERE chapter_id = :chi AND is_deleted = 0"
                    ),
                    {"chi": chapter_id},
                ).scalar() or 0

                question_count = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM questions "
                        "WHERE chapter_id = :chi AND is_deleted = 0"
                    ),
                    {"chi": chapter_id},
                ).scalar() or 0

                faq_count = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM faqs "
                        "WHERE course_id = :ci AND is_deleted = 0"
                    ),
                    {"ci": resolved_course_id},
                ).scalar() or 0

                materials.append({
                    "chapter_id": ch[0],
                    "course_id": ch[1],
                    "chapter_no": ch[2],
                    "title": ch[3],
                    "summary": ch[4] or "",
                    "point_count": point_count,
                    "question_count": question_count,
                    "faq_count": faq_count,
                })

        return {
            "chapters": materials,
            "total": len(materials),
            "assigned": True,
            "course_ids": user_course_ids,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("student_materials_error", error=str(exc))
        return {"chapters": [], "total": 0, "assigned": False, "course_ids": []}
