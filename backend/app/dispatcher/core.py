"""dispatch() -- the entire dispatcher in one function.

Per `docs/dispatcher.md`: per-handler exceptions are isolated; one bad
handler never fails the submission. Rewards from all handlers are
aggregated and sorted by weight (descending) for the client to render
as a celebration sequence.
"""

from __future__ import annotations

from time import perf_counter

import structlog

from app.dispatcher.types import Context, Handler, HandlerResult, Reward

log = structlog.get_logger()


async def dispatch(ctx: Context, handlers: list[Handler]) -> list[Reward]:
    """Run every handler in order, collect rewards, sort by weight desc."""
    started = perf_counter()
    all_rewards: list[Reward] = []
    # Per-handler timing for Risk 0003 closure -- the whole-dispatch
    # `duration_ms` is the SLO budget; the per-handler breakdown
    # is what an operator looks at when a single handler regresses.
    # Records ms even for handlers that raised (so the row is complete
    # in the structured log).
    handler_timings: dict[str, float] = {}
    for handler in handlers:
        handler_started = perf_counter()
        try:
            result = await handler.handle(ctx)
        except Exception:  # intentional catch-all per docs/dispatcher.md
            handler_timings[handler.name] = round((perf_counter() - handler_started) * 1000, 2)
            log.exception(
                "dispatcher.handler_failed",
                handler=handler.name,
                observation_id=ctx.observation.id,
                user_id=ctx.user.id,
            )
            ctx.results[handler.name] = HandlerResult(rewards=[])
            continue
        handler_timings[handler.name] = round((perf_counter() - handler_started) * 1000, 2)
        ctx.results[handler.name] = result
        all_rewards.extend(result.rewards)

    # Stable sort: ties resolve by handler registration order (insertion order
    # of `all_rewards.extend` calls), which is what `docs/dispatcher.md`
    # specifies.
    all_rewards.sort(key=lambda r: r.weight, reverse=True)

    log.info(
        "dispatcher.complete",
        observation_id=ctx.observation.id,
        reward_count=len(all_rewards),
        reward_types=[r.type for r in all_rewards],
        duration_ms=round((perf_counter() - started) * 1000, 2),
        handler_durations_ms=handler_timings,
    )
    return all_rewards
