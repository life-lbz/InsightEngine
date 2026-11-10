"""Milvus 过滤表达式构建（生产级增强：注入防护）。"""
from __future__ import annotations

import re

from retrieval.course_scope import CourseScope


# Milvus 表达式关键字黑名单
EXPR_KEYWORDS = {
    "and", "or", "not", "in", "like", "exists",
    "AND", "OR", "NOT", "IN", "LIKE", "EXISTS",
}

# 安全字符模式：仅允许字母、数字、下划线、连字符
SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def escape_expr_value(value: str) -> str:
    """转义 Milvus 表达式中的字符串值，防止注入。

    入参：
        value：待转义的值

    返回：
        转义后的安全字符串（用双引号包裹）

    异常：
        ValueError：当值包含表达式关键字或非法字符时
    """
    if not value:
        raise ValueError("过滤表达式值不能为空")

    # 检查是否包含表达式关键字
    words_in_value = set(re.findall(r"\w+", value))
    dangerous = words_in_value & EXPR_KEYWORDS
    if dangerous:
        raise ValueError(
            f"过滤表达式值包含非法关键字: {dangerous}，疑似注入攻击"
        )

    # 转义双引号
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def validate_id_field(value: str, field_name: str) -> str:
    """校验 ID 类型字段（course_id、chapter_id、point_id）。

    入参：
        value：字段值
        field_name：字段名称（用于错误信息）

    返回：
        校验通过的原值

    异常：
        ValueError：当值包含非法字符时
    """
    if not value:
        raise ValueError(f"{field_name} 不能为空")

    if not SAFE_ID_PATTERN.match(value):
        raise ValueError(
            f"{field_name} 包含非法字符: '{value}'，"
            f"仅允许字母、数字、下划线、连字符"
        )

    return value


def build_course_expr(scope: CourseScope) -> str:
    """构建 Milvus 过滤表达式（生产级增强：注入防护）。

    入参：
        scope：课程范围对象

    返回：
        Milvus 过滤表达式字符串

    异常：
        ValueError：当任何字段值包含注入内容时
    """
    conditions: list[str] = []

    # course_id：严格白名单校验
    course_id = validate_id_field(scope.course_id, "course_id")
    conditions.append(f'course_id == {escape_expr_value(course_id)}')

    if scope.chapter_id:
        chapter_id = validate_id_field(scope.chapter_id, "chapter_id")
        conditions.append(f'chapter_id == {escape_expr_value(chapter_id)}')

    if scope.point_id:
        point_id = validate_id_field(scope.point_id, "point_id")
        conditions.append(f'point_id == {escape_expr_value(point_id)}')

    if scope.kb_version:
        kb_version = validate_id_field(scope.kb_version, "kb_version")
        conditions.append(f'kb_version == {escape_expr_value(kb_version)}')

    if scope.content_type:
        content_type = validate_id_field(scope.content_type, "content_type")
        conditions.append(f'content_type == {escape_expr_value(content_type)}')

    return " and ".join(conditions)