"""Species facts for the kid-facing observation detail screen.

`GET /v1/species/{taxon_id}` serves a small factual "about this species"
sheet extracted from the cached iNaturalist taxon payload
(`species_cache.source_payload` -- the raw `/taxa/{id}` JSON). The
summary text is iNat's Wikipedia extract: real reference content, never
runtime-generated (ADR 0002 forbids kid-facing runtime LLM output; the
Phase-13 follow-up layers author-time REVIEWED blurbs on top of this
same response shape).

Degradation contract mirrors identify's `cv_unavailable`: when iNat is
unreachable and the taxon isn't cached yet, the endpoint returns 200
with `facts_available=false` so the kid UI simply shows nothing extra.
"""

from __future__ import annotations

import html
import re
from typing import Annotated
from urllib.parse import urlparse

import structlog
from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel

from app.core.auth import CurrentUserDep, resolve_current_user_row
from app.db.session import DbSessionDep
from app.inat.client import InatClientDep, InatUnavailable
from app.services import species_cache

router = APIRouter(prefix="/v1/species", tags=["species"])

log = structlog.get_logger()

_TAG_RE = re.compile(r"<[^>]+>")


class SpeciesFactsResponse(BaseModel):
    taxon_id: int
    common_name: str | None
    scientific_name: str | None
    rank: str | None
    iconic_taxon: str | None
    # Wikipedia extract via iNat, HTML stripped. A future reviewed
    # kid-blurb (ADR 0002 follow-up) overrides this field server-side;
    # the client contract doesn't change.
    summary: str | None
    wikipedia_url: str | None
    observations_worldwide: int | None
    conservation_status: str | None
    facts_available: bool = True


def _plain_text(value: object) -> str | None:
    """Strip tags + unescape entities to a fixpoint.

    The summary is world-editable Wikipedia content mirrored by iNat, so
    entity-escaped markup (`&lt;script&gt;`, or double-escaped variants)
    must never survive into the plain-text contract -- a single
    strip-then-unescape pass would synthesize literal tags from escaped
    ones. Input that never stabilizes is dropped outright.
    """
    if not isinstance(value, str):
        return None
    text = value
    for _ in range(5):
        stripped = html.unescape(_TAG_RE.sub("", text))
        if stripped == text:
            break
        text = stripped
    else:
        return None
    text = text.strip()
    return text or None


def _str_field(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def _int_field(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _conservation_status(payload: dict[str, object]) -> str | None:
    raw = payload.get("conservation_status")
    if not isinstance(raw, dict):
        return None
    name = raw.get("status_name")
    return name if isinstance(name, str) and name else None


def _wikipedia_url(payload: dict[str, object]) -> str | None:
    """Only ever hand the client a real https Wikipedia link.

    The payload is world-editable upstream; anything that isn't
    `https://*.wikipedia.org` is dropped rather than passed through to a
    surface that might one day render it tappable.
    """
    url = _str_field(payload, "wikipedia_url")
    if url is None:
        return None
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return None
    host = parsed.netloc.lower()
    if host == "wikipedia.org" or host.endswith(".wikipedia.org"):
        return url
    return None


def facts_from_payload(taxon_id: int, payload: dict[str, object]) -> SpeciesFactsResponse:
    """Pure extraction from a raw iNat `/taxa/{id}` result dict.

    Every field is optional-tolerant: iNat payloads vary by taxon and
    the cache may hold minimal rows (e.g. test seeds, very old fills).
    """
    return SpeciesFactsResponse(
        taxon_id=taxon_id,
        common_name=_str_field(payload, "preferred_common_name"),
        scientific_name=_str_field(payload, "name"),
        rank=_str_field(payload, "rank"),
        iconic_taxon=_str_field(payload, "iconic_taxon_name"),
        summary=_plain_text(payload.get("wikipedia_summary")),
        wikipedia_url=_wikipedia_url(payload),
        observations_worldwide=_int_field(payload, "observations_count"),
        conservation_status=_conservation_status(payload),
        facts_available=True,
    )


@router.get("/{taxon_id}", response_model=SpeciesFactsResponse)
async def get_species_facts(
    # int32-bounded: an unbounded int overflows the asyncpg bind on the
    # Integer PK and 500s instead of 422ing. ge=1 matches every other
    # user-supplied taxon_id in the codebase.
    taxon_id: Annotated[int, Path(ge=1, le=2_147_483_647)],
    current_user: CurrentUserDep,
    session: DbSessionDep,
    inat_client: InatClientDep,
) -> SpeciesFactsResponse:
    await resolve_current_user_row(session, current_user)

    try:
        payload = await species_cache.get_source_payload(session, inat_client, taxon_id)
    except InatUnavailable as exc:
        # iNat down + cache empty: the kid UI quietly shows no facts.
        # Same graceful-degradation contract as identify's cv_unavailable.
        log.warning(
            "species.facts.unavailable",
            taxon_id=taxon_id,
            reason=str(exc),
        )
        return SpeciesFactsResponse(
            taxon_id=taxon_id,
            common_name=None,
            scientific_name=None,
            rank=None,
            iconic_taxon=None,
            summary=None,
            wikipedia_url=None,
            observations_worldwide=None,
            conservation_status=None,
            facts_available=False,
        )

    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taxon not found")

    # Persist a fresh cache fill (no-op on a pure cache hit).
    await session.commit()

    return facts_from_payload(taxon_id, payload)
