"""not_in_current_expedition matcher."""

from __future__ import annotations

from app.matchers.context import MatcherInputs
from app.models.expedition import MatchNotInCurrentExpedition


def match_not_in_current_expedition(
    spec: MatchNotInCurrentExpedition,
    inputs: MatcherInputs,
) -> bool:
    """Match when this taxon has not already completed a step in this run."""
    del spec
    return (
        inputs.taxon is not None
        and inputs.taxon.taxon_id not in inputs.current_expedition_taxon_ids
    )
