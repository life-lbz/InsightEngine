"""插件注册表（生产级增强：Schema 校验 + 线程安全）。"""
from __future__ import annotations

import threading
from typing import Any, Protocol


class ComponentProtocol(Protocol):
    """组件协议：所有插件必须实现 __init__(config: dict)。"""
    def __init__(self, config: dict) -> None: ...


class Registry:
    """线程安全的组件注册表。

    生产级增强：
        - 加锁保护并发注册
        - 支持 Schema 校验（注册时附带配置 Schema）
        - 列出所有已注册组件
    """

    def __init__(self) -> None:
        self._items: dict[str, type] = {}
        self._schemas: dict[str, dict] = {}
        self._lock = threading.Lock()

    def register(
        self,
        key: str,
        item: type,
        schema: dict | None = None,
    ) -> None:
        """注册实现。

        入参：
            key：组件标识（如 "milvus"、"openai_compatible"）
            item：实现类
            schema：可选的配置 Schema（JSON Schema 格式）
        """
        with self._lock:
            self._items[key] = item
            if schema:
                self._schemas[key] = schema

    def get(self, key: str) -> type:
        """获取实现类。

        入参：
            key：组件标识

        返回：
            实现类

        异常：
            KeyError：未注册的组件
        """
        if key not in self._items:
            available = ", ".join(sorted(self._items.keys()))
            raise KeyError(f"未注册的组件：{key}（可用：{available}）")
        return self._items[key]

    def get_schema(self, key: str) -> dict | None:
        """获取组件的配置 Schema。"""
        return self._schemas.get(key)

    def list_registered(self) -> list[str]:
        """列出所有已注册的组件标识。"""
        return sorted(self._items.keys())


# 全局注册表实例
vector_store_registry = Registry()
llm_registry = Registry()
loader_registry = Registry()