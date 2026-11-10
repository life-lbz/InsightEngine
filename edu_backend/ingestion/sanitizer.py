"""内容脱敏器：正则替换手机号、身份证号、邮箱等敏感信息。"""
from __future__ import annotations

import re


# 敏感信息正则模式
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # 手机号：1[3-9]开头的 11 位数字
    ("phone", re.compile(r"1[3-9]\d{9}")),
    # 身份证号：18 位（最后一位可能是 X）
    ("id_card", re.compile(r"\d{17}[\dXx]")),
    # 邮箱地址
    ("email", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    # QQ 号：5-12 位纯数字（以防止误匹配，要求前后非数字）
    ("qq", re.compile(r"(?<!\d)[1-9]\d{4,11}(?!\d)")),
]

# 各类型对应的替换文本
REPLACEMENTS: dict[str, str] = {
    "phone": "***",
    "id_card": "****",
    "email": "***@***",
    "qq": "***",
}


def sanitize_text(text: str) -> str:
    """脱敏文本中的敏感信息。

    入参：
        text：原始文本

    返回：
        脱敏后的文本

    边界条件：
        - 空字符串直接返回
        - 仅替换匹配到的部分，保留其余内容不变
    """
    if not text:
        return text

    result = text
    for pattern_name, pattern in PATTERNS:
        replacement = REPLACEMENTS.get(pattern_name, "***")
        result = pattern.sub(replacement, result)

    return result


def sanitize_chunks(
    chunks: list[dict[str, str]],
    content_key: str = "text",
) -> list[dict[str, str]]:
    """批量脱敏 chunk 内容。

    入参：
        chunks：chunk 字典列表
        content_key：内容字段名

    返回：
        内容已脱敏的 chunk 列表
    """
    sanitized: list[dict[str, str]] = []
    for chunk in chunks:
        new_chunk = dict(chunk)
        if content_key in new_chunk:
            new_chunk[content_key] = sanitize_text(new_chunk[content_key])
        sanitized.append(new_chunk)
    return sanitized