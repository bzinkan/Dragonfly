"""Tests for admin/backfill_step_completions.py.

`backfill` is driven with a mocked AsyncSession (same style as the
sync_expeditions tests). The invariants that matter: dict values --
handler-written or already backfilled -- are NEVER touched (idempotent),
legacy strings become the dict shape with observation_id=None (shape
only; the original ids are unrecoverable), and --dry-run writes nothing.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from admin.backfill_step_completions import backfill
from app.db import models

_DICT_VALUE = {
    "completed_at": "2026-05-10T12:00:00+00:00",
    "observation_id": "01J0OBSID0000000000000ULID",
}


def _progress(prog_id: str, completed: dict[str, Any]) -> models.ExpeditionProgress:
    return models.ExpeditionProgress(
        id=prog_id,
        user_id="01J0KIDID0000000000000ULID",
        group_id="01J0GROUPID00000000000ULID",
        expedition_id=f"exp-{prog_id}",
        completed_steps=completed,
        completed_at=None,
    )


def _wire(fake_session: AsyncMock, rows: list[models.ExpeditionProgress]) -> None:
    result = MagicMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=rows)
    result.scalars = MagicMock(return_value=scalars)
    fake_session.execute = AsyncMock(return_value=result)
    fake_session.commit = AsyncMock()


@pytest.fixture
def fake_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


async def test_legacy_string_rewritten_to_dict_shape(fake_session: AsyncMock) -> None:
    row = _progress("p1", {"first": "2026-05-10T11:00:00+00:00"})
    _wire(fake_session, [row])

    counts = await backfill(fake_session)

    assert counts == {"rows_scanned": 1, "rows_changed": 1, "values_rewritten": 1}
    # Shape-only: the timestamp is preserved verbatim; the crediting
    # observation is unrecoverable and stays None.
    assert row.completed_steps == {
        "first": {"completed_at": "2026-05-10T11:00:00+00:00", "observation_id": None}
    }
    fake_session.commit.assert_awaited_once()


async def test_dict_values_untouched(fake_session: AsyncMock) -> None:
    """Idempotence: a second run over already-dict values is a no-op --
    no mutation, no commit."""
    row = _progress("p1", {"first": dict(_DICT_VALUE)})
    _wire(fake_session, [row])

    counts = await backfill(fake_session)

    assert counts == {"rows_scanned": 1, "rows_changed": 0, "values_rewritten": 0}
    assert row.completed_steps == {"first": _DICT_VALUE}
    fake_session.commit.assert_not_awaited()


async def test_mixed_row_rewrites_only_the_strings(fake_session: AsyncMock) -> None:
    row = _progress(
        "p1",
        {
            "first": "2026-05-10T11:00:00+00:00",
            "second": dict(_DICT_VALUE),
            "third": "2026-05-10T11:30:00+00:00",
        },
    )
    _wire(fake_session, [row])

    counts = await backfill(fake_session)

    assert counts == {"rows_scanned": 1, "rows_changed": 1, "values_rewritten": 2}
    assert row.completed_steps == {
        "first": {"completed_at": "2026-05-10T11:00:00+00:00", "observation_id": None},
        "second": _DICT_VALUE,
        "third": {"completed_at": "2026-05-10T11:30:00+00:00", "observation_id": None},
    }
    fake_session.commit.assert_awaited_once()


async def test_dry_run_counts_but_never_writes(fake_session: AsyncMock) -> None:
    row = _progress("p1", {"first": "2026-05-10T11:00:00+00:00"})
    _wire(fake_session, [row])

    counts = await backfill(fake_session, dry_run=True)

    assert counts == {"rows_scanned": 1, "rows_changed": 1, "values_rewritten": 1}
    # The legacy value is untouched and nothing was committed.
    assert row.completed_steps == {"first": "2026-05-10T11:00:00+00:00"}
    fake_session.commit.assert_not_awaited()
