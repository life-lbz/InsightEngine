#!/usr/bin/env python3
"""标准化健康检查脚本。

检查项：
    1. API 进程存活（/health 端点）
    2. MySQL 连通性
    3. Redis 连通性
    4. Milvus 连通性

退出码：
    0: 全部健康
    1: 部分不健康（但不影响核心功能）
    2: 核心依赖不健康（MySQL/Redis/Milvus 不可用）
"""
from __future__ import annotations

import os
import sys

import redis
import requests
from sqlalchemy import create_engine, text


def check_api() -> bool:
    """检查 API 进程存活。"""
    try:
        resp = requests.get("http://localhost:8000/health", timeout=3)
        return resp.status_code == 200 and resp.json().get("status") == "healthy"
    except Exception:
        return False


def check_mysql() -> bool:
    """检查 MySQL 连通性。"""
    try:
        engine = create_engine(
            f"mysql+pymysql://{os.environ.get('MYSQL_USER', 'root')}:"
            f"{os.environ.get('MYSQL_PASSWORD', '')}@"
            f"{os.environ.get('MYSQL_HOST', 'localhost')}:"
            f"{os.environ.get('MYSQL_PORT', '3306')}/insight_engine"
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def check_redis() -> bool:
    """检查 Redis 连通性。"""
    try:
        client = redis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        )
        client.ping()
        return True
    except Exception:
        return False


def check_milvus() -> bool:
    """检查 Milvus 连通性。"""
    try:
        from pymilvus import connections, utility
        connections.connect(
            alias="default",
            uri=os.environ.get("MILVUS_URI", "http://localhost:19530"),
        )
        utility.list_collections()
        return True
    except Exception:
        return False


def main() -> int:
    checks = {
        "api": check_api(),
        "mysql": check_mysql(),
        "redis": check_redis(),
        "milvus": check_milvus(),
    }

    all_healthy = all(checks.values())
    core_healthy = checks["mysql"] and checks["redis"] and checks["milvus"]

    for name, healthy in checks.items():
        status = "OK" if healthy else "FAIL"
        print(f"  {name}: {status}")

    if all_healthy:
        print("全部健康")
        return 0
    elif core_healthy:
        print("核心依赖健康，部分非核心组件不可用")
        return 1
    else:
        print("核心依赖不可用")
        return 2


if __name__ == "__main__":
    sys.exit(main())