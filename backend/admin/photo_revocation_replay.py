"""Retry incomplete fail-closed photo revocations.

Provision as a closed-beta Container Apps Job. W1 NoOp photos remain private
and do not require this job for promotion, but any adult/stale rejection uses
the same durable service once the review surface is enabled.
"""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.storage import BlobSignedUrlGenerator, SignedUrlGenerator
from app.db import models
from app.moderation.review_service import ReviewResolutionConflict
from app.moderation.revocation import (
    MAX_REVOCATION_ATTEMPTS,
    PhotoRevocationPending,
    revoke_and_reject_review_item,
)

log = structlog.get_logger()


async def replay(
    session: AsyncSession,
    *,
    storage: SignedUrlGenerator,
    limit: int = 50,
) -> tuple[int, int]:
    """Return ``(succeeded, still_pending_or_failed)`` for one bounded pass."""
    rows = (
        await session.execute(
            select(models.PhotoRevocation, models.ReviewQueueItem)
            .join(
                models.ReviewQueueItem,
                models.ReviewQueueItem.id == models.PhotoRevocation.review_id,
            )
            .where(
                models.PhotoRevocation.state != "succeeded",
                models.PhotoRevocation.attempt_count < MAX_REVOCATION_ATTEMPTS,
                models.ReviewQueueItem.status == models.PhotoRevocation.claim_review_status,
            )
            .order_by(models.PhotoRevocation.last_attempt_at, models.PhotoRevocation.photo_id)
            .limit(limit)
        )
    ).all()
    succeeded = 0
    pending = 0
    for revocation, review in rows:
        try:
            await revoke_and_reject_review_item(
                session,
                storage=storage,
                review=review,
                reviewer_user_id=revocation.requesting_actor_user_id,
                source=revocation.source,
                claim_review_status=revocation.claim_review_status,
                nonblocking=True,
            )
        except (PhotoRevocationPending, ReviewResolutionConflict):
            await session.rollback()
            pending += 1
            continue
        succeeded += 1
    log.info(
        "photo_revocation_replay.complete",
        candidates=len(rows),
        succeeded=succeeded,
        pending=pending,
    )
    return succeeded, pending


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.sqlalchemy_database_url)
    sessions: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    storage = BlobSignedUrlGenerator(settings.blob_account_endpoint)
    try:
        async with sessions() as session:
            succeeded, pending = await replay(session, storage=storage)
        print(f"photo_revocation_replay: succeeded={succeeded} pending={pending}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
