"""Closed-choice ecology tags a kid can attach during observation save.

These tags are not identification guesses. They are small, kid-selected
metadata for expedition steps that cannot be inferred safely from an iNat
taxon alone, such as plant life stage.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, Field
from pydantic_core import PydanticCustomError


class EcologyTagOption(BaseModel):
    value: str
    label: str


class EcologyTagDefinition(BaseModel):
    key: str
    label: str
    options: list[EcologyTagOption] = Field(min_length=2)


ECOLOGY_TAG_DEFINITIONS: dict[str, EcologyTagDefinition] = {
    "life_stage": EcologyTagDefinition(
        key="life_stage",
        label="Life stage",
        options=[
            EcologyTagOption(value="flower", label="Flower"),
            EcologyTagOption(value="fruit_seed", label="Fruit or seed"),
            EcologyTagOption(value="seedling", label="Seedling"),
            EcologyTagOption(value="leaf", label="Leaf"),
            EcologyTagOption(value="adult", label="Adult"),
            EcologyTagOption(value="egg_larva_nymph", label="Egg, larva, or nymph"),
        ],
    )
}

_ALLOWED_VALUES = {
    key: {option.value for option in definition.options}
    for key, definition in ECOLOGY_TAG_DEFINITIONS.items()
}


def normalize_ecology_tags(value: Mapping[str, object] | None) -> dict[str, str]:
    """Validate and normalize an observation's ecology_tags payload."""
    if value is None:
        return {}

    normalized: dict[str, str] = {}
    for key, raw in value.items():
        if key not in _ALLOWED_VALUES:
            raise PydanticCustomError(
                "ecology_tag_key",
                "unsupported ecology tag key: {key}",
                {"key": key},
            )
        if not isinstance(raw, str):
            raise PydanticCustomError(
                "ecology_tag_type",
                "ecology tag {key} must be a string",
                {"key": key},
            )
        if raw not in _ALLOWED_VALUES[key]:
            raise PydanticCustomError(
                "ecology_tag_value",
                "unsupported ecology tag value for {key}: {value}",
                {"key": key, "value": raw},
            )
        normalized[key] = raw
    return normalized
