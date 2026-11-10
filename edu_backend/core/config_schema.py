"""插件配置 Schema 声明（新增）。"""
from __future__ import annotations

# 各组件类型的配置 Schema（JSON Schema 简化版）
COMPONENT_SCHEMAS: dict[str, dict[str, dict]] = {
    "vector_store": {
        "milvus": {
            "type": "object",
            "required": ["type", "uri", "collection_name"],
            "properties": {
                "type": {"type": "string"},
                "uri": {"type": "string"},
                "collection_name": {"type": "string"},
                "username": {"type": "string"},
                "password": {"type": "string"},
            },
        },
        "qdrant": {
            "type": "object",
            "required": ["type", "collection_name"],
            "properties": {
                "type": {"type": "string"},
                "uri": {"type": "string"},
                "collection_name": {"type": "string"},
            },
        },
    },
    "llm": {
        "openai_compatible": {
            "type": "object",
            "required": ["type", "model", "api_key", "base_url"],
            "properties": {
                "type": {"type": "string"},
                "model": {"type": "string"},
                "api_key": {"type": "string"},
                "base_url": {"type": "string"},
                "temperature": {"type": "number"},
                "max_tokens": {"type": "integer"},
                "timeout": {"type": "integer"},
                "max_retries": {"type": "integer"},
            },
        },
    },
    "loader": {
        "native": {
            "type": "object",
            "required": [],
            "properties": {
                "type": {"type": "string"},
            },
        },
    },
}


def get_schema(component_type: str, plugin_name: str) -> dict | None:
    """获取指定插件类型的配置 Schema。

    入参：
        component_type：组件类型（vector_store/llm/loader）
        plugin_name：插件标识

    返回：
        JSON Schema 字典，不存在则返回 None
    """
    return COMPONENT_SCHEMAS.get(component_type, {}).get(plugin_name)