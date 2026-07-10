"""Dex listing endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.auth import CurrentUserDep, resolve_current_user_row
from app.db import models
from app.db.session import DbSessionDep

router = APIRouter(prefix="/v1/dex", tags=["dex"])

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 50


class DexListItem(BaseModel):
    id: str
    taxon_id: int
    species_name: str | None
    common_name: str | None
    scientific_name: str | None
    iconic_taxon: str | None
    first_observation_id: str
    first_photo_id: str
    first_photo_status: str | None
    representative_observation_id: str | None
    representative_photo_id: str | None
    first_seen_at: datetime
    observation_count: int
    latest_seen_at: datetime


class DexListResponse(BaseModel):
    items: list[DexListItem]
    next_cursor: str | None = Field(
        default=None,
        description=(
            "Pass back as `before` to fetch the next page. Null when this is the last page."
        ),
    )


async def _cursor_first_seen_at(
    session: AsyncSession,
    *,
    user_id: str,
    before: str,
) -> datetime | None:
    return (
        await session.execute(
            select(models.DexEntry.first_seen_at).where(
                models.DexEntry.user_id == user_id,
                models.DexEntry.id == before,
            )
        )
    ).scalar_one_or_none()


@router.get("/me", response_model=DexListResponse)
async def list_my_dex(
    current_user: CurrentUserDep,
    session: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=_MAX_LIMIT)] = _DEFAULT_LIMIT,
    before: Annotated[str | None, Query(min_length=26, max_length=26)] = None,
) -> DexListResponse:
    user = await resolve_current_user_row(session, current_user)

    representative_observation = aliased(models.Observation)
    representative_photo = aliased(models.Photo)
    first_photo_revocation = aliased(models.PhotoRevocation)
    representative_revocation = aliased(models.PhotoRevocation)

    stmt = (
        select(
            models.DexEntry,
            models.Observation,
            models.Photo,
            models.SpeciesCache,
            representative_observation,
            representative_photo,
            first_photo_revocation,
            representative_revocation,
        )
        .join(
            models.Observation,
            models.DexEntry.first_observation_id == models.Observation.id,
        )
        .join(models.Photo, models.Observation.photo_id == models.Photo.id)
        .outerjoin(
            first_photo_revocation,
            first_photo_revocation.photo_id == models.Photo.id,
        )
        .outerjoin(models.SpeciesCache, models.SpeciesCache.taxon_id == models.DexEntry.taxon_id)
        .outerjoin(
            representative_observation,
            and_(
                representative_observation.id == models.DexEntry.representative_observation_id,
                representative_observation.rejected_at.is_(None),
                representative_observation.moderation_status == "clean",
            ),
        )
        .outerjoin(
            representative_photo,
            and_(
                representative_photo.id == models.DexEntry.representative_photo_id,
                representative_observation.photo_id == representative_photo.id,
                representative_photo.status == "clean",
                representative_photo.attachment_status == "attached",
            ),
        )
        .outerjoin(
            representative_revocation,
            representative_revocation.photo_id == representative_photo.id,
        )
        .where(
            models.DexEntry.user_id == user.id,
            models.Observation.rejected_at.is_(None),
            models.Observation.moderation_status != "rejected",
        )
    )

    if before is not None:
        cursor_first_seen = await _cursor_first_seen_at(
            session,
            user_id=user.id,
            before=before,
        )
        if cursor_first_seen is None:
            return DexListResponse(items=[], next_cursor=None)
        stmt = stmt.where(
            or_(
                models.DexEntry.first_seen_at < cursor_first_seen,
                and_(
                    models.DexEntry.first_seen_at == cursor_first_seen,
                    models.DexEntry.id < before,
                ),
            )
        )

    stmt = stmt.order_by(desc(models.DexEntry.first_seen_at), desc(models.DexEntry.id)).limit(
        limit + 1
    )
    rows = (await session.execute(stmt)).all()

    has_more = len(rows) > limit
    page = rows[:limit]
    items = [
        DexListItem(
            id=dex.id,
            taxon_id=dex.taxon_id,
            species_name=dex.species_name,
            common_name=species.common_name if species is not None else None,
            scientific_name=species.scientific_name if species is not None else None,
            iconic_taxon=species.iconic_taxon if species is not None else None,
            first_observation_id=dex.first_observation_id,
            first_photo_id=first_obs.photo_id,
            first_photo_status=("deleted" if first_revocation is not None else photo.status),
            representative_observation_id=(
                representative_obs.id
                if representative_obs is not None
                and clean_photo is not None
                and clean_revocation is None
                else None
            ),
            representative_photo_id=(
                clean_photo.id
                if representative_obs is not None
                and clean_photo is not None
                and clean_revocation is None
                else None
            ),
            first_seen_at=dex.first_seen_at,
            observation_count=dex.observation_count,
            latest_seen_at=dex.latest_seen_at,
        )
        for (
            dex,
            first_obs,
            photo,
            species,
            representative_obs,
            clean_photo,
            first_revocation,
            clean_revocation,
        ) in page
    ]

    return DexListResponse(
        items=items,
        next_cursor=items[-1].id if has_more and items else None,
    )
