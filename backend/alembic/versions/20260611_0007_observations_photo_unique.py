"""One observation per photo.

Revision ID: 20260611_0007

`POST /v1/observations` only checks that the photo is still `pending`,
and moderation flips that status asynchronously -- so a double-submit
(retry after a lost response, double-tap) could attach two observations
to one photo. The moderation worker resolves photo -> observation with
`scalar_one_or_none()` and raises `MultipleResultsFound` on duplicates,
abandon-looping the Service Bus message into the DLQ and permanently
wedging that photo's moderation.

The unique constraint makes the invariant structural; the create route
maps the violation to a 409.

This will fail loudly if duplicate `photo_id` rows already exist --
resolve those by hand first (keep the oldest, delete the rest); we do
not auto-delete kid data in a migration.
"""

from __future__ import annotations

from alembic import op

revision = "20260611_0007"
down_revision = "20260604_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_observations_photo_id", "observations", ["photo_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_observations_photo_id", "observations", type_="unique")
