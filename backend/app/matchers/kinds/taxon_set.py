"""taxon_set matcher."""

from __future__ import annotations

from app.matchers.context import MatcherInputs
from app.models.expedition import MatchTaxonSet


def match_taxon_set(spec: MatchTaxonSet, inputs: MatcherInputs) -> bool:
    """Match a taxon or one of its ancestors against a curated set."""
    if inputs.taxon is None:
        return False

    taxon_ids = inputs.taxon_sets.get(spec.value)
    if not taxon_ids:
        return False

    if inputs.taxon.taxon_id in taxon_ids:
        return True
    return spec.include_descendants and any(
        ancestor_id in taxon_ids for ancestor_id in inputs.taxon.ancestor_ids
    )
