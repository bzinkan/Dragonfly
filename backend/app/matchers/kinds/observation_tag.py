"""observation_tag matcher."""

from __future__ import annotations

from app.matchers.context import MatcherInputs
from app.models.expedition import MatchObservationTag


def match_observation_tag(spec: MatchObservationTag, inputs: MatcherInputs) -> bool:
    """Match a closed-choice observation tag selected during save."""
    return inputs.ecology_tags.get(spec.key) == spec.value
