"""iNaturalist taxon lookups (no auth required)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import httpx
import structlog

from app.inat.client import InatUnavailable

log = structlog.get_logger()


@dataclass(frozen=True)
class TaxonInfo:
    taxon_id: int
    scientific_name: str | None
    common_name: str | None
    iconic_taxon: str | None
    raw: dict[str, object]


async def get_taxon(client: httpx.AsyncClient, taxon_id: int) -> TaxonInfo | None:
    """Fetch one taxon. Returns `None` on 404 (taxon doesn't exist)."""
    try:
        res = await client.get(f"/taxa/{taxon_id}")
    except (httpx.TransportError, httpx.TimeoutException) as exc:
        log.warning("inat.taxa.transport_error", taxon_id=taxon_id, error=str(exc))
        raise InatUnavailable("iNat taxa transport error") from exc

    if res.status_code == 404:
        return None
    if res.status_code in (401, 403, 429):
        # Auth/rate problems are OUR outage, not the taxon's absence --
        # same convention as cv.py. Callers degrade (facts_available
        # false / species_name left as-is) instead of treating the
        # taxon as nonexistent.
        log.warning(
            "inat.taxa.degraded",
            taxon_id=taxon_id,
            status=res.status_code,
        )
        raise InatUnavailable(f"iNat taxa auth/rate error: {res.status_code}")
    if res.status_code >= 500:
        raise InatUnavailable(f"iNat taxa server error: {res.status_code}")
    if res.status_code >= 400:
        log.warning(
            "inat.taxa.client_error",
            taxon_id=taxon_id,
            status=res.status_code,
            body=res.text[:200],
        )
        return None

    payload = cast(dict[str, object], res.json())
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return None

    taxon = results[0]
    if not isinstance(taxon, dict):
        return None

    return TaxonInfo(
        taxon_id=taxon_id,
        scientific_name=_str_or_none(taxon.get("name")),
        common_name=_str_or_none(taxon.get("preferred_common_name")),
        iconic_taxon=_str_or_none(taxon.get("iconic_taxon_name")),
        raw=cast(dict[str, object], taxon),
    )


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
