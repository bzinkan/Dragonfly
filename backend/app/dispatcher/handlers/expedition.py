"""ExpeditionHandler -- match observations to incomplete expedition steps.

Walks every active expedition for the user, finds the first incomplete
step in each, evaluates its match spec against the observation, advances
matched steps. Per docs/dispatcher.md:

- A single observation can match at most ONE step per expedition (the
  first unmatched), but can advance MULTIPLE expeditions in one shot.
- ExpeditionHandler runs AFTER DexHandler so `not_in_dex` matchers see
  the dex state before this observation's row was inserted.

Phase 10 follow-up: TaxonInfo.ancestor_ids is left empty here. The
`taxon_id` matcher with `include_descendants=True` only works when the
ancestor chain is populated. Once `species_cache` stores the chain
(needs an iNat taxa-tree fetch on cache fill), this handler picks it
up automatically.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.db import models
from app.dispatcher.types import Context, HandlerResult, Reward
from app.matchers.context import MatcherInputs, PriorObservation, TaxonInfo
from app.matchers.registry import matches
from app.models.expedition import Expedition

log = structlog.get_logger()


class ExpeditionHandler:
    name = "expedition"

    async def handle(self, ctx: Context) -> HandlerResult:
        progress_pairs = (
            await ctx.db.execute(
                select(models.ExpeditionProgress, models.ExpeditionContent)
                .join(
                    models.ExpeditionContent,
                    models.ExpeditionProgress.expedition_id == models.ExpeditionContent.id,
                )
                .where(
                    models.ExpeditionProgress.user_id == ctx.user.id,
                    models.ExpeditionProgress.completed_at.is_(None),
                    models.ExpeditionContent.archived.is_(False),
                )
            )
        ).all()

        if not progress_pairs:
            return HandlerResult(rewards=[])

        inputs = await self._build_inputs(ctx)

        rewards: list[Reward] = []
        any_advanced = False

        for progress, content in progress_pairs:
            try:
                exp = Expedition.model_validate(content.body)
            except Exception:  # body got corrupted somehow; don't crash
                log.warning(
                    "dispatcher.expedition.bad_content",
                    expedition_id=content.id,
                )
                continue

            completed = dict(progress.completed_steps or {})
            next_step = next((s for s in exp.steps if s.id not in completed), None)
            if next_step is None:
                # Race: something else completed all steps. Skip.
                continue

            if not matches(next_step.match, inputs):
                continue

            completed[next_step.id] = ctx.observation.created_at.isoformat()
            progress.completed_steps = completed
            # JSONB mutation tracking needs an explicit nudge when we
            # reassign with the same key set.
            flag_modified(progress, "completed_steps")
            any_advanced = True

            rewards.append(
                Reward(
                    type="expedition_step",
                    title="Expedition step!",
                    detail=f"{exp.title}: {next_step.description}",
                    icon="expedition.step",
                    weight=40,
                    payload={"expedition_id": exp.id, "step_id": next_step.id},
                )
            )

            if len(completed) == len(exp.steps):
                progress.completed_at = ctx.observation.created_at
                rewards.append(
                    Reward(
                        type="expedition_complete",
                        title="Expedition complete!",
                        detail=exp.outro,
                        icon="expedition.complete",
                        weight=30,
                        payload={"expedition_id": exp.id},
                    )
                )

        if any_advanced:
            await ctx.db.commit()

        log.info(
            "dispatcher.expedition.complete",
            observation_id=ctx.observation.id,
            user_id=ctx.user.id,
            advanced_count=sum(1 for r in rewards if r.type == "expedition_step"),
            completed_count=sum(1 for r in rewards if r.type == "expedition_complete"),
        )
        return HandlerResult(rewards=rewards)

    async def _build_inputs(self, ctx: Context) -> MatcherInputs:
        obs = ctx.observation

        taxon: TaxonInfo | None = None
        if obs.taxon_id is not None:
            species = (
                await ctx.db.execute(
                    select(models.SpeciesCache).where(models.SpeciesCache.taxon_id == obs.taxon_id)
                )
            ).scalar_one_or_none()
            taxon = TaxonInfo(
                taxon_id=obs.taxon_id,
                iconic_taxon=species.iconic_taxon if species is not None else None,
                # Phase 10 follow-up: store the iNat ancestor chain in
                # species_cache so taxon_id matches with descendants work.
                ancestor_ids=(),
            )

        # Exclude the dex_entry that DexHandler just inserted for this
        # observation -- otherwise not_in_dex would always return False
        # for first finds.
        dex_rows = (
            await ctx.db.execute(
                select(models.DexEntry.taxon_id).where(
                    models.DexEntry.user_id == ctx.user.id,
                    models.DexEntry.first_observation_id != obs.id,
                )
            )
        ).all()
        user_dex = frozenset(r[0] for r in dex_rows)

        prior_rows = (
            await ctx.db.execute(
                select(
                    models.Observation.latitude,
                    models.Observation.longitude,
                ).where(
                    models.Observation.user_id == ctx.user.id,
                    models.Observation.id != obs.id,
                )
            )
        ).all()
        priors = tuple(PriorObservation(latitude=lat, longitude=lng) for lat, lng in prior_rows)

        return MatcherInputs(
            taxon=taxon,
            user_dex_taxon_ids=user_dex,
            user_prior_observations=priors,
            obs_latitude=obs.latitude,
            obs_longitude=obs.longitude,
        )
