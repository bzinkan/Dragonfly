"""Backfill legacy `completed_steps` string values into the dict shape.

`expedition_progress.completed_steps` values written before the
per-observation replay gate landed are plain ISO-8601 strings; the
current shape is ``{"completed_at": <iso string>, "observation_id":
<ulid>}`` (see `app.services.expedition_progress`). This task rewrites
every legacy string value to ``{"completed_at": <the string>,
"observation_id": null}`` so exactly one value shape exists going
forward.

This is SHAPE-ONLY normalization: the observation ids of pre-migration
completions were never recorded and are unrecoverable, so the handler's
replay gate still cannot match those observations -- a backfilled value
carries ``observation_id: null``, exactly what the legacy string parsed
to. The point is one uniform value shape, not retroactive gating.

Idempotent: dict values (handler-written or already backfilled) are
never touched, so re-running is a no-op.

Run once after deploying the dict value format:

    python -m admin.backfill_step_completions
    python -m admin.backfill_step_completions --dry-run

Same admin-task pattern as expedition_funnel / rarity_refresh:

    python -m admin.backfill_step_completions
"""

from __future__ import annotations

import argparse
import asyncio

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import get_settings
from app.db import models

log = structlog.get_logger()


async def backfill(
    session: AsyncSession,
    *,
    batch_size: int = 500,
    dry_run: bool = False,
) -> dict[str, int]:
    """Rewrite legacy string values in place; returns scan/change counts.

    With dry_run=True the scan still runs but nothing is mutated or
    committed -- only the would-change counts are reported.
    """
    counts = {"rows_scanned": 0, "rows_changed": 0, "values_rewritten": 0}

    rows = (
        (
            await session.execute(
                select(models.ExpeditionProgress).order_by(models.ExpeditionProgress.id)
            )
        )
        .scalars()
        .all()
    )

    uncommitted = 0
    for progress in rows:
        counts["rows_scanned"] += 1
        completed = dict(progress.completed_steps or {})
        legacy_keys = [key for key, value in completed.items() if isinstance(value, str)]
        if not legacy_keys:
            continue
        counts["rows_changed"] += 1
        counts["values_rewritten"] += len(legacy_keys)
        log.info(
            "backfill_step_completions.row",
            progress_id=progress.id,
            expedition_id=progress.expedition_id,
            legacy_steps=legacy_keys,
            dry_run=dry_run,
        )
        if dry_run:
            continue
        for key in legacy_keys:
            # The original crediting observation is unrecoverable --
            # null, matching what parse_step_completion returned for
            # the legacy string.
            completed[key] = {"completed_at": completed[key], "observation_id": None}
        progress.completed_steps = completed
        # JSONB mutation tracking needs an explicit nudge when we
        # reassign with the same key set.
        flag_modified(progress, "completed_steps")
        uncommitted += 1
        if uncommitted >= batch_size:
            await session.commit()
            uncommitted = 0

    if not dry_run and uncommitted:
        await session.commit()
    return counts


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report would-change counts without writing anything",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Commit after this many changed rows (default: 500)",
    )
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    settings = get_settings()
    engine = create_async_engine(settings.sqlalchemy_database_url)
    sessions: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            counts = await backfill(session, batch_size=args.batch_size, dry_run=args.dry_run)
    finally:
        await engine.dispose()

    log.info("backfill_step_completions.complete", dry_run=args.dry_run, **counts)
    prefix = "[dry-run] " if args.dry_run else ""
    print(
        f"{prefix}backfill complete: {counts['rows_scanned']} rows scanned, "
        f"{counts['rows_changed']} rows changed, "
        f"{counts['values_rewritten']} values rewritten"
    )


if __name__ == "__main__":
    asyncio.run(main())
