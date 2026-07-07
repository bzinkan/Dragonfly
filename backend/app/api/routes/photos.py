"""Photo upload endpoints.

`POST /v1/photos/presign` issues a V4 signed PUT URL for a single image
landing in `gs://<photos_bucket>/pending/<photo_id>.jpg`. The mobile client
PUTs the image bytes to that URL with `Content-Type: image/jpeg`, then calls
`POST /v1/observations` with the returned `photo_id`. Moderation runs out of
band on the GCS finalize event (see `docs/moderation.md`).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.core.auth import CurrentUserDep, resolve_current_user_row
from app.core.config import Settings, get_request_settings
from app.core.storage import SignedUrlGeneratorDep
from app.db import models
from app.db.session import DbSessionDep
from app.inat.client import InatClientDep, InatUnavailable
from app.inat.cv import score_image

router = APIRouter(prefix="/v1/photos", tags=["photos"])

log = structlog.get_logger()

# 15 minutes is generous for the offline-then-upload path while keeping the
# signed-URL exposure window bounded.
_PRESIGN_TTL = timedelta(minutes=15)

AllowedContentType = Literal["image/jpeg"]


class PhotoPresignRequest(BaseModel):
    content_type: AllowedContentType = Field(default="image/jpeg")


class PhotoPresignResponse(BaseModel):
    photo_id: str
    upload_url: str
    object_name: str
    bucket: str
    content_type: str
    expires_at: datetime


@router.post(
    "/presign",
    response_model=PhotoPresignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def presign_photo(
    payload: PhotoPresignRequest,
    current_user: CurrentUserDep,
    session: DbSessionDep,
    signer: SignedUrlGeneratorDep,
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> PhotoPresignResponse:
    user_row = await resolve_current_user_row(session, current_user)

    photo_id = str(ULID())
    object_name = f"pending/{photo_id}.jpg"
    bucket = settings.photos_bucket

    upload_url, expires_at = signer.generate_put_url(
        bucket=bucket,
        object_name=object_name,
        content_type=payload.content_type,
        expires_in=_PRESIGN_TTL,
    )

    photo = models.Photo(
        id=photo_id,
        user_id=user_row.id,
        bucket=bucket,
        object_name=object_name,
        status="pending",
        content_type=payload.content_type,
    )
    session.add(photo)
    await session.commit()

    log.info(
        "photos.presign.issued",
        photo_id=photo_id,
        user_id=user_row.id,
        bucket=bucket,
        object_name=object_name,
        ttl_seconds=int(_PRESIGN_TTL.total_seconds()),
    )

    return PhotoPresignResponse(
        photo_id=photo_id,
        upload_url=upload_url,
        object_name=object_name,
        bucket=bucket,
        content_type=payload.content_type,
        expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# GET /v1/photos/{photo_id}/url -- short-lived signed GET for rendering
# ---------------------------------------------------------------------------

# 5 minutes is enough for the mobile client to render + cache the image.
# Shorter than presign because GET is read-only and can be re-issued
# cheaply.
_PHOTO_GET_TTL = timedelta(minutes=5)


class PhotoUrlResponse(BaseModel):
    photo_id: str
    url: str
    expires_at: datetime


class CvSuggestionDTO(BaseModel):
    taxon_id: int
    common_name: str | None
    scientific_name: str | None
    score: float


class PhotoIdentifyResponse(BaseModel):
    """Top-K iNat CV suggestions for a pending photo."""

    photo_id: str
    suggestions: list[CvSuggestionDTO]
    cv_unavailable: bool = False
    no_matches: bool = False


async def _intersecting_groups(
    session: AsyncSession, *, caller_user_id: str, photo_owner_id: str
) -> bool:
    """True if caller and photo owner share any group. Authorization
    boundary for the signed-GET endpoint -- adults reviewing quarantined
    photos and kids viewing their own both qualify (a kid is in their own
    group; the photo owner == them when it's their photo)."""
    if caller_user_id == photo_owner_id:
        return True
    rows = (
        await session.execute(
            select(models.Membership.user_id, models.Membership.group_id).where(
                models.Membership.user_id.in_([caller_user_id, photo_owner_id])
            )
        )
    ).all()
    seen: dict[str, set[str]] = {caller_user_id: set(), photo_owner_id: set()}
    for uid, gid in rows:
        seen[uid].add(gid)
    return bool(seen[caller_user_id] & seen[photo_owner_id])


@router.get("/{photo_id}/url", response_model=PhotoUrlResponse)
async def photo_get_url(
    photo_id: str,
    current_user: CurrentUserDep,
    session: DbSessionDep,
    signer: SignedUrlGeneratorDep,
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> PhotoUrlResponse:
    user_row = await resolve_current_user_row(session, current_user)

    photo = (
        await session.execute(select(models.Photo).where(models.Photo.id == photo_id))
    ).scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    if not await _intersecting_groups(
        session, caller_user_id=user_row.id, photo_owner_id=photo.user_id
    ):
        # Caller has no group overlap with the photo owner -- 404 like
        # missing, no enumeration leak.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    url, expires_at = signer.generate_get_url(
        bucket=photo.bucket,
        object_name=photo.object_name,
        expires_in=_PHOTO_GET_TTL,
    )
    return PhotoUrlResponse(photo_id=photo.id, url=url, expires_at=expires_at)


# ---------------------------------------------------------------------------
# POST /v1/photos/{photo_id}/identify -- pre-save iNat CV suggestions
# ---------------------------------------------------------------------------


@router.post("/{photo_id}/identify", response_model=PhotoIdentifyResponse)
async def identify_photo(
    photo_id: str,
    current_user: CurrentUserDep,
    session: DbSessionDep,
    inat_client: InatClientDep,
    storage: SignedUrlGeneratorDep,
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> PhotoIdentifyResponse:
    user_row = await resolve_current_user_row(session, current_user)

    # Owner check stays in the WHERE clause, so wrong-owner IDs look
    # identical to missing IDs.
    photo = (
        await session.execute(
            select(models.Photo).where(
                models.Photo.id == photo_id,
                models.Photo.user_id == user_row.id,
            )
        )
    ).scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    if photo.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Photo is in status {photo.status}, not pending",
        )

    if not settings.inat_oauth_token:
        log.info(
            "observations.identify.cv_unavailable_no_token",
            photo_id=photo_id,
            pre_save=True,
        )
        return PhotoIdentifyResponse(photo_id=photo_id, suggestions=[], cv_unavailable=True)

    image_bytes = storage.fetch_object_bytes(bucket=photo.bucket, object_name=photo.object_name)

    try:
        suggestions = await score_image(inat_client, image_bytes=image_bytes, top_k=3)
    except InatUnavailable as exc:
        log.warning(
            "observations.identify.cv_unavailable",
            photo_id=photo_id,
            pre_save=True,
            reason=str(exc),
        )
        return PhotoIdentifyResponse(photo_id=photo_id, suggestions=[], cv_unavailable=True)

    no_matches = len(suggestions) == 0
    log.info(
        "observations.identify.scored",
        photo_id=photo_id,
        pre_save=True,
        suggestion_count=len(suggestions),
        no_matches=no_matches,
    )
    return PhotoIdentifyResponse(
        photo_id=photo_id,
        suggestions=[
            CvSuggestionDTO(
                taxon_id=s.taxon_id,
                common_name=s.common_name,
                scientific_name=s.scientific_name,
                score=s.score,
            )
            for s in suggestions
        ],
        no_matches=no_matches,
    )
