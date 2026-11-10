"""答疑 Agent：调用现有 RagPipeline 检索知识库并回答。

保留 RagPipeline 线性管道不动，作为答疑 Agent 的底层工具被调用。
"""
from __future__ import annotations

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from llm.resilient_client import get_resilient_llm

QA_SYSTEM_PROMPT = """你是在线教育智能答疑助手。你的任务是调用 rag_answer 工具检索知识库并回答学员问题。

工作流程：
1. 调用 rag_answer 工具，传入学员问题、course_id、session_id
2. 工具返回包含 answer、sources、confidence、ok 字段的结构化结果
3. 若 ok=True，基于 answer 组织自然语言回复，并标注来源
4. 若 ok=False，礼貌告知答疑服务暂不可用，建议稍后重试

约束：
- 必须调用工具获取知识库依据，不得凭空作答
- 回复使用中文，语气友好专业
"""


@tool
async def rag_answer(question: str, course_id: str, session_id: str = "") -> dict:
    """检索知识库并回答学员问题。

    Args:
        question: 学员的问题
        course_id: 课程 ID
        session_id: 会话 ID（用于历史上下文）

    Returns:
        包含 answer/sources/confidence/ok 的字典；失败时 ok=False
    """
    from core.rag_engine import get_rag_pipeline

    try:
        pipeline = get_rag_pipeline()
        result = await pipeline.answer(
            question=question, course_id=course_id, session_id=session_id
        )
        return {
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "confidence": result.get("confidence", 0.5),
            "ok": True,
        }
    except Exception as e:
        return {
            "answer": "",
            "ok": False,
            "error": f"rag_unavailable: {type(e).__name__}: {e}",
        }


def build_qa_agent():
    """构建答疑 Agent（create_react_agent）。"""
    llm = get_resilient_llm().get_chat_model()
    return create_react_agent(
        model=llm,
        tools=[rag_answer],
        prompt=QA_SYSTEM_PROMPT,
        name="qa_agent",
    )
