"""调试路由：开发辅助端点。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import require_admin_auth
from config.settings import get_settings

router = APIRouter()


@router.get("/debug/config")
async def debug_config(user=Depends(require_admin_auth)):
    """调试配置端点：仅管理员可访问（暴露数据库/向量库/LLM 连接信息）。"""
    settings = get_settings()
    return {
        "app_env": settings.app_env,
        "mysql_host": settings.mysql_host,
        "mysql_port": settings.mysql_port,
        "mysql_database": settings.mysql_database,
        "redis_host": settings.redis_host,
        "redis_port": settings.redis_port,
        "milvus_uri": settings.milvus_uri,
        "llm_model": settings.llm_model,
        "llm_base_url": settings.llm_base_url,
        "embedding_model_path": settings.embedding_model_path,
        "reranker_model_path": settings.reranker_model_path,
        "cache_enabled": settings.cache_enabled,
        "is_production": settings.is_production,
    }


@router.get("/debug/ping")
async def ping():
    return {"pong": True}
