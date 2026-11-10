"""组件工厂（生产级增强：配置校验 + 健康探测）。"""
from __future__ import annotations

from typing import Any

from factory.registry import (
    llm_registry,
    loader_registry,
    vector_store_registry,
)
from observability.logger import get_logger

logger = get_logger(__name__)

# 触发插件注册（import 即注册），使用 try-except 防止单个插件依赖缺失导致整体不可用
import importlib

def _load_plugin(module_path: str) -> None:
    try:
        importlib.import_module(module_path)
    except ImportError as e:
        logger.warning("plugin_load_failed", module=module_path, error=str(e))

_load_plugin("plugins.milvus.adapter")
_load_plugin("plugins.qdrant.adapter")
_load_plugin("plugins.openai.adapter")
_load_plugin("plugins.native.adapter")


def _validate_config(
    registry,
    component_type: str,
    key: str,
    config: dict,
) -> None:
    """校验组件配置是否符合注册时声明的 Schema。

    入参：
        registry：注册表实例
        component_type：组件类型（vector_store/llm/loader）
        key：组件标识
        config：配置字典

    异常：
        ValueError：配置不符合 Schema
    """
    schema = registry.get_schema(key)
    if not schema:
        return

    # 简化的 Schema 校验：检查 required 字段
    for field in schema.get("required", []):
        if field not in config:
            raise ValueError(
                f"{component_type} '{key}' 配置缺少必填字段：{field}"
            )


def create_vector_store(config: dict) -> BaseVectorStore:
    """创建向量存储实例。

    入参：
        config：顶层配置字典，需包含 vector_store.type 和相关参数

    返回：
        BaseVectorStore 实例

    异常：
        KeyError：未注册的向量库类型
        ValueError：配置校验失败
    """
    vs_config = config["vector_store"]
    vs_type = vs_config["type"]

    _validate_config(vector_store_registry, "vector_store", vs_type, vs_config)

    cls = vector_store_registry.get(vs_type)
    instance = cls(vs_config)
    logger.info("vector_store_created", vs_type=vs_type)
    return instance


def create_llm(config: dict) -> BaseLLM:
    """创建 LLM 实例。

    入参：
        config：顶层配置字典，需包含 llm.type 和相关参数

    返回：
        BaseLLM 实例
    """
    llm_config = config["llm"]
    llm_type = llm_config["type"]

    _validate_config(llm_registry, "llm", llm_type, llm_config)

    cls = llm_registry.get(llm_type)
    instance = cls(llm_config)
    logger.info("llm_created", llm_type=llm_type)
    return instance


def create_loader(config: dict) -> BaseDocumentLoader:
    """创建文档加载器实例。

    入参：
        config：顶层配置字典，需包含 loader.type

    返回：
        BaseDocumentLoader 实例
    """
    loader_config = config.get("loader", {})
    loader_type = loader_config.get("type", "native")

    _validate_config(loader_registry, "loader", loader_type, loader_config)

    cls = loader_registry.get(loader_type)
    instance = cls(loader_config)
    logger.info("loader_created", loader_type=loader_type)
    return instance


def health_check_all(config: dict) -> dict[str, Any]:
    """对所有配置的组件执行健康检查。

    入参：
        config：顶层配置字典

    返回：
        {
            "vector_store": {"healthy": bool, "latency_ms": int, ...},
            "llm": {"healthy": bool, "latency_ms": int, ...},
            "overall": bool,
        }
    """
    results: dict[str, Any] = {}

    try:
        vs = create_vector_store(config)
        results["vector_store"] = vs.health_check()
    except Exception as exc:
        results["vector_store"] = {"healthy": False, "error": str(exc)}

    try:
        llm = create_llm(config)
        results["llm"] = llm.health_check()
    except Exception as exc:
        results["llm"] = {"healthy": False, "error": str(exc)}

    results["overall"] = all(
        r.get("healthy", False) for r in results.values() if isinstance(r, dict)
    )

    return results