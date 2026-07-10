"""Process queued per-user derived-state rebuild jobs.

Run as an Azure Container Apps Job::

    python -m admin.derived_state_rebuild
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db import models
from app.derived_state import process_rebuild_job

log = structlog.get_logger()

_MAX_PER_RUN = 50
_RUNNING_LEASE = timedelta(minutes=15)
_STRICT_ENV = "HINTERLAND_DERIVED_REBUILD_STRICT_DRAIN"
_STRICT_MAX_PASSES_ENV = "HINTERLAND_DERIVED_REBUILD_MAX_PASSES"
_DEFAULT_STRICT_MAX_PASSES = 20


@dataclass(frozen=True)
class DrainResult:
    passes: int
    succeeded: int
    failed_attempts: int
    remaining_work: int
    terminal_failures: int

    @property
    def complete(self) -> bool:
        return self.remaining_work == 0 and self.terminal_failures == 0


async def run(sessions: async_sessionmaker[AsyncSession]) -> tuple[int, int]:
    stale_before = datetime.now(UTC) - _RUNNING_LEASE
    async with sessions() as session:
        ids = (
            (
                await session.execute(
                    select(models.DerivedStateRebuild.id)
                    .where(
                        or_(
                            models.DerivedStateRebuild.status.in_(("queued", "failed")),
                            (
                                (models.DerivedStateRebuild.status == "running")
                                & (models.DerivedStateRebuild.started_at < stale_before)
                            ),
                        ),
                        models.DerivedStateRebuild.attempt_count < 5,
                    )
                    .order_by(models.DerivedStateRebuild.created_at)
                    .limit(_MAX_PER_RUN)
                )
            )
            .scalars()
            .all()
        )
        await session.rollback()

    succeeded = 0
    failed = 0
    for job_id in ids:
        async with sessions() as session:
            if await process_rebuild_job(session, job_id=job_id):
                succeeded += 1
            else:
                failed += 1

    log.info(
        "derived_state_rebuild.run_complete",
        candidates=len(ids),
        succeeded=succeeded,
        failed=failed,
    )
    return succeeded, failed


async def backlog_counts(
    sessions: async_sessionmaker[AsyncSession],
) -> tuple[int, int]:
    """Return nonterminal incomplete work and terminal failures."""

    async with sessions() as session:
        remaining = await session.scalar(
            select(func.count(models.DerivedStateRebuild.id)).where(
                or_(
                    models.DerivedStateRebuild.status.in_(("queued", "running")),
                    (
                        (models.DerivedStateRebuild.status == "failed")
                        & (models.DerivedStateRebuild.attempt_count < 5)
                    ),
                )
            )
        )
        terminal = await session.scalar(
            select(func.count(models.DerivedStateRebuild.id)).where(
                models.DerivedStateRebuild.status == "failed",
                models.DerivedStateRebuild.attempt_count >= 5,
            )
        )
        await session.rollback()
    return int(remaining or 0), int(terminal or 0)


async def drain(
    sessions: async_sessionmaker[AsyncSession],
    *,
    max_passes: int,
) -> DrainResult:
    """Boundedly drain rebuild work for a strict promotion execution."""

    if max_passes < 1:
        raise ValueError("max_passes must be positive")

    succeeded_total = 0
    failed_total = 0
    remaining = 0
    terminal = 0
    passes = 0
    for pass_number in range(1, max_passes + 1):
        passes = pass_number
        succeeded, failed = await run(sessions)
        succeeded_total += succeeded
        failed_total += failed
        remaining, terminal = await backlog_counts(sessions)
        if terminal or remaining == 0:
            break
        # Recent work already claimed by another execution cannot be drained by
        # this promotion process. Fail instead of spinning or declaring success.
        if succeeded == 0 and failed == 0:
            break

    result = DrainResult(
        passes=passes,
        succeeded=succeeded_total,
        failed_attempts=failed_total,
        remaining_work=remaining,
        terminal_failures=terminal,
    )
    log.info("derived_state_rebuild.drain_complete", **result.__dict__)
    return result


def _strict_drain_enabled() -> bool:
    return os.environ.get(_STRICT_ENV, "").strip().lower() in {"1", "true", "yes"}


def _strict_max_passes() -> int:
    raw = os.environ.get(_STRICT_MAX_PASSES_ENV, "").strip()
    if not raw:
        return _DEFAULT_STRICT_MAX_PASSES
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{_STRICT_MAX_PASSES_ENV} must be an integer") from exc
    if not 1 <= value <= 100:
        raise RuntimeError(f"{_STRICT_MAX_PASSES_ENV} must be between 1 and 100")
    return value


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.sqlalchemy_database_url)
    sessions: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )
    try:
        if _strict_drain_enabled():
            result = await drain(sessions, max_passes=_strict_max_passes())
            print(
                "derived_state_rebuild strict: "
                f"passes={result.passes} succeeded={result.succeeded} "
                f"failed_attempts={result.failed_attempts} "
                f"remaining_work={result.remaining_work} "
                f"terminal_failures={result.terminal_failures}"
            )
            if not result.complete:
                raise RuntimeError(
                    "strict derived-state rebuild did not drain cleanly: "
                    f"remaining_work={result.remaining_work}, "
                    f"terminal_failures={result.terminal_failures}"
                )
        else:
            succeeded, failed = await run(sessions)
            print(f"derived_state_rebuild: {succeeded} succeeded, {failed} failed")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
