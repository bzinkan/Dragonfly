from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from admin import derived_state_rebuild as rebuild_job


@pytest.mark.asyncio
async def test_strict_drain_repeats_until_no_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = AsyncMock(side_effect=[(50, 0), (2, 0)])
    backlog = AsyncMock(side_effect=[(2, 0), (0, 0)])
    monkeypatch.setattr(rebuild_job, "run", run)
    monkeypatch.setattr(rebuild_job, "backlog_counts", backlog)

    result = await rebuild_job.drain(AsyncMock(), max_passes=3)  # type: ignore[arg-type]

    assert result.complete is True
    assert result.passes == 2
    assert result.succeeded == 52
    assert result.failed_attempts == 0


@pytest.mark.asyncio
async def test_strict_drain_surfaces_terminal_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rebuild_job, "run", AsyncMock(return_value=(0, 1)))
    monkeypatch.setattr(rebuild_job, "backlog_counts", AsyncMock(return_value=(0, 1)))

    result = await rebuild_job.drain(AsyncMock(), max_passes=5)  # type: ignore[arg-type]

    assert result.complete is False
    assert result.terminal_failures == 1
    assert result.passes == 1


@pytest.mark.asyncio
async def test_strict_drain_is_bounded_when_work_remains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rebuild_job, "run", AsyncMock(return_value=(50, 0)))
    monkeypatch.setattr(rebuild_job, "backlog_counts", AsyncMock(return_value=(1, 0)))

    result = await rebuild_job.drain(AsyncMock(), max_passes=2)  # type: ignore[arg-type]

    assert result.complete is False
    assert result.remaining_work == 1
    assert result.passes == 2


def test_strict_rebuild_mode_is_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HINTERLAND_DERIVED_REBUILD_STRICT_DRAIN", raising=False)
    assert rebuild_job._strict_drain_enabled() is False

    monkeypatch.setenv("HINTERLAND_DERIVED_REBUILD_STRICT_DRAIN", "true")
    assert rebuild_job._strict_drain_enabled() is True


@pytest.mark.parametrize("value", ["0", "101", "not-a-number"])
def test_strict_max_passes_is_bounded(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("HINTERLAND_DERIVED_REBUILD_MAX_PASSES", value)

    with pytest.raises(RuntimeError):
        rebuild_job._strict_max_passes()
