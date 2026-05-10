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
from ulid import ULID

from app.core.auth import CurrentUserDep
from app.core.config import Settings, get_request_settings
from app.core.storage import SignedUrlGeneratorDep
from app.db import models
from app.db.session import DbSessionDep

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
    user_row = (
        await session.execute(
            select(models.User).where(models.User.firebase_uid == current_user.uid)
        )
    ).scalar_one_or_none()
    if user_row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No Postgres user for this Firebase identity",
        )

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
