"""Match-spec interpreter.

`matches(spec, inputs)` walks the spec tree and returns True if the
observation satisfies it. Each Match<Name> Pydantic class maps to a
pure function in `kinds/<name>.py`. Combinators (`all_of`, `any_of`)
recurse back into `matches()`.

Adding a new kind: create the matcher in `kinds/`, register it here.
The boot-time check in `_REGISTRY` raises if a registered kind isn't
implemented (or vice versa) -- catches the common copy-paste mistake.
"""

from __future__ import annotations

from collections.abc import Callable

from app.matchers.context import MatcherInputs
from app.matchers.kinds.any_organism import match_any_organism
from app.matchers.kinds.iconic_taxon import match_iconic_taxon
from app.matchers.kinds.not_in_current_expedition import match_not_in_current_expedition
from app.matchers.kinds.not_in_dex import match_not_in_dex
from app.matchers.kinds.not_within_radius import match_not_within_radius
from app.matchers.kinds.observation_tag import match_observation_tag
from app.matchers.kinds.taxon_id import match_taxon_id
from app.matchers.kinds.taxon_set import match_taxon_set
from app.models.expedition import (
    MatchAllOf,
    MatchAnyOf,
    MatchAnyOrganism,
    MatchIconicTaxon,
    MatchNotInCurrentExpedition,
    MatchNotInDex,
    MatchNotWithinRadius,
    MatchObservationTag,
    MatchSpec,
    MatchTaxonId,
    MatchTaxonSet,
)

# Each entry: spec class -> matcher function.
# Combinators (all_of, any_of) handled inline below since they recurse
# into matches() rather than calling out to a leaf matcher.
_LEAF_MATCHERS: dict[type, Callable[..., bool]] = {
    MatchIconicTaxon: match_iconic_taxon,
    MatchTaxonId: match_taxon_id,
    MatchAnyOrganism: match_any_organism,
    MatchNotInDex: match_not_in_dex,
    MatchNotWithinRadius: match_not_within_radius,
    MatchTaxonSet: match_taxon_set,
    MatchNotInCurrentExpedition: match_not_in_current_expedition,
    MatchObservationTag: match_observation_tag,
}


def matches(spec: MatchSpec, inputs: MatcherInputs) -> bool:
    """Evaluate the match spec against the inputs."""
    if isinstance(spec, MatchAllOf):
        return all(matches(s, inputs) for s in spec.matches)
    if isinstance(spec, MatchAnyOf):
        return any(matches(s, inputs) for s in spec.matches)

    matcher = _LEAF_MATCHERS.get(type(spec))
    if matcher is None:
        # Should be unreachable -- the Pydantic discriminated union
        # ensures `spec` is one of the registered classes.
        raise NotImplementedError(f"No matcher registered for {type(spec).__name__}")
    return bool(matcher(spec, inputs))
