from __future__ import annotations

from app.matchers.context import MatcherInputs
from app.models.expedition import MatchTaxonId


def match_taxon_id(spec: MatchTaxonId, inputs: MatcherInputs) -> bool:
    """True if observation's taxon == spec.value, OR (with descendants)
    if spec.value appears in the taxon's ancestor chain."""
    if inputs.taxon is None:
        return False
    if inputs.taxon.taxon_id == spec.value:
        return True
    return spec.include_descendants and spec.value in inputs.taxon.ancestor_ids
