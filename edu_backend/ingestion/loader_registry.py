"""文档加载器注册表：按扩展名分派 Loader。

每个 Loader 实现 load(file_path) -> list[dict[str, str]]，
返回的 chunk 字典至少包含 "text" 键。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from config.settings import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)


class DocumentLoader(Protocol):
    """文档加载器协议。"""

    def load(self, file_path: Path) -> list[dict[str, Any]]:
        ...


def _split_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """按长度切分文本，带重叠。"""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
        if start >= len(text):
            break
    return chunks


class TextLoader:
    """加载 .md / .txt 文本文件。"""

    def load(self, file_path: Path) -> list[dict[str, Any]]:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        settings = get_settings()
        parts = _split_text(
            text,
            chunk_size=settings.parent_chunk_size,
            overlap=settings.parent_overlap,
        )
        return [
            {"text": p, "source": str(file_path), "file_path": str(file_path)}
            for p in parts
        ]


class PDFLoader:
    """加载 .pdf 文件（使用 PyMuPDF）。"""

    def load(self, file_path: Path) -> list[dict[str, Any]]:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("pymupdf_not_installed", file=str(file_path))
            raise ImportError("PDF 加载需要 PyMuPDF：pip install pymupdf")

        chunks: list[dict[str, Any]] = []
        settings = get_settings()
        doc = fitz.open(str(file_path))
        for page_num in range(len(doc)):
            text = doc[page_num].get_text("text")
            if not text.strip():
                continue
            parts = _split_text(
                text,
                chunk_size=settings.parent_chunk_size,
                overlap=settings.parent_overlap,
            )
            for i, part in enumerate(parts):
                chunks.append({
                    "text": part,
                    "source": str(file_path),
                    "file_path": str(file_path),
                    "page": page_num + 1,
                    "chunk_index": i,
                })
        doc.close()
        return chunks


class DocxLoader:
    """加载 .docx 文件（使用 python-docx）。"""

    def load(self, file_path: Path) -> list[dict[str, Any]]:
        try:
            import docx
        except ImportError:
            raise ImportError("DOCX 加载需要 python-docx：pip install python-docx")

        doc = docx.Document(str(file_path))
        full_text = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        settings = get_settings()
        parts = _split_text(
            full_text,
            chunk_size=settings.parent_chunk_size,
            overlap=settings.parent_overlap,
        )
        return [
            {"text": p, "source": str(file_path), "file_path": str(file_path)}
            for p in parts
        ]


class PptxLoader:
    """加载 .pptx 文件（使用 python-pptx）。"""

    def load(self, file_path: Path) -> list[dict[str, Any]]:
        try:
            from pptx import Presentation
        except ImportError:
            raise ImportError("PPTX 加载需要 python-pptx：pip install python-pptx")

        prs = Presentation(str(file_path))
        chunks: list[dict[str, Any]] = []
        for slide_num, slide in enumerate(prs.slides, 1):
            texts: list[str] = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    texts.append(shape.text.strip())
            if texts:
                text = "\n".join(texts)
                chunks.append({
                    "text": text,
                    "source": str(file_path),
                    "file_path": str(file_path),
                    "page": slide_num,
                })
        return chunks


class CSVLoader:
    """加载 .csv 文件。"""

    def load(self, file_path: Path) -> list[dict[str, Any]]:
        import csv

        chunks: list[dict[str, Any]] = []
        with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                text = "\n".join(f"{k}: {v}" for k, v in row.items() if v)
                if text.strip():
                    chunks.append({
                        "text": text,
                        "source": str(file_path),
                        "file_path": str(file_path),
                    })
        return chunks


class ExcelLoader:
    """加载 .xlsx 文件（使用 openpyxl）。"""

    def load(self, file_path: Path) -> list[dict[str, Any]]:
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise ImportError("Excel 加载需要 openpyxl：pip install openpyxl")

        wb = load_workbook(str(file_path), read_only=True, data_only=True)
        chunks: list[dict[str, Any]] = []
        for ws in wb.worksheets:
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue
            headers = [str(h) if h else f"col_{i}" for i, h in enumerate(rows[0])]
            for row in rows[1:]:
                text = "\n".join(
                    f"{headers[i]}: {v}"
                    for i, v in enumerate(row)
                    if v is not None
                )
                if text.strip():
                    chunks.append({
                        "text": text,
                        "source": str(file_path),
                        "file_path": str(file_path),
                        "sheet": ws.title,
                    })
        wb.close()
        return chunks


_LOADERS: dict[str, DocumentLoader] = {}


def _init_loaders() -> None:
    global _LOADERS
    if _LOADERS:
        return
    _LOADERS = {
        ".md": TextLoader(),
        ".txt": TextLoader(),
        ".pdf": PDFLoader(),
        ".docx": DocxLoader(),
        ".pptx": PptxLoader(),
        ".csv": CSVLoader(),
        ".xlsx": ExcelLoader(),
    }


def get_loader(suffix: str) -> DocumentLoader | None:
    """按文件扩展名获取 Loader。

    入参：
        suffix：文件后缀（小写，含点号，如 ".pdf"）

    返回：
        Loader 实例，无匹配时返回 None
    """
    _init_loaders()
    return _LOADERS.get(suffix)
