"""异步 DB 访问：把同步 SQLAlchemy 调用包到线程池，避免阻塞事件循环。

Agent 工具运行在 async 上下文中，但项目 DB 层（storage.db_engine.get_engine）
返回同步 Engine。直接调用会阻塞事件循环，导致 WebSocket 全线卡死。
本模块用 anyio.to_thread.run_sync 将同步查询/写入委托到线程池。
"""
from __future__ import annotations

from typing import Any

from anyio import to_thread
from sqlalchemy import text
from sqlalchemy.engine import Engine

from storage.db_engine import get_engine


def _exec_read(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    engine: Engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params or {}).mappings().all()
        return [dict(r) for r in rows]


def _exec_write(sql: str, params: dict[str, Any] | None = None) -> int:
    engine: Engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(text(sql), params or {})
        return result.rowcount


async def run_sql(
    sql: str,
    params: dict[str, Any] | None = None,
    *,
    write: bool = False,
) -> list[dict[str, Any]] | int:
    """异步执行 SQL（在线程池运行同步 SQLAlchemy）。

    write=False：返回 list[dict]（行集）
    write=True：返回受影响行数 int
    """
    if write:
        return await to_thread.run_sync(lambda: _exec_write(sql, params))
    return await to_thread.run_sync(lambda: _exec_read(sql, params))


async def run_sql_one(
    sql: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """异步查询单行：返回首行 dict 或 None。"""
    rows = await run_sql(sql, params, write=False)
    return rows[0] if rows else None
