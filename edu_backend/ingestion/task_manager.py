"""异步入库任务管理器：在后台执行入库，通过 task_id 查询进度。"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from observability.logger import get_logger

logger = get_logger(__name__)

_tasks: dict[str, dict[str, Any]] = {}


def create_task(kb_version: str, mode: str) -> str:
    task_id = uuid.uuid4().hex[:12]
    _tasks[task_id] = {
        "task_id": task_id,
        "kb_version": kb_version,
        "mode": mode,
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": time.time(),
        "finished_at": None,
    }
    return task_id


def get_task(task_id: str) -> dict[str, Any] | None:
    return _tasks.get(task_id)


def list_tasks() -> list[dict[str, Any]]:
    return sorted(
        _tasks.values(), key=lambda t: t["created_at"], reverse=True
    )


def _running_count() -> int:
    return sum(1 for t in _tasks.values() if t["status"] == "running")


def has_running_task() -> bool:
    """是否存在正在执行中的入库任务。"""
    return _running_count() > 0


async def run_task(
    task_id: str,
    input_dir,
    course_id: str,
    kb_version: str,
    mode: str,
) -> None:
    task = _tasks[task_id]
    task["status"] = "running"
    task["started_at"] = time.time()
    logger.info("ingestion_task_started", task_id=task_id, mode=mode)

    try:
        from ingestion.service import (
            run_full_ingestion,
            run_incremental_ingestion,
        )

        loop = asyncio.get_event_loop()
        if mode == "incremental":
            result = await loop.run_in_executor(
                None, run_incremental_ingestion, input_dir, kb_version
            )
        else:
            result = await loop.run_in_executor(
                None, run_full_ingestion, input_dir, course_id, kb_version
            )

        task["status"] = "completed"
        task["result"] = result
        task["finished_at"] = time.time()
        logger.info(
            "ingestion_task_completed",
            task_id=task_id,
            success=result.get("success", 0),
            failed=result.get("failed", 0),
        )
    except Exception as exc:
        task["status"] = "failed"
        task["error"] = str(exc)[:500]
        task["finished_at"] = time.time()
        logger.error("ingestion_task_failed", task_id=task_id, error=str(exc))


def cleanup_old_tasks(max_age_seconds: int = 3600) -> None:
    now = time.time()
    expired = [
        tid
        for tid, t in _tasks.items()
        if t.get("finished_at") and now - t["finished_at"] > max_age_seconds
    ]
    for tid in expired:
        _tasks.pop(tid, None)
