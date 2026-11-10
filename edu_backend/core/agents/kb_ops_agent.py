"""知识库运维 Agent（管理端）：挖掘高频未解决问题、辅助 FAQ 维护。"""
from __future__ import annotations

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from llm.rate_limiter import get_llm_semaphore
from llm.resilient_client import get_resilient_llm
from storage.async_db import run_sql

KB_OPS_SYSTEM_PROMPT = """你是知识库运维专家，面向管理端。负责知识库健康监控与自动补全。

工作流程：
1. 调用 mine_unresolved_questions 挖掘高频未解决问题
2. 调用 suggest_faq 用 LLM 为高频问题生成 FAQ 候选
3. 调用 get_kb_status 查看知识库版本与入库进度
4. 调用 trigger_ingestion 触发数据入库

约束：
- FAQ 候选必须人工审核后才能入库（写入 faq_candidates 表，status=pending_review）
- 使用中文
"""

_UNRESOLVED_SQL = """
    SELECT question, COUNT(*) AS cnt
    FROM qa_feedback
    WHERE course_id = :cid
    GROUP BY question
    ORDER BY cnt DESC
    LIMIT :n
"""

_KB_STATUS_SQL = """
    SELECT course_id, kb_version, status, version_seq, updated_at
    FROM kb_versions
    WHERE course_id = :cid AND is_deleted = 0
    ORDER BY version_seq DESC
"""

_INGESTION_STATUS_SQL = """
    SELECT status, COUNT(*) AS cnt
    FROM ingestion_progress
    WHERE kb_version = :kv
    GROUP BY status
"""

_SUGGEST_FAQ_SQL = """
    INSERT INTO faq_candidates
        (course_id, question, suggested_answer, source, status, created_at)
    VALUES (:cid, :q, :a, 'agent_suggested', 'pending_review', NOW())
"""


@tool
async def mine_unresolved_questions(course_id: str, limit: int = 10) -> list[dict]:
    """挖掘高频未解决问题（按 qa_feedback 聚合）。"""
    try:
        return await run_sql(_UNRESOLVED_SQL, {"cid": course_id, "n": limit})
    except Exception:
        return []


@tool
async def suggest_faq(course_id: str, question: str) -> dict:
    """用 LLM 为高频问题生成 FAQ 候选（写入 faq_candidates 待审核）。"""
    llm = get_resilient_llm()
    async with get_llm_semaphore():
        resp = await llm.agenerate([{
            "role": "user",
            "content": f"为以下教育问题生成一条 FAQ 答案（简洁准确）：\n{question}",
        }])
    answer = getattr(resp, "content", str(resp))
    try:
        await run_sql(
            _SUGGEST_FAQ_SQL,
            {"cid": course_id, "q": question, "a": answer},
            write=True,
        )
    except Exception:
        pass
    return {"question": question, "suggested_answer": answer, "status": "pending_review"}


@tool
async def get_kb_status(course_id: str, kb_version: str = "") -> dict:
    """查看知识库版本与入库进度。"""
    versions = await run_sql(_KB_STATUS_SQL, {"cid": course_id})
    ingestion: list[dict] = []
    kv = kb_version or (versions[0]["kb_version"] if versions else "")
    if kv:
        try:
            ingestion = await run_sql(_INGESTION_STATUS_SQL, {"kv": kv})
        except Exception:
            pass
    return {"versions": versions, "ingestion_status": ingestion}


@tool
async def trigger_ingestion(
    course_id: str,
    kb_version: str,
    input_dir: str,
    mode: str = "full",
) -> dict:
    """触发数据入库（复用 ingestion.service，异步不阻塞）。"""
    from pathlib import Path

    from ingestion.service import run_ingestion_background

    try:
        result = await run_ingestion_background(
            Path(input_dir), course_id, kb_version, mode
        )
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": f"ingestion_failed: {e}"}


def build_kb_ops_agent():
    """构建知识库运维 Agent。"""
    llm = get_resilient_llm().get_chat_model()
    return create_react_agent(
        model=llm,
        tools=[mine_unresolved_questions, suggest_faq, get_kb_status, trigger_ingestion],
        prompt=KB_OPS_SYSTEM_PROMPT,
        name="kb_ops_agent",
    )
