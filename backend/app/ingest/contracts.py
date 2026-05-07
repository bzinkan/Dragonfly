"""Shared contracts for closed-beta ingest pipelines.

The implementation workers will land feature by feature, but these contracts
define the behavior every ingest path must preserve: idempotent source IDs,
explicit cursors, auditable status, and retry-safe payloads.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class IngestSource(StrEnum):
    OBSERVATION = "observation"
    PHOTO = "photo"
    EXPEDITION_CONTENT = "expedition_content"
    SPECIES_TAXA = "species_taxa"
    RARITY_SNAPSHOT = "rarity_snapshot"
    GEOCODING_CACHE = "geocoding_cache"
    MODERATION_EVENT = "moderation_event"
    TELEMETRY = "telemetry"


class IngestStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IngestCursor(BaseModel):
    value: dict[str, Any] = Field(default_factory=dict)


class IngestEnvelope(BaseModel):
    source: IngestSource
    source_run_id: str = Field(min_length=1, max_length=160)
    payload: dict[str, Any] = Field(default_factory=dict)
    cursor: IngestCursor | None = None
    checksum: str | None = Field(default=None, max_length=128)
    occurred_at: datetime


class IngestResult(BaseModel):
    source: IngestSource
    source_run_id: str
    status: IngestStatus
    processed_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    cursor: IngestCursor | None = None
    last_error: str | None = None


ObservationIngestKind = Literal["observation_submitted"]
PhotoIngestKind = Literal["photo_uploaded", "photo_moderated"]
ContentIngestKind = Literal["expedition_synced"]


class ObservationIngestPayload(BaseModel):
    kind: ObservationIngestKind
    observation_id: str
    user_id: str
    group_id: str
    photo_id: str
    taxon_id: int | None = None


class PhotoIngestPayload(BaseModel):
    kind: PhotoIngestKind
    photo_id: str
    bucket: str
    object_name: str
    status: Literal["pending", "clean", "quarantine", "deleted"]


class ExpeditionContentIngestPayload(BaseModel):
    kind: ContentIngestKind
    expedition_id: str
    content_hash: Annotated[str, Field(min_length=64, max_length=64)]
    path: str
