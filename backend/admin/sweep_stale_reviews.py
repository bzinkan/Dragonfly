"""Auto-reject review_queue rows still pending after the staleness window.

Per docs/moderation.md "Teacher review lifecycle":

> Stale (no decision in 30 days). The nightly sweep auto-rejects the
> review and runs the rejection path.

Same admin-task pattern as cleanup_smoke_users.py and rarity_refresh.py:

    python -m admin.sweep_stale_reviews

Idempotent: re-running with no stale rows is a no-op. The
photos.status='deleted' update + memberships.observation_count
decrement mirrors what the manual reject endpoint
(POST /v1/review-queue/{id}/reject) does.

Run as a Cloud Run Job triggered by Cloud Scheduler nightly. Spec
mirrors the hinterland-cleanup-smoke-nightly cron in
infra-gcp/main.tf; document the new cron in runbook follow-up.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db import models

log = structlog.get_logger()

# 30 days matches docs/moderation.md. Tunable via this constant rather
# than a config var because the threshold is a moderation-policy
# decision, not an operations one.
_STALE_AFTER = timedelta(days=30)


async def sweep(session: AsyncSession) -> int:
    """Auto-reject stale pending reviews. Returns the count resolved."""
    cutoff = datetime.now(UTC) - _STALE_AFTER

    # Pull all stale rows + the joined photo + observation in one query
    # so we know what to decrement.
    stale = (
        await session.execute(
            select(models.ReviewQueueItem, models.Photo, models.Observation)
            .join(models.Photo, models.ReviewQueueItem.photo_id == models.Photo.id)
            .outerjoin(
                models.Observation,
                models.ReviewQueueItem.observation_id == models.Observation.id,
            )
            .where(
                models.ReviewQueueItem.status == "pending",
                models.ReviewQueueItem.created_at < cutoff,
            )
        )
    ).all()

    if not stale:
        log.info("sweep_stale_reviews.nothing_to_do")
        return 0

    now = datetime.now(UTC)
    for review, photo, observation in stale:
        photo.status = "deleted"
        photo.moderated_at = now

        # Decrement counter only when the original observation row is
        # known. Same skip-if-missing posture as the reject endpoint.
        if observation is not None:
            await session.execute(
                update(models.Membership)
                .where(
                    models.Membership.user_id == observation.user_id,
                    models.Membership.group_id == observation.group_id,
                )
                .values(observation_count=models.Membership.observation_count - 1)
            )

        review.status = "rejected"
        review.reviewer_user_id = None  # auto-reject -- no human reviewer
        review.resolved_at = now

        log.info(
            "sweep_stale_reviews.auto_rejected",
            review_id=review.id,
            photo_id=photo.id,
            age_days=(now - review.created_at).days,
        )

    await session.commit()
    log.info("sweep_stale_reviews.complete", count=len(stale))
    return len(stale)


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.sqlalchemy_database_url)
    sessions: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            count = await sweep(session)
        print(f"sweep_stale_reviews: {count} review(s) auto-rejected")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
