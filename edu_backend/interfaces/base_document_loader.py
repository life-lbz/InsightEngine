"""文档加载抽象接口（生产级增强：扩展名声明 + 路径校验）。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.documents import Document


class BaseDocumentLoader(ABC):
    """所有 Loader 实现必须继承。

    生产级增强：
        - supported_extensions：声明支持的文件扩展名，供注册表校验
        - validate_path：路径安全校验（防止路径穿越）
    """

    @property
    def supported_extensions(self) -> list[str]:
        """返回支持的文件扩展名列表。"""
        return []

    @abstractmethod
    def load(self, path: str) -> list[Document]:
        """加载文件。

        入参：
            path：文件路径

        返回：
            Document 列表
        """

    def validate_path(self, path: str) -> bool:
        """校验文件路径安全性。

        入参：
            path：文件路径

        返回：
            是否安全（不含 .. 穿越符号，扩展名受支持）
        """
        from pathlib import Path

        p = Path(path).resolve()
        if ".." in str(p):
            return False
        if self.supported_extensions:
            return p.suffix.lower() in self.supported_extensions
        return True
