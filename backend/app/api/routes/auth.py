"""Authenticated user routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from ulid import ULID

from app.core.auth import (
    CurrentUser,
    CurrentUserDep,
    set_firebase_custom_claims,
)
from app.core.config import Settings, get_request_settings
from app.db import models
from app.db.session import DbSessionDep

router = APIRouter(prefix="/v1", tags=["auth"])

log = structlog.get_logger()

# Bumped any time the privacy policy text changes materially. Recorded
# alongside each consent so we know which version each parent agreed to.
_CURRENT_POLICY_VERSION = "2026-05-10-DRAFT"


class ParentSignupRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=80)


class UserResponse(BaseModel):
    """Public shape of a `users` row over the API."""

    id: str
    firebase_uid: str
    role: str
    display_name: str

    @classmethod
    def from_model(cls, user: models.User) -> UserResponse:
        return cls(
            id=user.id,
            firebase_uid=user.firebase_uid,
            role=user.role,
            display_name=user.display_name,
        )


@router.get("/me", response_model=CurrentUser)
def me(current_user: CurrentUserDep) -> CurrentUser:
    return current_user


@router.post(
    "/auth/parent-signup",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def parent_signup(
    request_body: ParentSignupRequest,
    current_user: CurrentUserDep,
    session: DbSessionDep,
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> UserResponse:
    """Create or return the parent `users` row for the authenticated Firebase ID.

    The client is expected to have already created the Firebase user via
    email/password (Firebase Web SDK). This endpoint:

    1. Reads the verified Firebase ID token from the `Authorization` header.
    2. Upserts a `users` row with `role='parent'` keyed by the Firebase uid.
    3. Sets the Firebase custom claim `role=parent` so subsequent ID tokens
       carry the role without a server lookup.

    Idempotent: if a `users` row already exists for this firebase_uid, the
    existing row is returned and no new `users` row is created. The custom
    claim is re-set on every call to recover from drift (e.g. claims wiped
    by a manual Console action).
    """
    result = await session.execute(
        select(models.User).where(models.User.firebase_uid == current_user.uid)
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        set_firebase_custom_claims(current_user.uid, {"role": "parent"}, settings)
        log.info(
            "auth.parent_signup.idempotent",
            user_id=existing.id,
            firebase_uid=current_user.uid,
        )
        return UserResponse.from_model(existing)

    new_user = models.User(
        id=str(ULID()),
        firebase_uid=current_user.uid,
        role="parent",
        display_name=request_body.display_name,
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    set_firebase_custom_claims(current_user.uid, {"role": "parent"}, settings)
    log.info(
        "auth.parent_signup.created",
        user_id=new_user.id,
        firebase_uid=current_user.uid,
    )
    return UserResponse.from_model(new_user)


# ---------------------------------------------------------------------------
# POST /v1/auth/consent -- public, COPPA parental consent record
# ---------------------------------------------------------------------------


class ConsentRequest(BaseModel):
    """Pre-signup consent record. Public endpoint -- no auth header.

    The parent visits the web /consent page, enters their email, and
    confirms. We record the (email, policy_version, timestamp) in
    Cloud Logging as `auth.consent.recorded`. When the parent later
    signs up via parent_signup, we'll join the consent record to the
    user row via email -- that linkage is a follow-up slice.
    """

    # Lightweight regex check -- avoids pulling in email-validator just
    # for one endpoint. Real semantic validation happens via Firebase
    # Auth at signup time.
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)
    policy_version: str | None = None


class ConsentResponse(BaseModel):
    recorded_at: datetime
    policy_version: str


@router.post(
    "/auth/consent",
    response_model=ConsentResponse,
    status_code=status.HTTP_200_OK,
)
async def record_consent(payload: ConsentRequest) -> ConsentResponse:
    """Record COPPA parental consent. Public, unauthenticated.

    Storage today is structured Cloud Logging (append-only,
    queryable, retained 30 days by default). For long-term audit a
    follow-up slice adds a `parent_consent_records` table + Alembic
    migration; the JSON shape logged here is the same as the future
    row schema so the migration is mechanical.
    """
    version = payload.policy_version or _CURRENT_POLICY_VERSION
    now = datetime.now(UTC)
    log.info(
        "auth.consent.recorded",
        email=payload.email,
        policy_version=version,
        recorded_at=now.isoformat(),
    )
    return ConsentResponse(recorded_at=now, policy_version=version)
