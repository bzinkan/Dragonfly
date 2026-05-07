"""production foundation schema

Revision ID: 20260506_0001
Revises:
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260506_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("age_band", sa.String(length=16), nullable=True),
        sa.Column("parent_user_id", sa.String(length=26), nullable=True),
        sa.Column("consent_granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("role in ('parent', 'teacher', 'kid')", name="ck_users_role"),
        sa.ForeignKeyConstraint(["parent_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("firebase_uid", name="uq_users_firebase_uid"),
    )

    op.create_table(
        "groups",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("join_code", sa.String(length=6), nullable=False),
        sa.Column("owner_user_id", sa.String(length=26), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("join_code", name="uq_groups_join_code"),
    )

    op.create_table(
        "expedition_content",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash", name="uq_expedition_content_hash"),
    )

    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_run_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("cursor", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status in ('running', 'succeeded', 'failed', 'cancelled')",
            name="ck_ingest_runs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_run_id", name="uq_ingest_runs_source_run"),
    )
    op.create_index("ix_ingest_runs_source_status", "ingest_runs", ["source", "status"])

    op.create_table(
        "job_state",
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("cursor", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("name"),
    )

    op.create_table(
        "species_cache",
        sa.Column("taxon_id", sa.Integer(), nullable=False),
        sa.Column("scientific_name", sa.String(length=200), nullable=True),
        sa.Column("common_name", sa.String(length=200), nullable=True),
        sa.Column("iconic_taxon", sa.String(length=80), nullable=True),
        sa.Column("source_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("taxon_id"),
    )

    op.create_table(
        "geo_cache",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("rounded_lat", sa.String(length=16), nullable=False),
        sa.Column("rounded_lng", sa.String(length=16), nullable=False),
        sa.Column("place_name", sa.String(length=200), nullable=False),
        sa.Column("source_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rounded_lat", "rounded_lng", name="uq_geo_cache_lat_lng"),
    )

    op.create_table(
        "rarity_cache",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("region_geohash", sa.String(length=8), nullable=False),
        sa.Column("taxon_id", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(length=24), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "tier in ('abundant', 'common', 'rare', 'epic', 'legendary', 'unrecorded')",
            name="ck_rarity_cache_tier",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("region_geohash", "taxon_id", name="uq_rarity_cache_region_taxon"),
    )

    op.create_table(
        "memberships",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("group_id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("dex_count", sa.Integer(), nullable=False),
        sa.Column("rarest_tier", sa.String(length=24), nullable=True),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("role in ('parent', 'teacher', 'kid')", name="ck_memberships_role"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "user_id", name="uq_memberships_group_user"),
    )

    op.create_table(
        "photos",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("bucket", sa.String(length=128), nullable=False),
        sa.Column("object_name", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status in ('pending', 'clean', 'quarantine', 'deleted')",
            name="ck_photos_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bucket", "object_name", name="uq_photos_bucket_object"),
    )

    op.create_table(
        "observations",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("group_id", sa.String(length=26), nullable=False),
        sa.Column("photo_id", sa.String(length=26), nullable=False),
        sa.Column("taxon_id", sa.Integer(), nullable=True),
        sa.Column("species_name", sa.String(length=200), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("geohash4", sa.String(length=8), nullable=True),
        sa.Column("place_name", sa.String(length=200), nullable=True),
        sa.Column("inat_observation_id", sa.Integer(), nullable=True),
        sa.Column("submitted_to_inat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rewards", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_observations_group_created", "observations", ["group_id", "created_at"])
    op.create_index("ix_observations_taxon", "observations", ["taxon_id"])
    op.create_index("ix_observations_user_created", "observations", ["user_id", "created_at"])

    op.create_table(
        "dex_entries",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("group_id", sa.String(length=26), nullable=False),
        sa.Column("taxon_id", sa.Integer(), nullable=False),
        sa.Column("species_name", sa.String(length=200), nullable=True),
        sa.Column("first_observation_id", sa.String(length=26), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["first_observation_id"], ["observations.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "taxon_id", name="uq_dex_entries_user_taxon"),
    )
    op.create_index("ix_dex_entries_group_taxon", "dex_entries", ["group_id", "taxon_id"])

    op.create_table(
        "expedition_progress",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("group_id", sa.String(length=26), nullable=False),
        sa.Column("expedition_id", sa.String(length=120), nullable=False),
        sa.Column("completed_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["expedition_id"], ["expedition_content.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "expedition_id", name="uq_expedition_progress_user_exp"),
    )

    op.create_table(
        "review_queue",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("group_id", sa.String(length=26), nullable=False),
        sa.Column("photo_id", sa.String(length=26), nullable=False),
        sa.Column("observation_id", sa.String(length=26), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reviewer_user_id", sa.String(length=26), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status in ('pending', 'approved', 'rejected')",
            name="ck_review_queue_status",
        ),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["observation_id"], ["observations.id"]),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"]),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_queue_group_status", "review_queue", ["group_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_review_queue_group_status", table_name="review_queue")
    op.drop_table("review_queue")
    op.drop_table("expedition_progress")
    op.drop_index("ix_dex_entries_group_taxon", table_name="dex_entries")
    op.drop_table("dex_entries")
    op.drop_index("ix_observations_user_created", table_name="observations")
    op.drop_index("ix_observations_taxon", table_name="observations")
    op.drop_index("ix_observations_group_created", table_name="observations")
    op.drop_table("observations")
    op.drop_table("photos")
    op.drop_table("memberships")
    op.drop_table("rarity_cache")
    op.drop_table("geo_cache")
    op.drop_table("species_cache")
    op.drop_table("job_state")
    op.drop_index("ix_ingest_runs_source_status", table_name="ingest_runs")
    op.drop_table("ingest_runs")
    op.drop_table("expedition_content")
    op.drop_table("groups")
    op.drop_table("users")
