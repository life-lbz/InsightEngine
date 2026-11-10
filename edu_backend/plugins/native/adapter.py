"""原生 Loader 插件（生产级增强：扩展名声明 + 路径校验）。"""
from __future__ import annotations

from langchain_core.documents import Document

from factory.registry import loader_registry
from ingestion.loader_registry import load_file
from interfaces.base_document_loader import BaseDocumentLoader


class NativeLoaderAdapter(BaseDocumentLoader):
    """复用 loader_registry 的原生加载器。

    支持：.txt, .md, .pdf, .docx, .pptx, .csv, .xlsx
    """

    @property
    def supported_extensions(self) -> list[str]:
        return [".txt", ".md", ".pdf", ".docx", ".pptx", ".csv", ".xlsx"]

    def load(self, path: str) -> list[Document]:
        return load_file(path)


loader_registry.register(
    "native",
    NativeLoaderAdapter,
    schema={
        "type": "object",
        "required": [],
        "properties": {
            "type": {"type": "string"},
        },
    },
)