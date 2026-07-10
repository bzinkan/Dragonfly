"""Durable fail-closed clean-photo revocation.

Revision ID: 20260710_0017
Revises: 20260710_0016
Create Date: 2026-07-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260710_0017"
down_revision = "20260710_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_review_queue_status", "review_queue", type_="check")
    op.create_check_constraint(
        "ck_review_queue_status",
        "review_queue",
        "status in ('pending', 'approved', 'rejected', 'revoked')",
    )
    op.create_table(
        "photo_revocations",
        sa.Column(
            "photo_id",
            sa.String(length=26),
            sa.ForeignKey("photos.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "review_id",
            sa.String(length=26),
            sa.ForeignKey("review_queue.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("claim_review_status", sa.String(length=24), nullable=False),
        sa.Column(
            "requesting_actor_user_id",
            sa.String(length=26),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source", sa.String(length=48), nullable=False),
        sa.Column("bucket", sa.String(length=128), nullable=False),
        sa.Column("source_object_name", sa.String(length=512), nullable=False),
        sa.Column("held_object_name", sa.String(length=512), nullable=False),
        # Nullable only so a malformed legacy row can acquire the durable
        # deny gate before operator repair supplies verified metadata.
        sa.Column("expected_byte_count", sa.Integer(), nullable=True),
        sa.Column("expected_sha256", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "state in ('pending', 'copying', 'succeeded', 'failed')",
            name="ck_photo_revocations_state",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_photo_revocations_attempt_count",
        ),
        sa.CheckConstraint(
            "claim_review_status in ('pending', 'approved')",
            name="ck_photo_revocations_claim_review_status",
        ),
        sa.UniqueConstraint("review_id", name="uq_photo_revocations_review_id"),
    )
    op.create_index(
        "ix_photo_revocations_state_attempt",
        "photo_revocations",
        ["state", "last_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_photo_revocations_state_attempt",
        table_name="photo_revocations",
    )
    op.drop_table("photo_revocations")
    op.execute("UPDATE review_queue SET status = 'rejected' WHERE status = 'revoked'")
    op.drop_constraint("ck_review_queue_status", "review_queue", type_="check")
    op.create_check_constraint(
        "ck_review_queue_status",
        "review_queue",
        "status in ('pending', 'approved', 'rejected')",
    )
