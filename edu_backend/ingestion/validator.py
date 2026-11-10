"""数据前置校验器：入库前校验文件完整性与字段规范。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ValidationResult:
    """校验结果。

    属性：
        valid：是否通过校验
        errors：错误信息列表
        warnings：告警信息列表
    """

    valid: bool
    errors: list[str]
    warnings: list[str]


# 各 Loader 对应的必填列定义
REQUIRED_COLUMNS: dict[str, list[str]] = {
    "question": ["question"],
    "faq": ["question", "answer"],
    "course": ["chapter_id", "course_id", "title"],
}

# 允许的文件后缀白名单
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({
    ".md", ".txt", ".pdf", ".docx", ".pptx", ".csv", ".xlsx",
})


def validate_file_type(file_path: Path) -> ValidationResult:
    """校验文件类型是否在白名单内。

    入参：
        file_path：文件路径

    返回：
        ValidationResult：校验结果
    """
    errors: list[str] = []
    warnings: list[str] = []

    ext = file_path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(
            f"文件类型 {ext} 不在白名单 {sorted(ALLOWED_EXTENSIONS)} 中"
        )

    if not file_path.exists():
        errors.append(f"文件不存在: {file_path}")
    elif file_path.stat().st_size == 0:
        errors.append(f"文件大小为 0: {file_path}")

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


def validate_table_columns(
    rows: list[dict[str, Any]],
    loader_type: str,
    file_path: str,
) -> ValidationResult:
    """校验表格数据的必填列是否存在。

    入参：
        rows：解析后的行数据（字典列表）
        loader_type：Loader 类型（question/faq/course）
        file_path：文件路径（用于错误信息）

    返回：
        ValidationResult：校验结果
    """
    errors: list[str] = []
    warnings: list[str] = []

    required = REQUIRED_COLUMNS.get(loader_type, [])
    if not required:
        return ValidationResult(valid=True, errors=[], warnings=[])

    if not rows:
        errors.append(f"[{file_path}] 数据为空，无行记录")
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    actual_columns = set(rows[0].keys())
    for col in required:
        if col not in actual_columns:
            errors.append(f"[{file_path}] 缺少必填列: '{col}'（实际列: {sorted(actual_columns)}）")

    # 告警：存在空值行
    empty_count = sum(
        1 for row in rows
        if any(not str(row.get(col, "")).strip() for col in required)
    )
    if empty_count > 0:
        warnings.append(f"[{file_path}] {empty_count} 行存在必填列为空")

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


def validate_chunk_content(
    text: str,
    min_chars: int = 20,
) -> ValidationResult:
    """校验单个 chunk 内容质量。

    入参：
        text：chunk 文本内容
        min_chars：最小字符数

    返回：
        ValidationResult：校验结果
    """
    errors: list[str] = []
    warnings: list[str] = []

    stripped = text.strip()

    if len(stripped) == 0:
        errors.append("chunk 内容为空")
    elif len(stripped) < min_chars:
        warnings.append(f"chunk 内容过短（{len(stripped)} 字符 < {min_chars}）")

    # 检测纯符号/空白
    if stripped and not any(c.isalnum() for c in stripped):
        errors.append("chunk 内容为纯符号/空白，无有效字符")

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)