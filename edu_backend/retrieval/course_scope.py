"""课程范围限定：构建检索过滤边界。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CourseScope:
    """课程检索范围限定器。

    属性：
        course_id：课程 ID（必填）
        chapter_id：章节 ID（可选，限定检索到特定章节）
        point_id：知识点 ID（可选，限定到更细粒度）
        kb_version：知识库版本标签（用于 Collection 路由）
        content_type：内容类型过滤（faq/doc/question）
    """

    course_id: str
    chapter_id: str = ""
    point_id: str = ""
    kb_version: str = ""
    content_type: str = ""

    @classmethod
    def from_request(
        cls,
        course_id: str,
        chapter_id: str = "",
        point_id: str = "",
        kb_version: str = "",
        content_type: str = "",
    ) -> CourseScope:
        """从请求参数构建 CourseScope。"""
        return cls(
            course_id=course_id,
            chapter_id=chapter_id,
            point_id=point_id,
            kb_version=kb_version,
            content_type=content_type,
        )

    def to_dict(self) -> dict:
        return {
            "course_id": self.course_id,
            "chapter_id": self.chapter_id,
            "point_id": self.point_id,
            "kb_version": self.kb_version,
            "content_type": self.content_type,
        }
