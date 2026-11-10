"""Agent 协作路由：多 Agent 协作入口（WebSocket + HTTP）。

与 chat_router 的 /stream 并存，通过 settings.enable_agent_collab 灰度。
消息格式与 /stream 保持一致（type=status/start/end/error），前端可复用。
Agent 协作异常时自动回退 RagPipeline 直答，保证学员不中断。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from api.auth import require_student_auth, verify_token
from config.settings import get_settings
from observability.logger import get_logger
from observability.metrics import websocket_active_connections
from pipeline.agent_guardrails import output_guard

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/agent/stream")
async def agent_stream(ws: WebSocket, token: str = Query(default="")):
    """Agent 协作流式入口（WebSocket）。"""
    settings = get_settings()
    if not settings.enable_agent_collab:
        await ws.close(code=4403, reason="Agent 协作未启用")
        return

    try:
        payload = verify_token(token)
    except Exception:
        await ws.close(code=4401, reason="认证失败")
        return

    role = payload.get("role", "student") if isinstance(payload, dict) else "student"
    user_id = payload.get("sub", "") if isinstance(payload, dict) else ""

    await ws.accept()
    websocket_active_connections.inc()
    try:
        await ws.send_json(
            {"type": "status", "stage": "ready", "message": "Agent 协作已连接"}
        )
        while True:
            data = await ws.receive_json()
            if data.get("type") == "ping":
                await ws.send_json({"type": "pong"})
                continue
            if data.get("type") != "query":
                continue

            question = data.get("question", "")
            session_id = data.get("session_id", "")
            course_id = data.get("course_id", settings.default_course_id)

            await ws.send_json({"type": "start", "trace_id": session_id})
            await ws.send_json(
                {"type": "status", "stage": "thinking", "message": "Agent 协作处理中"}
            )

            try:
                from core.agent_engine import agent_answer

                result = await agent_answer(
                    question=question,
                    role=role,
                    course_id=course_id,
                    session_id=session_id,
                    user_id=user_id,
                )
                answer = result.get("answer", "")
                if settings.agent_enable_output_guard and answer:
                    answer = await output_guard(
                        answer, result.get("sources"), course_id
                    )
                await ws.send_json(
                    {
                        "type": "end",
                        "answer": answer,
                        "sources": result.get("sources", []),
                        "intent": result.get("intent", ""),
                        "degraded": False,
                    }
                )
                try:
                    from memory.history import ChatHistoryStore

                    store = ChatHistoryStore()
                    store.save_message(session_id, "user", question, user_id=user_id)
                    store.save_message(session_id, "assistant", answer, user_id=user_id)
                except Exception as exc:
                    logger.warning("agent_history_save_failed", error=str(exc)[:100])
            except Exception as exc:
                logger.error("agent_stream_failed", error=str(exc))
                await _fallback_to_rag(ws, question, course_id, session_id)
    except WebSocketDisconnect:
        pass
    finally:
        websocket_active_connections.dec()


async def _fallback_to_rag(
    ws: WebSocket, question: str, course_id: str, session_id: str
) -> None:
    """Agent 协作失败时回退 RagPipeline 直答。"""
    try:
        from core.rag_engine import get_rag_pipeline

        pipeline = get_rag_pipeline()
        result = await pipeline.answer(
            question=question, course_id=course_id, session_id=session_id
        )
        await ws.send_json(
            {
                "type": "end",
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "degraded": True,
            }
        )
        await ws.send_json({"type": "fallback", "reason": "agent_failed"})
    except Exception as e2:
        await ws.send_json({"type": "error", "error": f"Agent 与兜底均失败：{e2}"})


@router.post("/agent/chat")
async def agent_chat(req: dict, user=Depends(require_student_auth)) -> dict[str, Any]:
    """HTTP 版 Agent 协作（非流式，便于调试）。"""
    settings = get_settings()
    if not settings.enable_agent_collab:
        return {"error": "Agent 协作未启用"}
    from core.agent_engine import agent_answer

    # require_student_auth 返回 dict，需按键读取（此前 getattr 恒取默认值导致角色透传失败）
    user_info = user if isinstance(user, dict) else {}
    return await agent_answer(
        question=req.get("question", ""),
        role=user_info.get("role", "student"),
        course_id=req.get("course_id", settings.default_course_id),
        session_id=req.get("session_id", ""),
        user_id=user_info.get("user_id", ""),
    )
