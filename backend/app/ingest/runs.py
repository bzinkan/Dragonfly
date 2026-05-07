"""Helpers for ingest run state transitions."""

from __future__ import annotations

from datetime import UTC, datetime

from app.ingest.contracts import IngestResult, IngestStatus


def mark_succeeded(result: IngestResult) -> IngestResult:
    """Return a succeeded copy without mutating caller-owned state."""
    return result.model_copy(update={"status": IngestStatus.SUCCEEDED, "last_error": None})


def mark_failed(result: IngestResult, error: str) -> IngestResult:
    """Return a failed copy with a bounded error string for storage/logging."""
    bounded_error = error[:2000]
    return result.model_copy(
        update={
            "status": IngestStatus.FAILED,
            "retry_count": result.retry_count + 1,
            "last_error": bounded_error,
        }
    )


def utc_now() -> datetime:
    return datetime.now(tz=UTC)
