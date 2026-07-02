"""Tests for the expedition Pydantic models.

Covers schema validation, snake_case enforcement, step-id uniqueness,
and the discriminated-union resolution for MatchSpec / Prerequisite.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.expedition import (
    Expedition,
    MatchAllOf,
    MatchAnyOf,
    MatchIconicTaxon,
    MatchNotInDex,
    MatchNotWithinRadius,
    MatchTaxonId,
    Step,
)


def _valid_expedition_dict() -> dict[str, object]:
    return {
        "id": "test_starter",
        "title": "Test Starter",
        "tier": 1,
        "duration_minutes": 20,
        "environments": ["yard", "park"],
        "intro": "Look around.",
        "outro": "You contributed real data.",
        "steps": [
            {
                "id": "any_plant",
                "description": "Find a plant",
                "match": {"kind": "iconic_taxon", "value": "Plantae"},
            }
        ],
    }


def test_minimal_valid_expedition_parses() -> None:
    exp = Expedition.model_validate(_valid_expedition_dict())
    assert exp.id == "test_starter"
    assert exp.tier == 1
    assert isinstance(exp.steps[0].match, MatchIconicTaxon)


def test_id_must_be_snake_case() -> None:
    bad = _valid_expedition_dict() | {"id": "TestStarter"}
    with pytest.raises(ValidationError):
        Expedition.model_validate(bad)
    bad2 = _valid_expedition_dict() | {"id": "test-starter"}
    with pytest.raises(ValidationError):
        Expedition.model_validate(bad2)


def test_step_id_must_be_snake_case() -> None:
    bad = _valid_expedition_dict()
    bad["steps"] = [
        {
            "id": "Any-Plant",
            "description": "Find a plant",
            "match": {"kind": "iconic_taxon", "value": "Plantae"},
        }
    ]
    with pytest.raises(ValidationError):
        Expedition.model_validate(bad)


def test_duplicate_step_ids_rejected() -> None:
    bad = _valid_expedition_dict()
    bad["steps"] = [
        {
            "id": "any_plant",
            "description": "Find a plant",
            "match": {"kind": "iconic_taxon", "value": "Plantae"},
        },
        {
            "id": "any_plant",  # duplicate
            "description": "Find another plant",
            "match": {"kind": "iconic_taxon", "value": "Plantae"},
        },
    ]
    with pytest.raises(ValidationError) as exc_info:
        Expedition.model_validate(bad)
    assert "duplicate step id" in str(exc_info.value)


def test_tier_out_of_range_rejected() -> None:
    bad = _valid_expedition_dict() | {"tier": 6}
    with pytest.raises(ValidationError):
        Expedition.model_validate(bad)


def test_too_many_steps_rejected() -> None:
    """5 steps max per docs/expedition-authoring.md."""
    bad = _valid_expedition_dict()
    bad["steps"] = [
        {
            "id": f"step_{i}",
            "description": "x",
            "match": {"kind": "any_organism"},
        }
        for i in range(6)
    ]
    with pytest.raises(ValidationError):
        Expedition.model_validate(bad)


def test_zero_steps_rejected() -> None:
    bad = _valid_expedition_dict() | {"steps": []}
    with pytest.raises(ValidationError):
        Expedition.model_validate(bad)


def test_match_iconic_taxon_value_constrained() -> None:
    bad_step = {
        "id": "x",
        "description": "x",
        "match": {"kind": "iconic_taxon", "value": "NotARealTaxon"},
    }
    bad = _valid_expedition_dict() | {"steps": [bad_step]}
    with pytest.raises(ValidationError):
        Expedition.model_validate(bad)


def test_match_taxon_id_defaults_include_descendants() -> None:
    spec = MatchTaxonId.model_validate({"kind": "taxon_id", "value": 47157})
    assert spec.include_descendants is True


def test_match_not_within_radius_bounds() -> None:
    too_small = {"kind": "not_within_radius_of_existing", "radius_meters": 0}
    too_big = {"kind": "not_within_radius_of_existing", "radius_meters": 11_000}
    with pytest.raises(ValidationError):
        MatchNotWithinRadius.model_validate(too_small)
    with pytest.raises(ValidationError):
        MatchNotWithinRadius.model_validate(too_big)


def test_combinator_all_of_parses_recursively() -> None:
    spec = MatchAllOf.model_validate(
        {
            "kind": "all_of",
            "matches": [
                {"kind": "iconic_taxon", "value": "Plantae"},
                {"kind": "not_in_dex"},
            ],
        }
    )
    assert isinstance(spec.matches[0], MatchIconicTaxon)
    assert isinstance(spec.matches[1], MatchNotInDex)


def test_combinator_any_of_parses() -> None:
    spec = MatchAnyOf.model_validate(
        {
            "kind": "any_of",
            "matches": [
                {"kind": "iconic_taxon", "value": "Aves"},
                {"kind": "iconic_taxon", "value": "Insecta"},
            ],
        }
    )
    assert len(spec.matches) == 2


def test_combinator_empty_matches_rejected() -> None:
    """An empty all_of would vacuously match ANY photo; empty any_of
    would match none. Both are authoring mistakes -- reject them."""
    with pytest.raises(ValidationError):
        MatchAllOf.model_validate({"kind": "all_of", "matches": []})
    with pytest.raises(ValidationError):
        MatchAnyOf.model_validate({"kind": "any_of", "matches": []})


def test_combinator_single_element_accepted() -> None:
    all_of = MatchAllOf.model_validate({"kind": "all_of", "matches": [{"kind": "not_in_dex"}]})
    assert len(all_of.matches) == 1
    any_of = MatchAnyOf.model_validate(
        {"kind": "any_of", "matches": [{"kind": "iconic_taxon", "value": "Aves"}]}
    )
    assert len(any_of.matches) == 1


def test_step_descriminated_union_resolves_each_kind() -> None:
    """One step per kind, just to smoke each one."""
    kinds = [
        {"kind": "iconic_taxon", "value": "Aves"},
        {"kind": "taxon_id", "value": 47157},
        {"kind": "any_organism"},
        {"kind": "not_in_dex"},
        {"kind": "not_within_radius_of_existing", "radius_meters": 50},
    ]
    for k in kinds:
        step = Step.model_validate({"id": "x", "description": "x", "match": k})
        assert step.match is not None
