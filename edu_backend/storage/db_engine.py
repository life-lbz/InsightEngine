"""进程级数据库引擎单例，复用连接池。"""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from config.settings import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """返回进程级 SQLAlchemy 引擎单例，复用连接池参数。"""
    settings = get_settings()
    return create_engine(settings.mysql_sync_uri, **settings.mysql_engine_kwargs)
