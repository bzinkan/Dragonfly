"""Snapshot scenarios from `docs/dispatcher.md` table.

Each test maps to a numbered scenario in the doc. The tests stub the
SQLAlchemy session rather than spin up real Postgres -- that's a Phase 11
follow-up for the beta-polish run-the-real-DB harness. The shape we lock
in here is the *contract* between handlers and the dispatcher: given
this DB state, this is the exact ordered list of rewards the kid sees.

Scenarios deferred to Phase 10 (need ExpeditionHandler full impl):
  6. Observation completes an expedition step
  7. Observation completes the final step
  8. One observation advances two expeditions

Scenario 4 (low_data parent-geohash fallback) is deferred to a Phase 9
follow-up -- captured on RarityHandler's docstring.

Scenarios 10 (idempotent re-submit) and 11 (replay after crash) need a
real DB to be meaningful; their handler-level invariants (Dex's
INSERT ... ON CONFLICT, Rarity's idempotent UPSERT) are exercised by
the per-handler unit tests.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models
from app.dispatcher.core import dispatch
from app.dispatcher.handlers.dex import DexHandler
from app.dispatcher.handlers.expedition import ExpeditionHandler
from app.dispatcher.handlers.rarity import RarityHandler
from app.dispatcher.types import Context, Handler, HandlerResult

_USER_ID = "01J0KIDID0000000000000ULID"
_GROUP_ID = "01J0GROUPID00000000000ULID"
_OBS_ID = "01J0OBSID0000000000000ULID"
_PHOTO_ID = "01J0PHOTOID00000000000ULID"


def _user() -> models.User:
    return models.User(id=_USER_ID, firebase_uid="fb-1", role="kid", display_name="Kid")


def _group() -> models.Group:
    return models.Group(id=_GROUP_ID, name="Family", join_code="ABC123", owner_user_id=_USER_ID)


def _obs(*, taxon_id: int = 12345, species_name: str = "Northern Cardinal") -> models.Observation:
    obs = models.Observation(
        id=_OBS_ID,
        user_id=_USER_ID,
        group_id=_GROUP_ID,
        photo_id=_PHOTO_ID,
        latitude=39.1,
        longitude=-84.5,
        taxon_id=taxon_id,
        species_name=species_name,
        geohash4="dnp1",
    )
    obs.created_at = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
    return obs


def _ctx(fake_session: AsyncMock) -> Context:
    return Context(
        db=fake_session,
        user=_user(),
        group=_group(),
        observation=_obs(),
        photo=models.Photo(
            id=_PHOTO_ID,
            user_id=_USER_ID,
            bucket="b",
            object_name=f"observations/{_PHOTO_ID}.jpg",
            status="clean",
        ),
    )


def _wire_for_dex_first_then_rarity(
    fake_session: AsyncMock,
    *,
    dex_inserted_id: str | None,
    rarity_species_row: models.RarityCache | None,
    region_seen: bool = True,
) -> None:
    """Wire `execute()` for the dispatcher run.

    Order of execute() calls (dex then rarity then expedition stub):
    1. DexHandler INSERT ... ON CONFLICT RETURNING
    2. (first-find only) DexHandler counter UPDATE
    3. RarityHandler species lookup
    4. (rarity miss only) RarityHandler region-existence lookup
    5. RarityHandler rarest_tier UPDATE (when observed_tier set)

    ExpeditionHandler stub returns empty without touching the session.
    """
    dex_insert_result = MagicMock()
    dex_insert_result.scalar_one_or_none = MagicMock(return_value=dex_inserted_id)

    dex_update_result = MagicMock()

    rarity_species_result = MagicMock()
    rarity_species_result.scalar_one_or_none = MagicMock(return_value=rarity_species_row)

    rarity_region_result = MagicMock()
    rarity_region_result.scalar_one_or_none = MagicMock(
        return_value="dnp1" if region_seen else None
    )

    rarity_update_result = MagicMock()

    side_effects: list[Any] = [dex_insert_result]
    is_first_find = dex_inserted_id is not None
    if is_first_find:
        side_effects.append(dex_update_result)
    side_effects.append(rarity_species_result)
    if rarity_species_row is None:
        side_effects.append(rarity_region_result)
    # rarest_tier UPDATE -- skipped only when both: rarity hit was None
    # AND region cold-start (observed_tier stays None).
    if rarity_species_row is not None or region_seen:
        side_effects.append(rarity_update_result)

    fake_session.execute = AsyncMock(side_effect=side_effects)
    fake_session.commit = AsyncMock()


def _rarity_row(tier: str) -> models.RarityCache:
    return models.RarityCache(
        id="dnp1:12345",
        region_geohash="dnp1",
        taxon_id=12345,
        tier=tier,
        observation_count=1,
        refreshed_at=datetime(2026, 5, 9, 3, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def fake_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


_HANDLERS: list[Handler] = [
    DexHandler(),
    RarityHandler(),
    ExpeditionHandler(),
]


# ---------------------------------------------------------------------------
# Scenario 1: First observation ever, common species, common region.
# Expected: first_find (80) + rarity_tier common (10), in that weight order.
# ---------------------------------------------------------------------------


async def test_scenario_1_first_find_common_species_common_region(
    fake_session: AsyncMock,
) -> None:
    _wire_for_dex_first_then_rarity(
        fake_session,
        dex_inserted_id="dex-row-1",
        rarity_species_row=_rarity_row("common"),
    )
    rewards = await dispatch(_ctx(fake_session), _HANDLERS)
    assert [r.type for r in rewards] == ["first_find", "rarity_tier"]
    assert [r.weight for r in rewards] == [80, 10]


# ---------------------------------------------------------------------------
# Scenario 2: Repeat find, same species as #1 (still common region).
# Expected: rarity_tier common (10), repeat_find (10) -- equal weights resolve
# by handler registration order (dex then rarity).
# ---------------------------------------------------------------------------


async def test_scenario_2_repeat_find_common_region(fake_session: AsyncMock) -> None:
    _wire_for_dex_first_then_rarity(
        fake_session,
        dex_inserted_id=None,  # ON CONFLICT fired -> repeat
        rarity_species_row=_rarity_row("common"),
    )
    rewards = await dispatch(_ctx(fake_session), _HANDLERS)
    assert [r.type for r in rewards] == ["repeat_find", "rarity_tier"]
    assert [r.weight for r in rewards] == [10, 10]


# ---------------------------------------------------------------------------
# Scenario 3: First find, rare species, common region.
# Expected: first_find (80), rarity_tier rare (40).
# ---------------------------------------------------------------------------


async def test_scenario_3_first_find_rare_species(fake_session: AsyncMock) -> None:
    _wire_for_dex_first_then_rarity(
        fake_session,
        dex_inserted_id="dex-row-1",
        rarity_species_row=_rarity_row("rare"),
    )
    rewards = await dispatch(_ctx(fake_session), _HANDLERS)
    assert [r.type for r in rewards] == ["first_find", "rarity_tier"]
    assert [r.weight for r in rewards] == [80, 40]


# ---------------------------------------------------------------------------
# Scenario 5: Unrecorded species (never seen in region before).
# Expected: unrecorded (100), first_find (80).
# ---------------------------------------------------------------------------


async def test_scenario_5_unrecorded_species(fake_session: AsyncMock) -> None:
    _wire_for_dex_first_then_rarity(
        fake_session,
        dex_inserted_id="dex-row-1",
        rarity_species_row=None,
        region_seen=True,
    )
    rewards = await dispatch(_ctx(fake_session), _HANDLERS)
    assert [r.type for r in rewards] == ["unrecorded", "first_find"]
    assert [r.weight for r in rewards] == [100, 80]


# ---------------------------------------------------------------------------
# Scenario 9: One handler raises; others still produce rewards.
# Expected: dispatcher catches the exception, dex_count for the bad
# handler is empty, other handlers' rewards still flow.
# ---------------------------------------------------------------------------


class _BoomMidHandler:
    name = "boom"

    async def handle(self, ctx: Context) -> HandlerResult:
        raise RuntimeError("intentional")


async def test_scenario_9_handler_raises_others_still_run(
    fake_session: AsyncMock,
) -> None:
    _wire_for_dex_first_then_rarity(
        fake_session,
        dex_inserted_id="dex-row-1",
        rarity_species_row=_rarity_row("common"),
    )
    handlers: list[Handler] = [
        DexHandler(),
        _BoomMidHandler(),
        RarityHandler(),
        ExpeditionHandler(),
    ]
    ctx = _ctx(fake_session)
    rewards = await dispatch(ctx, handlers)

    # Boom handler produced nothing; the other two still emit their rewards.
    assert {r.type for r in rewards} == {"first_find", "rarity_tier"}
    # And the failed handler still gets a recorded HandlerResult so
    # downstream handlers' presence checks don't KeyError.
    assert "boom" in ctx.results
    assert ctx.results["boom"].rewards == []
