"""DexHandler -- atomic first-find detection + dex_count counter bump.

Owns:
- The DexEntry row (one per (user_id, taxon_id))
- memberships.dex_count (incremented on first find)
- The first_find / repeat_find rewards

Per `docs/dispatcher.md` this handler MUST run first because downstream
handlers (ExpeditionHandler, MissionHandler, ...) read
`ctx.results["dex"].state[STATE_IS_FIRST_FIND]` to gate "rare discovery"
bonuses. Don't reorder without auditing every handler that depends on it.

Per AGENTS.md non-negotiables: the first-find check uses an atomic
conditional insert (INSERT ... ON CONFLICT DO NOTHING RETURNING). Never
introduce a read-then-write pattern here -- two simultaneous submissions
of the same species would both see "no row" and both bump the counter.
"""

from __future__ import annotations

import structlog
from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.db import models
from app.dispatcher.types import Context, HandlerResult, Reward

log = structlog.get_logger()


class DexHandler:
    name = "dex"
    version = "2"

    # Public state keys -- downstream handlers should reference these
    # constants instead of bare strings.
    STATE_IS_FIRST_FIND = "is_first_find"

    async def handle(self, ctx: Context) -> HandlerResult:
        obs = ctx.observation

        # No taxon -> no Dex entry. Repeat-find rewards aren't meaningful
        # without a species to deduplicate on.
        if obs.taxon_id is None:
            return HandlerResult(rewards=[], state={self.STATE_IS_FIRST_FIND: False})

        # Atomic insert. RETURNING is empty when ON CONFLICT fired, so
        # we use that as the first-find signal -- no read-then-write race.
        observed_at = obs.observed_at or obs.created_at
        photo_is_clean = obs.moderation_status == "clean" and ctx.photo.status == "clean"
        new_id = str(ULID())
        stmt = (
            pg_insert(models.DexEntry)
            .values(
                id=new_id,
                user_id=ctx.user.id,
                group_id=obs.group_id,
                taxon_id=obs.taxon_id,
                species_name=obs.species_name,
                first_observation_id=obs.id,
                first_seen_at=observed_at,
                observation_count=1,
                latest_seen_at=observed_at,
                representative_observation_id=obs.id if photo_is_clean else None,
                representative_photo_id=obs.photo_id if photo_is_clean else None,
            )
            .on_conflict_do_nothing(constraint="uq_dex_entries_user_taxon")
            .returning(models.DexEntry.id)
        )
        inserted_id = (await ctx.db.execute(stmt)).scalar_one_or_none()
        is_first_find = inserted_id is not None

        if not is_first_find:
            # The durable handler ledger guarantees this succeeds once per
            # accepted observation. A backdated observation may replace the
            # first-seen fact without replaying a first-find celebration.
            is_earlier = or_(
                models.DexEntry.first_seen_at > observed_at,
                and_(
                    models.DexEntry.first_seen_at == observed_at,
                    models.DexEntry.first_observation_id > obs.id,
                ),
            )
            await ctx.db.execute(
                update(models.DexEntry)
                .where(
                    models.DexEntry.user_id == ctx.user.id,
                    models.DexEntry.taxon_id == obs.taxon_id,
                )
                .values(
                    species_name=(
                        obs.species_name
                        if obs.species_name is not None
                        else models.DexEntry.species_name
                    ),
                    first_seen_at=case(
                        (is_earlier, observed_at),
                        else_=models.DexEntry.first_seen_at,
                    ),
                    first_observation_id=case(
                        (is_earlier, obs.id),
                        else_=models.DexEntry.first_observation_id,
                    ),
                    observation_count=models.DexEntry.observation_count + 1,
                    latest_seen_at=func.greatest(
                        models.DexEntry.latest_seen_at,
                        observed_at,
                    ),
                )
            )

        if photo_is_clean:
            await promote_clean_representative(ctx.db, observation=obs, photo=ctx.photo)

        if is_first_find:
            # Bump dex_count atomically on the membership row. The
            # observation_count counter is bumped by the create endpoint;
            # dex_count is the dispatcher's responsibility.
            await ctx.db.execute(
                update(models.Membership)
                .where(
                    models.Membership.user_id == ctx.user.id,
                    models.Membership.group_id == obs.group_id,
                )
                .values(dex_count=models.Membership.dex_count + 1)
            )
            reward = Reward(
                type="first_find",
                title="New species!",
                detail=_format_first_find_detail(obs),
                icon="dex.first_find",
                weight=80,
                payload={"taxon_id": obs.taxon_id},
            )
        else:
            # Repeat find -- no DB writes beyond the no-op insert.
            reward = Reward(
                type="repeat_find",
                title="Logged",
                detail=_format_repeat_find_detail(obs),
                icon="dex.repeat",
                weight=10,
                payload={"taxon_id": obs.taxon_id},
            )

        log.info(
            "dispatcher.dex.complete",
            observation_id=obs.id,
            user_id=ctx.user.id,
            taxon_id=obs.taxon_id,
            is_first_find=is_first_find,
        )
        return HandlerResult(
            rewards=[reward],
            state={self.STATE_IS_FIRST_FIND: is_first_find},
        )


def _format_first_find_detail(obs: models.Observation) -> str:
    species = obs.species_name or "this species"
    return f"First {species} in your Dex"


def _format_repeat_find_detail(obs: models.Observation) -> str:
    species = obs.species_name or "this species"
    return f"Another {species}"


async def promote_clean_representative(
    session: AsyncSession,
    *,
    observation: models.Observation,
    photo: models.Photo,
) -> None:
    """Promote the newest verified-clean image without changing Dex counts.

    Moderation calls this after both lifecycle rows become clean. Rebuilds use
    the same function while replaying accepted observations chronologically.
    """

    if (
        observation.taxon_id is None
        or observation.rejected_at is not None
        or observation.moderation_status != "clean"
        or photo.status != "clean"
        or photo.attachment_status != "attached"
    ):
        return

    observed_at = observation.observed_at or observation.created_at
    current_representative_seen = (
        select(models.Observation.observed_at)
        .where(models.Observation.id == models.DexEntry.representative_observation_id)
        .scalar_subquery()
    )
    await session.execute(
        update(models.DexEntry)
        .where(
            models.DexEntry.user_id == observation.user_id,
            models.DexEntry.taxon_id == observation.taxon_id,
            or_(
                models.DexEntry.representative_observation_id.is_(None),
                current_representative_seen < observed_at,
                and_(
                    current_representative_seen == observed_at,
                    models.DexEntry.representative_observation_id < observation.id,
                ),
            ),
        )
        .values(
            representative_observation_id=observation.id,
            representative_photo_id=photo.id,
        )
    )
