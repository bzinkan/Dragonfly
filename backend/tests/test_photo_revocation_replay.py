from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from admin import photo_revocation_replay
from app.db import models


@pytest.mark.asyncio
async def test_replay_preserves_approved_claim_and_revoking_actor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor_id = "01ARZ3NDEKTSV4RRFFQ69G5FAA"
    revocation = models.PhotoRevocation(
        photo_id="01ARZ3NDEKTSV4RRFFQ69G5FAB",
        review_id="01ARZ3NDEKTSV4RRFFQ69G5FAC",
        claim_review_status="approved",
        requesting_actor_user_id=actor_id,
        source="adult_revocation",
        bucket="photos",
        source_object_name="observations/photo.jpg",
        held_object_name="rejected/held/photo.jpg",
        expected_byte_count=100,
        expected_sha256="a" * 64,
        state="copying",
        attempt_count=1,
    )
    review = models.ReviewQueueItem(
        id=revocation.review_id,
        group_id="01ARZ3NDEKTSV4RRFFQ69G5FAD",
        photo_id=revocation.photo_id,
        status="approved",
    )
    result = SimpleNamespace(all=lambda: [(revocation, review)])
    session = SimpleNamespace(
        execute=AsyncMock(return_value=result),
        rollback=AsyncMock(),
    )
    captured: dict[str, object] = {}

    async def fake_revoke(*args: object, **kwargs: object) -> None:
        del args
        captured.update(kwargs)

    monkeypatch.setattr(
        photo_revocation_replay,
        "revoke_and_reject_review_item",
        fake_revoke,
    )

    succeeded, pending = await photo_revocation_replay.replay(  # type: ignore[arg-type]
        session,
        storage=SimpleNamespace(),  # type: ignore[arg-type]
    )

    assert (succeeded, pending) == (1, 0)
    assert captured["claim_review_status"] == "approved"
    assert captured["reviewer_user_id"] == actor_id
    assert captured["source"] == "adult_revocation"
