from __future__ import annotations

from app.matchers.context import MatcherInputs
from app.models.expedition import MatchIconicTaxon


def match_iconic_taxon(spec: MatchIconicTaxon, inputs: MatcherInputs) -> bool:
    """True if the observation's iconic taxon matches the spec value."""
    if inputs.taxon is None:
        return False
    return inputs.taxon.iconic_taxon == spec.value
