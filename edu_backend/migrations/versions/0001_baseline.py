"""baseline: 从 runtime_schema.sql 导入初始表结构

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    sql_path = op.get_context().script.location / ".." / "storage" / "runtime_schema.sql"
    if sql_path.exists():
        sql_text = sql_path.read_text(encoding="utf-8")
        statements = [s.strip() for s in sql_text.split(";") if s.strip() and not s.strip().startswith("--")]
        for stmt in statements:
            try:
                conn.execute(sa.text(stmt))
            except Exception:
                pass


def downgrade() -> None:
    tables = [
        "qa_feedback", "chat_messages", "audit_logs",
        "student_progress", "questions", "knowledge_points",
        "chapters", "faqs", "courses", "documents",
        "file_registry", "kb_versions", "users",
        "ab_tests", "ab_test_assignments",
    ]
    for t in tables:
        op.execute(f"DROP TABLE IF EXISTS {t}")
