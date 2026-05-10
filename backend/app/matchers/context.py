"""Pure-data inputs to the matcher functions.

Keeping the matcher inputs as a frozen dataclass (not the dispatcher
Context, which has the live DB session) lets matchers stay pure and
trivially unit-testable. The MatcherInputs object is built by the
ExpeditionHandler from data it already has loaded.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaxonInfo:
    taxon_id: int
    iconic_taxon: str | None
    ancestor_ids: tuple[int, ...]
    """The full ancestor chain (root -> immediate parent), used by
    `taxon_id` matches with include_descendants=True."""


@dataclass(frozen=True)
class PriorObservation:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class MatcherInputs:
    """Everything a matcher might need to decide. Pure data, no DB."""

    taxon: TaxonInfo | None
    """None when the observation has no taxon -- e.g. manual species_name only."""

    user_dex_taxon_ids: frozenset[int]
    """Taxa the user already has in their Dex. Used by not_in_dex."""

    user_prior_observations: tuple[PriorObservation, ...]
    """All of the user's prior observations (for not_within_radius)."""

    obs_latitude: float
    obs_longitude: float
