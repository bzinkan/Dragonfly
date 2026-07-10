"""Field Journal chronology indexes and maintained Dex projections.

Revision ID: 20260710_0016
Revises: 20260709_0015
Create Date: 2026-07-10

The migration is additive and safe to run before the API deployment.  It
reconciles existing rows before validating the projection constraints, then
queues every affected user for the normal deterministic rebuild.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260710_0016"
down_revision = "20260709_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dex_entries",
        sa.Column(
            "observation_count",
            sa.Integer(),
            nullable=True,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "dex_entries",
        sa.Column(
            "latest_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "dex_entries",
        sa.Column(
            "representative_observation_id",
            sa.String(length=26),
            nullable=True,
        ),
    )
    op.add_column(
        "dex_entries",
        sa.Column(
            "representative_photo_id",
            sa.String(length=26),
            nullable=True,
        ),
    )

    # Ensure a rebuild is pending even for users whose only historic Dex row
    # is about to disappear because every supporting observation was rejected.
    op.execute(
        sa.text(
            """
            INSERT INTO derived_state_rebuilds (
              id, user_id, trigger_observation_id, status, attempt_count,
              created_at, updated_at
            )
            SELECT 'J' || upper(substr(md5(affected.user_id || '-journal-projection'), 1, 25)),
                   affected.user_id, NULL, 'queued', 0, now(), now()
              FROM (
                    SELECT DISTINCT user_id FROM observations
                    UNION
                    SELECT DISTINCT user_id FROM dex_entries
                   ) AS affected
            ON CONFLICT DO NOTHING
            """
        )
    )

    # Rebuild the complete projection from accepted observations. The
    # earliest observed row remains the first-observation fact; the newest
    # clean row is independently selected for safe representative imagery.
    op.execute(
        sa.text(
            """
            WITH accepted AS (
              SELECT o.*,
                     row_number() OVER (
                       PARTITION BY o.user_id, o.taxon_id
                       ORDER BY o.observed_at, o.id
                     ) AS first_rank,
                     count(*) OVER (
                       PARTITION BY o.user_id, o.taxon_id
                     ) AS accepted_count,
                     max(o.observed_at) OVER (
                       PARTITION BY o.user_id, o.taxon_id
                     ) AS accepted_latest
                FROM observations o
               WHERE o.taxon_id IS NOT NULL
                 AND o.rejected_at IS NULL
                 AND o.moderation_status <> 'rejected'
            ),
            representative AS (
              SELECT DISTINCT ON (o.user_id, o.taxon_id)
                     o.user_id,
                     o.taxon_id,
                     o.id AS observation_id,
                     o.photo_id
                FROM observations o
                JOIN photos p ON p.id = o.photo_id
               WHERE o.taxon_id IS NOT NULL
                 AND o.rejected_at IS NULL
                 AND o.moderation_status = 'clean'
                 AND p.status = 'clean'
                 AND p.attachment_status = 'attached'
               ORDER BY o.user_id, o.taxon_id, o.observed_at DESC, o.id DESC
            )
            INSERT INTO dex_entries (
              id, user_id, group_id, taxon_id, species_name,
              first_observation_id, first_seen_at, observation_count,
              latest_seen_at, representative_observation_id,
              representative_photo_id, created_at, updated_at
            )
            SELECT 'X' || upper(substr(md5(a.user_id || ':' || a.taxon_id::text), 1, 25)),
                   a.user_id,
                   a.group_id,
                   a.taxon_id,
                   a.species_name,
                   a.id,
                   a.observed_at,
                   a.accepted_count,
                   a.accepted_latest,
                   r.observation_id,
                   r.photo_id,
                   now(),
                   now()
              FROM accepted a
              LEFT JOIN representative r
                ON r.user_id = a.user_id AND r.taxon_id = a.taxon_id
             WHERE a.first_rank = 1
            ON CONFLICT (user_id, taxon_id) DO UPDATE
              SET group_id = excluded.group_id,
                  species_name = excluded.species_name,
                  first_observation_id = excluded.first_observation_id,
                  first_seen_at = excluded.first_seen_at,
                  observation_count = excluded.observation_count,
                  latest_seen_at = excluded.latest_seen_at,
                  representative_observation_id = excluded.representative_observation_id,
                  representative_photo_id = excluded.representative_photo_id,
                  updated_at = now()
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM dex_entries d
             WHERE NOT EXISTS (
                   SELECT 1
                     FROM observations o
                    WHERE o.user_id = d.user_id
                      AND o.taxon_id = d.taxon_id
                      AND o.rejected_at IS NULL
                      AND o.moderation_status <> 'rejected'
             )
            """
        )
    )

    # Abort rather than promote a partially reconciled projection.
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1
                  FROM dex_entries d
                  LEFT JOIN LATERAL (
                    SELECT count(*) AS accepted_count,
                           min(o.observed_at) AS first_seen,
                           max(o.observed_at) AS latest_seen
                      FROM observations o
                     WHERE o.user_id = d.user_id
                       AND o.taxon_id = d.taxon_id
                       AND o.rejected_at IS NULL
                       AND o.moderation_status <> 'rejected'
                  ) expected ON true
                 WHERE d.observation_count <> expected.accepted_count
                    OR d.first_seen_at <> expected.first_seen
                    OR d.latest_seen_at <> expected.latest_seen
              ) THEN
                RAISE EXCEPTION 'Dex projection reconciliation failed';
              END IF;
            END $$
            """
        )
    )

    op.alter_column("dex_entries", "observation_count", nullable=False)
    op.alter_column("dex_entries", "latest_seen_at", nullable=False)
    op.create_check_constraint(
        "ck_dex_entries_observation_count",
        "dex_entries",
        "observation_count >= 0",
    )
    op.create_foreign_key(
        "fk_dex_entries_representative_observation_id_observations",
        "dex_entries",
        "observations",
        ["representative_observation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_dex_entries_representative_photo_id_photos",
        "dex_entries",
        "photos",
        ["representative_photo_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_dex_entries_user_first_seen",
        "dex_entries",
        ["user_id", "first_seen_at", "id"],
    )
    op.create_index(
        "ix_observations_user_observed_active",
        "observations",
        ["user_id", sa.text("observed_at DESC"), sa.text("id DESC")],
        postgresql_where=sa.text(
            "rejected_at IS NULL AND moderation_status <> 'rejected'"
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_observations_user_observed_active", table_name="observations")
    op.drop_index("ix_dex_entries_user_first_seen", table_name="dex_entries")
    op.drop_constraint(
        "fk_dex_entries_representative_photo_id_photos",
        "dex_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_dex_entries_representative_observation_id_observations",
        "dex_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_dex_entries_observation_count",
        "dex_entries",
        type_="check",
    )
    op.drop_column("dex_entries", "representative_photo_id")
    op.drop_column("dex_entries", "representative_observation_id")
    op.drop_column("dex_entries", "latest_seen_at")
    op.drop_column("dex_entries", "observation_count")
