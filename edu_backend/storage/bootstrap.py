"""MySQL Schema 初始化：支持版本化迁移。"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, text

from config.settings import get_settings

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent / "runtime_schema.sql"


def bootstrap_mysql_schema() -> None:
    """创建 MySQL 表结构。

    执行流程：
        1. 读取 runtime_schema.sql 中的 DDL 语句
        2. 按 ';' 分割逐条执行
        3. 幂等设计：CREATE TABLE IF NOT EXISTS 保证重复执行不报错

    边界条件：
        - 数据库不存在时先创建
        - 连接失败时抛出 RuntimeError
    """
    settings = get_settings()

    # 先连接到 MySQL 服务器（不指定数据库），确保目标数据库存在
    server_uri = (
        f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}"
        f"@{settings.mysql_host}:{settings.mysql_port}/?charset=utf8mb4"
    )
    server_engine = create_engine(server_uri, **settings.mysql_engine_kwargs)
    with server_engine.connect() as conn:
        conn.execute(text(
            f"CREATE DATABASE IF NOT EXISTS {settings.mysql_database} "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ))
        conn.commit()
    server_engine.dispose()

    # 连接到目标数据库
    engine = create_engine(
        settings.mysql_sync_uri,
        **settings.mysql_engine_kwargs,
    )

    sql_content = SCHEMA_PATH.read_text(encoding="utf-8")
    statements = [s.strip() for s in sql_content.split(";") if s.strip()]

    with engine.connect() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        conn.commit()

    logger.info(
        "MySQL schema initialized",
        extra={"database": settings.mysql_database, "statements": len(statements)},
    )

    _seed_default_users(engine)
    engine.dispose()


def _seed_default_users(engine) -> None:
    """如果 users 表为空，插入默认 admin 和 student 用户。"""
    import bcrypt

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
        if count and count > 0:
            return

        admin_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
        student_hash = bcrypt.hashpw(b"student123", bcrypt.gensalt()).decode()

        conn.execute(
            text(
                "INSERT INTO users (user_id, username, password_hash, role, "
                "course_ids, display_name, is_active) "
                "VALUES (:uid, :uname, :ph, :role, :cids, :dn, 1)"
            ),
            [
                {"uid": "admin-001", "uname": "admin", "ph": admin_hash,
                 "role": "admin", "cids": "default_course", "dn": "管理员"},
                {"uid": "student-001", "uname": "student", "ph": student_hash,
                 "role": "student", "cids": "default_course", "dn": "学员"},
            ],
        )
        conn.commit()
    logger.info("Default users seeded (admin, student)")


if __name__ == "__main__":
    bootstrap_mysql_schema()