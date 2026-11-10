"""标准化健康检查：检测 MySQL/Redis/Milvus 连通性、连接池状态、响应延迟。

用法（在 edu_backend 目录下）：
    python scripts/healthcheck.py          # 人类可读输出
    python scripts/healthcheck.py --json   # JSON 格式输出（供 K8s 探针使用）

也可在任意目录直接指定完整路径运行，脚本会自动定位项目根目录。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# 将项目根目录（edu_backend）加入模块搜索路径，支持直接运行脚本
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_settings


def check_mysql() -> dict[str, Any]:
    """检测 MySQL 连通性与连接池状态。

    返回：
        {"component": "mysql", "status": "healthy"|"unhealthy",
         "latency_ms": float, "pool_active": int, "pool_idle": int}
    """
    try:
        from sqlalchemy import text
        from storage.db_engine import get_engine
        engine = get_engine()
        start = time.perf_counter()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        pool = engine.pool
        return {
            "component": "mysql",
            "status": "healthy",
            "latency_ms": latency_ms,
            "pool_active": pool.checkedout(),
            "pool_idle": pool.checkedin(),
        }
    except Exception as exc:
        return {"component": "mysql", "status": "unhealthy", "error": str(exc)}


def check_redis() -> dict[str, Any]:
    """检测 Redis 连通性与延迟。

    返回：
        {"component": "redis", "status": "healthy"|"unhealthy", "latency_ms": float}
    """
    settings = get_settings()
    try:
        import redis
        client = redis.from_url(settings.redis_url, **settings.redis_pool_kwargs)
        start = time.perf_counter()
        client.ping()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        info = client.info(section="clients")
        return {
            "component": "redis",
            "status": "healthy",
            "latency_ms": latency_ms,
            "connected_clients": info.get("connected_clients", 0),
        }
    except Exception as exc:
        return {"component": "redis", "status": "unhealthy", "error": str(exc)}


def check_milvus() -> dict[str, Any]:
    """检测 Milvus 连通性与 Collection 列表。

    返回：
        {"component": "milvus", "status": "healthy"|"unhealthy",
         "latency_ms": float, "collection_count": int}
    """
    settings = get_settings()
    try:
        from pymilvus import MilvusClient
        client = MilvusClient(uri=settings.milvus_uri)
        start = time.perf_counter()
        collections = client.list_collections()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "component": "milvus",
            "status": "healthy",
            "latency_ms": latency_ms,
            "collection_count": len(collections),
            "collections": collections,
        }
    except Exception as exc:
        return {"component": "milvus", "status": "unhealthy", "error": str(exc)}


def run_healthcheck(as_json: bool = False) -> int:
    """执行全部健康检查。

    入参：
        as_json：是否输出 JSON 格式

    返回：
        0 表示全部健康，1 表示存在不健康组件
    """
    results = [check_mysql(), check_redis(), check_milvus()]

    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            status_icon = "✓" if r["status"] == "healthy" else "✗"
            print(f"  {status_icon} {r['component']}: {r['status']}", end="")
            if "latency_ms" in r:
                print(f"  ({r['latency_ms']}ms)", end="")
            if "error" in r:
                print(f"  error={r['error']}", end="")
            print()

    all_healthy = all(r["status"] == "healthy" for r in results)
    return 0 if all_healthy else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="教育答疑 RAG 系统健康检查")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()
    sys.exit(run_healthcheck(as_json=args.json))