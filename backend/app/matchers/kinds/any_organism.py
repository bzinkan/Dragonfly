from __future__ import annotations

from app.matchers.context import MatcherInputs
from app.models.expedition import MatchAnyOrganism


def match_any_organism(spec: MatchAnyOrganism, inputs: MatcherInputs) -> bool:
    """Wildcard: any observation with a known taxon matches.

    An observation with no taxon (manual species_name only, or no
    species at all) doesn't count -- "any organism" means iNat-mapped
    organism per docs/expedition-authoring.md.
    """
    return inputs.taxon is not None
