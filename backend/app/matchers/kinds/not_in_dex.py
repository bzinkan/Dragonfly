from __future__ import annotations

from app.matchers.context import MatcherInputs
from app.models.expedition import MatchNotInDex


def match_not_in_dex(spec: MatchNotInDex, inputs: MatcherInputs) -> bool:
    """True if the observation's taxon isn't in the user's Dex yet.

    Read this with the dispatcher in mind: ExpeditionHandler runs AFTER
    DexHandler. So `user_dex_taxon_ids` reflects the state BEFORE this
    observation -- exactly what we want, otherwise every first-find
    would auto-fail this match.
    """
    if inputs.taxon is None:
        return False
    return inputs.taxon.taxon_id not in inputs.user_dex_taxon_ids
