"""聊天路由：流式答疑 WebSocket、反馈、练习题、历史。"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from api.auth import require_student_auth, verify_token
from config.settings import get_settings
from observability.logger import get_logger
from observability.metrics import websocket_active_connections

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/stream")
async def stream(ws: WebSocket, token: str = Query(default="")):
    settings = get_settings()
    try:
        payload = verify_token(token)
    except Exception:
        await ws.close(code=4401, reason="认证失败")
        return

    await ws.accept()
    websocket_active_connections.inc()
    try:
        await ws.send_json({"type": "status", "stage": "ready", "message": "已连接"})
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "ping":
                await ws.send_json({"type": "pong"})
                continue
            if msg_type != "query":
                continue

            question = data.get("question", "")
            session_id = data.get("session_id", "")
            course_id = data.get("course_id", settings.default_course_id)

            await ws.send_json({"type": "start", "trace_id": session_id})
            await ws.send_json(
                {"type": "status", "stage": "retrieving", "message": "正在检索相关知识"}
            )

            try:
                result = await _generate_answer(question, course_id, session_id)

                await ws.send_json(
                    {
                        "type": "end",
                        "answer": result["answer"],
                        "sources": result.get("sources", []),
                        "confidence": result.get("confidence", 0.5),
                        "confidence_level": result.get("confidence_level", "medium"),
                        "intent": result.get("intent", ""),
                        "cache_hit": False,
                        "degraded": result.get("degraded", False),
                    }
                )

                try:
                    from memory.history import ChatHistoryStore
                    store = ChatHistoryStore()
                    user_id = payload.get("sub", "")
                    store.save_message(session_id, "user", question, user_id=user_id)
                    store.save_message(session_id, "assistant", result["answer"], user_id=user_id)
                except Exception as exc:
                    logger.warning("history_save_failed", error=str(exc)[:100])

            except Exception as exc:
                logger.error("ws_generate_failed", error=str(exc))
                await ws.send_json(
                    {"type": "error", "error": f"生成失败：{exc}"}
                )
    except WebSocketDisconnect:
        pass
    finally:
        websocket_active_connections.dec()


async def _generate_answer(
    question: str,
    course_id: str,
    session_id: str = "",
) -> dict[str, Any]:
    """调用 RAG 管道生成答案。

    入参：
        question：学员问题
        course_id：课程 ID
        session_id：会话 ID

    返回：
        RAG 管道返回的答案字典
    """
    from core.rag_engine import get_rag_pipeline

    pipeline = get_rag_pipeline()
    result = await pipeline.answer(
        question=question,
        course_id=course_id,
        session_id=session_id,
    )
    return result


@router.post("/feedback")
async def submit_feedback(user=Depends(require_student_auth)):
    return {"success": True}


class PracticeRequest(BaseModel):
    course_id: str = ""
    knowledge_point: str | None = None
    difficulty: str | None = None
    count: int = 5


@router.post("/practice")
async def get_practice(req: PracticeRequest, user=Depends(require_student_auth)):
    return {"questions": []}


@router.get("/history")
async def get_history(
    session_id: str = Query(...),
    limit: int = Query(default=50),
    user=Depends(require_student_auth),
):
    try:
        from memory.history import ChatHistoryStore

        store = ChatHistoryStore()
        rows = store.get_context_messages(session_id, max_messages=limit)
        messages = [
            {"id": str(i), "role": r.get("role", "user"),
             "content": r.get("content", ""), "timestamp": 0}
            for i, r in enumerate(rows)
        ]
        return {"messages": messages}
    except Exception:
        return {"messages": []}
