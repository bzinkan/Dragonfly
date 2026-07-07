"""Non-LLM organism suggestion fallback for photos iNat cannot classify."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal, Protocol, cast

import httpx
import structlog
from fastapi import Depends, Request

from app.core.config import Settings

log = structlog.get_logger()


class OrganismFallbackUnavailable(Exception):
    """Raised when the fallback provider is configured but unreachable."""


SuggestionSource = Literal["inat", "fallback"]


@dataclass(frozen=True)
class OrganismFallbackSuggestion:
    common_name: str
    scientific_name: str | None
    score: float


class OrganismFallback(Protocol):
    async def suggest(
        self,
        *,
        image_bytes: bytes,
        top_k: int = 3,
    ) -> list[OrganismFallbackSuggestion]:
        """Return display-only organism guesses, or [] when there is no match."""
        ...


class NoOpOrganismFallback:
    async def suggest(
        self,
        *,
        image_bytes: bytes,
        top_k: int = 3,
    ) -> list[OrganismFallbackSuggestion]:
        return []


_ORGANISM_LABELS: dict[str, tuple[str, str | None]] = {
    "animal": ("Animal", None),
    "amphibian": ("Amphibian", None),
    "bee": ("Bee", None),
    "bird": ("Bird", None),
    "butterfly": ("Butterfly", None),
    "cactus": ("Cactus", None),
    "cat": ("Cat", "Felis catus"),
    "dog": ("Dog", "Canis familiaris"),
    "domestic cat": ("Cat", "Felis catus"),
    "domestic dog": ("Dog", "Canis familiaris"),
    "fern": ("Fern", None),
    "fish": ("Fish", None),
    "flower": ("Flowering plant", None),
    "fungus": ("Fungus", None),
    "grass": ("Grass", None),
    "horse": ("Horse", "Equus caballus"),
    "insect": ("Insect", None),
    "leaf": ("Plant", None),
    "mammal": ("Mammal", None),
    "mushroom": ("Mushroom", None),
    "plant": ("Plant", None),
    "reptile": ("Reptile", None),
    "spider": ("Spider", None),
    "squirrel": ("Squirrel", None),
    "tree": ("Tree", None),
}

_BROADER_LABELS: dict[str, tuple[str, ...]] = {
    "cat": ("mammal", "animal"),
    "dog": ("mammal", "animal"),
    "domestic cat": ("mammal", "animal"),
    "domestic dog": ("mammal", "animal"),
    "horse": ("mammal", "animal"),
    "squirrel": ("mammal", "animal"),
    "bee": ("insect", "animal"),
    "butterfly": ("insect", "animal"),
    "spider": ("animal",),
    "flower": ("plant",),
    "leaf": ("plant",),
    "tree": ("plant",),
}

_NON_OBSERVATION_LABELS = {
    "boy",
    "child",
    "girl",
    "human",
    "man",
    "person",
    "people",
    "woman",
}


class AzureVisionOrganismFallback:
    """Display-only organism fallback backed by Azure AI Vision tags/objects.

    This intentionally does not mint taxon IDs. Suggestions are coarse labels
    such as "Dog" or "Flowering plant"; choosing one saves a manual species
    name and does not trigger Dex/rarity rewards.
    """

    API_VERSION = "2024-02-01"

    def __init__(
        self,
        *,
        endpoint: str,
        key: str,
        timeout: float,
        min_confidence: float,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._key = key
        self._timeout = timeout
        self._min_confidence = min_confidence

    async def suggest(
        self,
        *,
        image_bytes: bytes,
        top_k: int = 3,
    ) -> list[OrganismFallbackSuggestion]:
        if not self._endpoint or not self._key:
            raise OrganismFallbackUnavailable("Azure Vision endpoint/key missing")

        params = {
            "api-version": self.API_VERSION,
            "features": "tags,objects",
            "language": "en",
        }
        url = f"{self._endpoint}/computervision/imageanalysis:analyze"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers={
                    "Ocp-Apim-Subscription-Key": self._key,
                    "Content-Type": "application/octet-stream",
                },
            ) as client:
                res = await client.post(url, params=params, content=image_bytes)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            log.warning("organism_fallback.azure_vision.transport_error", error=str(exc))
            raise OrganismFallbackUnavailable("Azure Vision transport error") from exc

        if res.status_code in (401, 403):
            log.warning("organism_fallback.azure_vision.unauthorized", status=res.status_code)
            raise OrganismFallbackUnavailable(f"Azure Vision unauthorized: {res.status_code}")
        if res.status_code >= 500:
            log.warning("organism_fallback.azure_vision.server_error", status=res.status_code)
            raise OrganismFallbackUnavailable(f"Azure Vision server error: {res.status_code}")
        if res.status_code != 200:
            log.warning(
                "organism_fallback.azure_vision.client_error",
                status=res.status_code,
                body=res.text[:200],
            )
            return []

        payload = cast(dict[str, object], res.json())
        confidences = _extract_confidences(payload)
        suggestions = _organism_suggestions_from_labels(
            confidences,
            min_confidence=self._min_confidence,
            top_k=top_k,
        )
        log.info(
            "organism_fallback.azure_vision.scored",
            suggestion_count=len(suggestions),
            top_labels=list(confidences)[:8],
        )
        return suggestions


def _extract_confidences(payload: dict[str, object]) -> dict[str, float]:
    confidences: dict[str, float] = {}

    def add(name: object, confidence: object) -> None:
        if not isinstance(name, str) or not isinstance(confidence, int | float):
            return
        label = name.strip().lower()
        if not label:
            return
        confidences[label] = max(confidences.get(label, 0.0), float(confidence))

    tags_result = payload.get("tagsResult")
    if isinstance(tags_result, dict):
        values = tags_result.get("values")
        if isinstance(values, list):
            for raw in values:
                if isinstance(raw, dict):
                    add(raw.get("name"), raw.get("confidence"))

    objects_result = payload.get("objectsResult")
    if isinstance(objects_result, dict):
        values = objects_result.get("values")
        if isinstance(values, list):
            for raw_object in values:
                if not isinstance(raw_object, dict):
                    continue
                tags = raw_object.get("tags")
                if isinstance(tags, list):
                    for raw_tag in tags:
                        if isinstance(raw_tag, dict):
                            add(raw_tag.get("name"), raw_tag.get("confidence"))

    return dict(sorted(confidences.items(), key=lambda item: item[1], reverse=True))


def _organism_suggestions_from_labels(
    confidences: dict[str, float],
    *,
    min_confidence: float,
    top_k: int,
) -> list[OrganismFallbackSuggestion]:
    by_name: dict[str, OrganismFallbackSuggestion] = {}

    def add(label: str, confidence: float) -> None:
        if label in _NON_OBSERVATION_LABELS or confidence < min_confidence:
            return
        mapped = _ORGANISM_LABELS.get(label)
        if mapped is None:
            return
        common_name, scientific_name = mapped
        score = round(confidence * 100, 1)
        existing = by_name.get(common_name)
        if existing is None or score > existing.score:
            by_name[common_name] = OrganismFallbackSuggestion(
                common_name=common_name,
                scientific_name=scientific_name,
                score=score,
            )

    for label, confidence in confidences.items():
        add(label, confidence)
        for broader in _BROADER_LABELS.get(label, ()):
            add(broader, max(min_confidence, confidence * 0.92))

    return sorted(by_name.values(), key=lambda s: s.score, reverse=True)[:top_k]


def build_organism_fallback(settings: Settings) -> OrganismFallback:
    if settings.organism_fallback_provider == "azure_vision":
        return AzureVisionOrganismFallback(
            endpoint=settings.azure_vision_endpoint,
            key=settings.azure_vision_key,
            timeout=settings.azure_vision_request_timeout_seconds,
            min_confidence=settings.organism_fallback_min_confidence,
        )
    return NoOpOrganismFallback()


def get_organism_fallback(request: Request) -> OrganismFallback:
    fallback = getattr(request.app.state, "organism_fallback", None)
    if fallback is None:
        settings: Settings = request.app.state.settings
        fallback = build_organism_fallback(settings)
        request.app.state.organism_fallback = fallback
    return cast(OrganismFallback, fallback)


OrganismFallbackDep = Annotated[OrganismFallback, Depends(get_organism_fallback)]
