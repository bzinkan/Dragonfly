"""Curated taxon-set content used by Expedition matchers."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class TaxonSetEntry(BaseModel):
    taxon_id: Annotated[int, Field(ge=1)]
    name: Annotated[str, Field(min_length=1, max_length=120)]
    common_name: Annotated[str, Field(min_length=1, max_length=160)] | None = None
    rank: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    taxon_id_verified: bool


class ExpeditionTaxonSet(BaseModel):
    id: Annotated[str, Field(min_length=1, max_length=80)]
    title: Annotated[str, Field(min_length=1, max_length=120)]
    description: Annotated[str, Field(min_length=1, max_length=300)]
    taxa: Annotated[list[TaxonSetEntry], Field(min_length=1)]

    @field_validator("id")
    @classmethod
    def id_is_snake_case(cls, v: str) -> str:
        if not v.replace("_", "").isalnum() or v != v.lower():
            raise ValueError("taxon set id must be lowercase snake_case")
        return v

    @field_validator("taxa")
    @classmethod
    def taxa_are_unique_and_verified(cls, taxa: list[TaxonSetEntry]) -> list[TaxonSetEntry]:
        seen: set[int] = set()
        for taxon in taxa:
            if taxon.taxon_id in seen:
                raise ValueError(f"duplicate taxon_id: {taxon.taxon_id}")
            seen.add(taxon.taxon_id)
            if not taxon.taxon_id_verified:
                raise ValueError(f"taxon_id {taxon.taxon_id} must be verified")
        return taxa


class ExpeditionTaxonSetConfig(BaseModel):
    taxon_sets: Annotated[list[ExpeditionTaxonSet], Field(min_length=1)]

    @field_validator("taxon_sets")
    @classmethod
    def ids_are_unique(cls, taxon_sets: list[ExpeditionTaxonSet]) -> list[ExpeditionTaxonSet]:
        seen: set[str] = set()
        for taxon_set in taxon_sets:
            if taxon_set.id in seen:
                raise ValueError(f"duplicate taxon set id: {taxon_set.id}")
            seen.add(taxon_set.id)
        return taxon_sets
