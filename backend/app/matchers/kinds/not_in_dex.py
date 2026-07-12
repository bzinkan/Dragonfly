from __future__ import annotations

from app.matchers.context import MatcherInputs
from app.models.expedition import MatchNotInDex


def match_not_in_dex(spec: MatchNotInDex, inputs: MatcherInputs) -> bool:
    """True if the observation's taxon isn't in the user's Dex yet.

    ExpeditionHandler runs after DexHandler and reuses its atomic first-find
    decision. This avoids a second, potentially inconsistent Dex read.
    """
    if inputs.taxon is None:
        return False
    return inputs.current_taxon_is_first_find
