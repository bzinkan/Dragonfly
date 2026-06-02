"""Authenticated user routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ulid import ULID

from app.core.auth import (
    CurrentUser,
    CurrentUserDep,
)
from app.core.config import Settings, get_request_settings
from app.core.kid_jwt import (
    InvalidDragonflyJwt,
    mint_session_token,
    public_jwks,
    verify_dragonfly_jwt,
)
from app.db import models
from app.db.session import DbSessionDep

router = APIRouter(prefix="/v1", tags=["auth"])

# JWKS lives at /.well-known/... -- no /v1 prefix. Mounted separately from
# the main auth router so FastAPI doesn't prepend the prefix.
well_known_router = APIRouter(tags=["auth"])

log = structlog.get_logger()

# Bumped any time the privacy policy text changes materially. Recorded
# alongside each consent so we know which version each parent agreed to.
_CURRENT_POLICY_VERSION = "2026-05-10-DRAFT"


class ParentSignupRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=80)


class UserResponse(BaseModel):
    """Public shape of a `users` row over the API."""

    id: str
    firebase_uid: str | None = None
    entra_oid: str | None = None
    role: str
    display_name: str

    @classmethod
    def from_model(cls, user: models.User) -> UserResponse:
        return cls(
            id=user.id,
            firebase_uid=user.firebase_uid,
            entra_oid=getattr(user, "entra_oid", None),
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
    """Create or return the parent `users` row for the authenticated Entra ID.

    The client is expected to have already signed in with Microsoft Entra
    External ID via MSAL. This endpoint:

    1. Reads the verified Entra access token from the `Authorization` header
       (handled by the CurrentUserDep dependency).
    2. Upserts a `users` row with `role='parent'` keyed by the Entra OID
       (`users.entra_oid`).

    Idempotent: if a `users` row already exists for this entra_oid, the
    existing row is returned and no new `users` row is created. For
    back-compat with legacy Firebase rows we also fall back to looking
    up by `firebase_uid` when the caller has no Entra OID -- this keeps
    the existing test stubs working through Phase 6a.
    """
    # Resolve the Entra OID. In production this comes from the verified
    # token; in legacy/test paths the stub puts the Firebase uid into
    # current_user.uid with entra_oid=None.
    entra_oid = current_user.entra_oid

    if entra_oid is not None:
        result = await session.execute(
            select(models.User).where(models.User.entra_oid == entra_oid)
        )
    else:
        # Back-compat: legacy stub-token path -- fall back to firebase_uid
        # lookup so the existing test surface keeps passing.
        result = await session.execute(
            select(models.User).where(models.User.firebase_uid == current_user.uid)
        )
    existing = result.scalar_one_or_none()

    if existing is not None:
        # Backfill entra_oid on legacy rows whose first sign-in is via Entra.
        if entra_oid is not None and getattr(existing, "entra_oid", None) is None:
            existing.entra_oid = entra_oid  # type: ignore[attr-defined]
            await session.commit()
        log.info(
            "auth.parent_signup.idempotent",
            user_id=existing.id,
            entra_oid=entra_oid,
            firebase_uid=existing.firebase_uid,
        )
        return UserResponse.from_model(existing)

    # New row: Entra-only, no Firebase identity for fresh signups.
    new_user = models.User(
        id=str(ULID()),
        firebase_uid=None,
        role="parent",
        display_name=request_body.display_name,
    )
    if entra_oid is not None:
        new_user.entra_oid = entra_oid  # type: ignore[attr-defined]
    else:
        # Legacy stub path: keep the Firebase uid populated so the existing
        # test assertions that read `added_user.firebase_uid` still see a
        # value. Real Entra signups land in the branch above.
        new_user.firebase_uid = current_user.uid
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    log.info(
        "auth.parent_signup.created",
        user_id=new_user.id,
        entra_oid=entra_oid,
    )
    return UserResponse.from_model(new_user)


# ---------------------------------------------------------------------------
# POST /v1/auth/kid-exchange -- swap a single-use handoff JWT for a session JWT
# ---------------------------------------------------------------------------


class KidExchangeRequest(BaseModel):
    handoff_token: str = Field(..., min_length=1, max_length=4096)


class KidExchangeResponse(BaseModel):
    session_token: str
    expires_at: datetime
    user: UserResponse


@router.post(
    "/auth/kid-exchange",
    response_model=KidExchangeResponse,
    status_code=status.HTTP_200_OK,
)
async def kid_exchange(
    payload: KidExchangeRequest,
    session: DbSessionDep,
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> KidExchangeResponse:
    """Exchange a single-use handoff JWT for a long-lived kid session JWT.

    PUBLIC endpoint -- no `Authorization` header. The handoff JWT in the
    request body IS the proof of authority; it was minted by the parent's
    `POST /v1/groups/{group_id}/kids` call and handed to the kid's device.

    Single-use is enforced by an atomic INSERT into `kid_handoff_jti` keyed
    on the JWT's `jti` claim: a unique-violation means the token was already
    redeemed and we return 409 Conflict.
    """
    # 1. Verify the JWT signature + claims (issuer, audience, expiry, type).
    try:
        claims = verify_dragonfly_jwt(
            payload.handoff_token,
            settings=settings,
            expected_token_type="handoff",
        )
    except InvalidDragonflyJwt as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid handoff token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    jti_value = claims.get("jti")
    sub_value = claims.get("sub")
    exp_value = claims.get("exp")
    if not isinstance(jti_value, str) or not isinstance(sub_value, str) or exp_value is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Handoff token missing required claims",
            headers={"WWW-Authenticate": "Bearer"},
        )
    jti = jti_value
    kid_user_id = sub_value
    expires_at = datetime.fromtimestamp(int(exp_value), tz=UTC)  # type: ignore[arg-type]

    parent_id_claim = claims.get("parent_id")
    parent_id = parent_id_claim if isinstance(parent_id_claim, str) else ""
    group_id_claim = claims.get("group_id")
    group_id = group_id_claim if isinstance(group_id_claim, str) else ""

    # 2. Atomic single-use: INSERT the jti. Unique-PK collision means
    #    this handoff was already redeemed (replay attempt).
    jti_row = models.KidHandoffJti(
        jti=jti,
        kid_user_id=kid_user_id,
        consumed_at=datetime.now(UTC),
        expires_at=expires_at,
    )
    session.add(jti_row)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        log.info("auth.kid_exchange.replay", jti=jti, kid_id=kid_user_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Handoff token already used",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # 3. Load the kid's users row.
    kid_result = await session.execute(select(models.User).where(models.User.id == kid_user_id))
    kid = kid_result.scalar_one_or_none()
    if kid is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kid user not found.",
        )
    if kid.disabled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User disabled.",
        )

    # 4. Mint the session JWT (30 days by default; settings-driven).
    session_token = mint_session_token(
        kid_user_id=kid.id,
        parent_id=parent_id,
        group_id=group_id,
        settings=settings,
    )
    session_expires_at = datetime.now(UTC) + timedelta(
        seconds=settings.dragonfly_session_ttl_seconds
    )

    log.info(
        "auth.kid_exchange.success",
        kid_id=kid.id,
        jti=jti,
        parent_id=parent_id,
        group_id=group_id,
    )

    return KidExchangeResponse(
        session_token=session_token,
        expires_at=session_expires_at,
        user=UserResponse.from_model(kid),
    )


# ---------------------------------------------------------------------------
# GET /.well-known/dragonfly-kid-jwks.json -- public JWKS for kid tokens
# ---------------------------------------------------------------------------


@well_known_router.get(
    "/.well-known/dragonfly-kid-jwks.json",
    include_in_schema=False,
)
def kid_jwks(
    response: Response,
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> dict[str, object]:
    """Return the Dragonfly kid-JWT signing key in JWKS format.

    Used by any downstream service (mobile app, future services) to verify
    Dragonfly-minted kid handoff / session tokens. The same kid is rotated
    rarely (manifest constant `dragonfly_jwt_kid`), so this response is
    cacheable for an hour.
    """
    response.headers["Cache-Control"] = "public, max-age=3600"
    return public_jwks(settings)


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
