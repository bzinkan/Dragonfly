"""Add focused expedition state.

Revision ID: 20260708_0012
Revises: 20260707_0011
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260708_0012"
down_revision = "20260707_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "expedition_progress",
        sa.Column("focused_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_expedition_progress_user_focus",
        "expedition_progress",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("focused_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_expedition_progress_user_focus", table_name="expedition_progress")
    op.drop_column("expedition_progress", "focused_at")
