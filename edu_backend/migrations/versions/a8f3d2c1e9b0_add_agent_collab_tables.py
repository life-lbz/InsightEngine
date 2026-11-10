"""add agent collab tables

Revision ID: a8f3d2c1e9b0
Revises: 0001_baseline
Create Date: 2026-09-01

新增多 Agent 协作所需表：
- practice_records：学员练习记录（出题 Agent 写入，学情分析读取）
- faq_candidates：FAQ 候选（运维 Agent 写入 pending_review，管理员审核后入 faqs）
- agent_tasks：Agent 任务执行记录
- insight_reports：学情报告存档
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a8f3d2c1e9b0"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    statements = [
        """CREATE TABLE IF NOT EXISTS practice_records (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(191) NOT NULL,
            course_id VARCHAR(128) NOT NULL,
            question_id VARCHAR(191) NULL,
            question_text TEXT NOT NULL,
            user_answer TEXT NULL,
            is_correct TINYINT NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_pr_user_course (user_id, course_id),
            INDEX idx_pr_course (course_id)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci""",
        """CREATE TABLE IF NOT EXISTS faq_candidates (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            course_id VARCHAR(128) NOT NULL,
            question TEXT NOT NULL,
            suggested_answer MEDIUMTEXT NOT NULL,
            source VARCHAR(128) NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'pending_review',
            reviewer_id VARCHAR(191) NULL,
            reviewed_at DATETIME NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_fc_course (course_id),
            INDEX idx_fc_status (status)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci""",
        """CREATE TABLE IF NOT EXISTS agent_tasks (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(191) NOT NULL,
            user_id VARCHAR(191) NULL,
            role VARCHAR(32) NOT NULL DEFAULT 'student',
            course_id VARCHAR(128) NULL,
            question TEXT NULL,
            assigned_agent VARCHAR(64) NULL,
            answer MEDIUMTEXT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'running',
            trace_id VARCHAR(64) NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_at_session (session_id),
            INDEX idx_at_user (user_id)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci""",
        """CREATE TABLE IF NOT EXISTS insight_reports (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            course_id VARCHAR(128) NOT NULL,
            report MEDIUMTEXT NOT NULL,
            generated_by VARCHAR(32) NOT NULL DEFAULT 'teacher_insight_agent',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_ir_course (course_id)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci""",
    ]
    for stmt in statements:
        conn.execute(sa.text(stmt))


def downgrade() -> None:
    for t in (
        "insight_reports",
        "agent_tasks",
        "faq_candidates",
        "practice_records",
    ):
        op.execute(f"DROP TABLE IF EXISTS {t}")
