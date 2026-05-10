"""dispatch() -- the entire dispatcher in one function.

Per `docs/dispatcher.md`: per-handler exceptions are isolated; one bad
handler never fails the submission. Rewards from all handlers are
aggregated and sorted by weight (descending) for the client to render
as a celebration sequence.
"""

from __future__ import annotations

import structlog

from app.dispatcher.types import Context, Handler, HandlerResult, Reward

log = structlog.get_logger()


async def dispatch(ctx: Context, handlers: list[Handler]) -> list[Reward]:
    """Run every handler in order, collect rewards, sort by weight desc."""
    all_rewards: list[Reward] = []
    for handler in handlers:
        try:
            result = await handler.handle(ctx)
        except Exception:  # intentional catch-all per docs/dispatcher.md
            log.exception(
                "dispatcher.handler_failed",
                handler=handler.name,
                observation_id=ctx.observation.id,
                user_id=ctx.user.id,
            )
            ctx.results[handler.name] = HandlerResult(rewards=[])
            continue
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
    )
    return all_rewards
